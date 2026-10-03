#!/usr/bin/env python3
"""Device and app readiness for execute-mobile-test-cases (Phase 0). Real devices only.

  python device_info.py --platform android|ios [--serial <serial/UDID>] [--device "<name from the plan>"]
                        [--app "<APK/IPA path or package/bundle id>"] [--expected-hash <app_hash from the manifest>]
                        [--install] [--out <file.json>]

- Picks the real device (the serial given, else the device named in the plan, else the first connected real device);
  emulators and simulators are never used.
- Records model, manufacturer, OS version, screen size, language, dark mode, network (Wi-Fi / mobile data / offline),
  orientation lock and battery, and whether the device is awake and unlocked (a reminder; nothing is changed).
- App: installed or not, installed version and build, file version and build, file hash; with --install the app file
  from the plan is installed when it is missing or when the installed build differs from the file.
- Compares the app build fingerprint with --expected-hash (the build the exploration was made with) and says so when
  they differ, so the report can mention that the knowledge may be older than the build.
- Prints JSON with `environment_lines` ready for the bug Environment section and the report header.
Exit 1 when no real device is ready or the app cannot be installed / found.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_prerequisites as cp  # noqa: E402


def android_state(serial):
    def sh(*args, timeout=20):
        return cp.adb(["shell", *args], serial, timeout=timeout)[1].strip()
    d = cp.android_device_details(serial)
    m = re.search(r"(\d+)x(\d+)", sh("wm", "size").split("Override size:")[-1])
    d["screen"] = f"{m.group(1)} x {m.group(2)}" if m else ""
    dm = re.search(r"(\d+)", sh("wm", "density").split("Override density:")[-1])
    d["density"] = dm.group(1) if dm else ""
    loc = sh("getprop", "persist.sys.locale") or sh("getprop", "ro.product.locale")
    d["language"] = loc
    night = sh("cmd", "uimode", "night")
    d["dark_mode"] = "on" if "yes" in night.lower() else ("off" if "no" in night.lower() else "unknown")
    airplane = sh("settings", "get", "global", "airplane_mode_on") == "1"
    wifi_dump = sh("dumpsys", "wifi", timeout=30)
    wifi_on = bool(re.search(r"Wi-Fi is enabled", wifi_dump))
    conn = sh("dumpsys", "connectivity", timeout=30)
    active = re.search(r"Active default network: (\S+)", conn)
    transport = ""
    if re.search(r"NetworkAgentInfo.*?WIFI.*?CONNECTED", conn.replace("\n", " ")[:20000]):
        transport = "Wi-Fi"
    elif re.search(r"NetworkAgentInfo.*?(MOBILE|CELLULAR).*?CONNECTED", conn.replace("\n", " ")[:20000]):
        transport = "mobile data"
    d["network"] = "offline (airplane mode)" if airplane else (transport or ("Wi-Fi" if wifi_on and active else
                                                                             ("offline" if not active else "connected")))
    rot = sh("settings", "get", "system", "accelerometer_rotation")
    d["auto_rotate"] = rot == "1"
    batt = re.search(r"level: (\d+)", sh("dumpsys", "battery"))
    d["battery"] = f"{batt.group(1)}%" if batt else ""
    return d


def ios_state(udid):
    d = {"serial": udid, "manufacturer": "Apple", "model": "", "os_version": "", "os": ""}
    if cp.which("ideviceinfo"):
        code, out = cp.run(["ideviceinfo", "-u", udid], timeout=30, shell=False)
        info = dict(l.split(": ", 1) for l in out.splitlines() if ": " in l)
        d.update(model=info.get("ProductType", ""), os_version=info.get("ProductVersion", ""),
                 language=info.get("Locale", ""))
        d["os"] = f"iOS {d['os_version']}".strip()
    return d


def install_android(serial, path):
    code, out = cp.adb(["install", "-r", "-d", "-t", path], serial, timeout=600)
    ok = code == 0 and "Success" in out
    return ok, out.strip().splitlines()[-1] if out.strip() else ""


def main():
    cp.utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--platform", choices=["android", "ios"], required=True)
    ap.add_argument("--serial")
    ap.add_argument("--device")
    ap.add_argument("--app")
    ap.add_argument("--expected-hash")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = {"ok": False, "platform": a.platform, "device": None, "app": None, "problems": [], "notes": [],
           "installed_now": False, "environment_lines": []}

    # device
    if a.platform == "android":
        real, emus, not_ready = cp.real_android_devices()
    else:
        real, emus = cp.ios_real_devices()
        not_ready = []
    if a.serial:
        real = [d for d in real if d["serial"] == a.serial] or real
    dev, note = cp.pick_device(real, a.serial or a.device)
    if not dev:
        msg = cp.REAL_DEVICE_MSG
        if emus:
            msg = f"Only an emulator or simulator is connected. {cp.REAL_DEVICE_MSG}"
        if not_ready:
            msg = "; ".join(f"{d['serial']}: {d['problem']}" for d in not_ready) + f". {cp.REAL_DEVICE_MSG}"
        out["problems"].append(msg)
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        print()
        sys.exit(1)
    state = android_state(dev["serial"]) if a.platform == "android" else ios_state(dev["serial"])
    state["real_device"] = True
    out["device"] = state
    out["notes"].append(note)
    if state.get("awake") is False or state.get("locked"):
        out["notes"].append("The device screen is off or locked: unlock it and keep it awake during the run.")

    # app
    if a.app:
        info = cp.inspect_app(a.app, a.platform, dev["serial"], scan=False)
        app = {"given": a.app, "kind": info["kind"], "path": info.get("path"), "package": info.get("package"),
               "file_version": info.get("version") if info["kind"] == "file" else "",
               "file_build": info.get("build") if info["kind"] == "file" else "",
               "file_hash": info.get("sha256") if info["kind"] == "file" else "",
               "fingerprint": cp.app_fingerprint(info)}
        if info["kind"] == "file" and not info["exists"]:
            out["problems"].append(f"The app file in the test plan does not exist: {info.get('path')}")
        inst = cp.installed_android_app(app["package"], dev["serial"]) if a.platform == "android" and app["package"] \
            else {"installed": None, "version": "", "build": "", "sha256": ""}
        if a.platform == "android" and info["kind"] == "file" and info["exists"]:
            stale = inst["installed"] and inst["sha256"] and app["file_hash"] and inst["sha256"] != app["file_hash"] \
                and len(inst.get("apk_paths") or []) == 1
            if not inst["installed"] or (a.install and stale):
                if a.install:
                    ok, msg = install_android(dev["serial"], info["path"])
                    if ok:
                        out["installed_now"] = True
                        out["notes"].append("The app from the test plan was installed on the device"
                                            + (" (replacing a different build)." if stale else "."))
                        inst = cp.installed_android_app(app["package"], dev["serial"])
                    else:
                        out["problems"].append(f"The app file could not be installed on the device: {msg}")
                else:
                    out["notes"].append("The app is not installed (or another build is installed); "
                                        "run again with --install.")
        elif a.platform == "android" and info["kind"] == "installed" and not inst["installed"]:
            out["problems"].append(f"The app {app['package']} is not installed on the device and the test plan gives "
                                   "no app file to install.")
        app.update(installed=inst.get("installed"), installed_version=inst.get("version", ""),
                   installed_build=inst.get("build", ""), installed_hash=inst.get("sha256", ""))
        app["version"] = app["installed_version"] or app["file_version"]
        app["build"] = app["installed_build"] or app["file_build"]
        if a.expected_hash:
            app["matches_exploration"] = app["fingerprint"] == a.expected_hash
            if not app["matches_exploration"]:
                out["notes"].append("The app build differs from the one the exploration was made with; the stored "
                                    "knowledge may be older than this build.")
        out["app"] = app

    d = out["device"]
    lines = []
    if out["app"]:
        lines.append(f"App: {out['app'].get('package') or ''} {out['app'].get('version') or ''} "
                     f"(build {out['app'].get('build') or 'unknown'})".replace("  ", " "))
    lines.append(f"Device: {' '.join(x for x in (d.get('manufacturer'), d.get('model')) if x)} (real device)")
    lines.append(f"Operating system: {d.get('os') or ''}")
    if d.get("network"):
        lines.append(f"Network: {d['network']}")
    screen = ["portrait"]
    if d.get("language"):
        screen.append(f"language {d['language']}")
    if d.get("dark_mode") in ("on", "off"):
        screen.append(f"dark mode {d['dark_mode']}")
    lines.append("Screen: " + ", ".join(screen) + (f" ({d['screen']})" if d.get("screen") else ""))
    out["environment_lines"] = lines
    out["ok"] = not out["problems"]
    text = json.dumps(out, indent=2, ensure_ascii=False)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
