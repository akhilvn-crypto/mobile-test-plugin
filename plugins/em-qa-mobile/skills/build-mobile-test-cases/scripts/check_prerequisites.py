#!/usr/bin/env python3
"""Phase 0 prerequisite check for the mobile skills (Appium + Flutter, real devices only).

  python check_prerequisites.py --platform android|ios [--app "<APK/IPA path or package/bundle id>"]
                                [--device "<name, model or serial from the test plan>"]
                                [--appium-url http://127.0.0.1:4723] [--install] [--start-server]
                                [--server-log "<file>"] [--skip-app-scan]

Checks (each with the exact fix when missing):
  Node.js 22+ and npm, Java 8+, Android SDK (ANDROID_HOME, adb) or Xcode (macOS, iOS only), Appium server,
  the drivers uiautomator2 / xcuitest and appium-flutter-integration-driver, the Appium server status,
  a REAL connected device (emulators and simulators are never accepted), the device awake and unlocked
  (a reminder only - device settings are never changed), ffmpeg (optional), and the app:
  file exists / app installed, version, build number, sha256 (the app build fingerprint), whether it is a
  Flutter app and whether it contains the test server (appium_flutter_server) the Flutter driver needs.

--install       installs only light items: Appium (npm -g) and missing Appium drivers. Never the Android SDK or Xcode.
--start-server  starts the Appium server in the background when it is not running and waits for it.

Prints JSON {ok, platform, checks[], missing[], installed[], devices[], device, app, server}. Exit 1 when a required
item is missing (the `missing` list holds the messages to show the user), 0 otherwise.
Other scripts import inspect_app(), adb(), real_android_devices() and app_fingerprint() from this file.
"""
import argparse
import glob
import hashlib
import json
import os
import platform as pyplatform
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

REAL_DEVICE_MSG = "A real device is required for now. Please connect one."
FLUTTER_DRIVER = "appium-flutter-integration-driver"
TEST_SERVER_MARK = b"appium_flutter_server"


# ---------------------------------------------------------------- helpers

def utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def run(cmd, timeout=60, shell=None):
    """-> (exit code, stdout+stderr text). Never raises for a missing program (code 127)."""
    if shell is None:
        shell = os.name == "nt" and isinstance(cmd, str)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def which(name):
    p = shutil.which(name)
    if p:
        return p
    if os.name == "nt":
        for ext in (".cmd", ".exe", ".bat"):
            p = shutil.which(name + ext)
            if p:
                return p
    return None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def android_home():
    for k in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        v = os.environ.get(k)
        if v and os.path.isdir(v):
            return v
    return None


def adb_path():
    p = which("adb")
    if p:
        return p
    home = android_home()
    if home:
        cand = os.path.join(home, "platform-tools", "adb.exe" if os.name == "nt" else "adb")
        if os.path.exists(cand):
            return cand
    return None


def adb(args, serial=None, timeout=60):
    exe = adb_path()
    if not exe:
        return 127, "adb not found"
    cmd = [exe] + (["-s", serial] if serial else []) + list(args)
    return run(cmd, timeout=timeout, shell=False)


# ---------------------------------------------------------------- devices

def real_android_devices():
    """-> (real[], emulators[], not_ready[]) from `adb devices -l`. Emulators are listed but never accepted."""
    code, out = adb(["devices", "-l"], timeout=30)
    real, emus, not_ready = [], [], []
    if code != 0:
        return real, emus, not_ready
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        serial, state = parts[0], parts[1] if len(parts) > 1 else ""
        info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        entry = {"serial": serial, "state": state, "model": info.get("model", "").replace("_", " "),
                 "device": info.get("device", ""), "transport": "usb" if "usb" in info else "network"}
        is_emu = serial.startswith("emulator-") or re.search(r"sdk_g?phone|generic|emulator|vbox|genymotion",
                                                               (info.get("model", "") + info.get("device", "") +
                                                                info.get("product", "")).lower())
        if state == "device" and not is_emu:
            _, qemu = adb(["shell", "getprop", "ro.kernel.qemu"], serial, timeout=15)
            is_emu = qemu.strip() == "1"
        if is_emu:
            emus.append(entry)
        elif state != "device":
            entry["problem"] = {"unauthorized": "USB debugging is not authorised: unlock the phone and accept the "
                                                "'Allow USB debugging' prompt",
                                "offline": "the device is offline: reconnect the USB cable"}.get(state, f"state {state}")
            not_ready.append(entry)
        else:
            real.append(entry)
    return real, emus, not_ready


def android_device_details(serial):
    def prop(name):
        return adb(["shell", "getprop", name], serial, timeout=15)[1].strip()
    d = {"serial": serial, "manufacturer": prop("ro.product.manufacturer"), "model": prop("ro.product.model"),
         "os_version": prop("ro.build.version.release"), "api_level": prop("ro.build.version.sdk")}
    d["os"] = f"Android {d['os_version']}".strip()
    _, power = adb(["shell", "dumpsys", "power"], serial, timeout=20)
    m = re.search(r"mWakefulness=(\w+)", power)
    d["awake"] = (m.group(1) == "Awake") if m else None
    _, win = adb(["shell", "dumpsys", "window"], serial, timeout=20)
    locked = re.search(r"(mDreamingLockscreen=true|isKeyguardShowing=true|mShowingLockscreen=true|"
                       r"KeyguardShowing=true)", win)
    d["locked"] = bool(locked) if win else None
    return d


def ios_real_devices():
    """Physical iPhones only (macOS). Simulators are listed separately and never accepted."""
    real, sims = [], []
    if which("xcrun"):
        code, out = run(["xcrun", "xctrace", "list", "devices"], timeout=60, shell=False)
        section = None
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("== "):
                section = s.strip("= ").lower()
                continue
            m = re.match(r"^(.*?)\s+\(([\d.]+)\)\s+\(([0-9A-Fa-f-]{20,})\)$", s)
            if not m:
                continue
            entry = {"name": m.group(1), "os_version": m.group(2), "udid": m.group(3), "serial": m.group(3),
                     "model": m.group(1), "os": f"iOS {m.group(2)}"}
            if section and "simulator" in section:
                sims.append(entry)
            elif section and "offline" not in section and not re.search(r"\bMac\b", m.group(1)):
                real.append(entry)
    elif which("idevice_id"):
        _, out = run(["idevice_id", "-l"], timeout=30, shell=False)
        for u in out.split():
            real.append({"udid": u, "serial": u, "name": u, "model": u})
    return real, sims


def pick_device(devices, wanted):
    if not devices:
        return None, None
    if wanted:
        w = wanted.lower()
        for d in devices:
            hay = " ".join(str(d.get(k, "")) for k in ("serial", "model", "name", "device", "udid")).lower()
            if w in hay or any(tok and tok in hay for tok in re.split(r"[\s,()]+", w) if len(tok) > 3):
                return d, f"Using the device named in the test plan: {d.get('model') or d.get('name')} ({d['serial']})."
        return devices[0], (f"The device named in the test plan ({wanted}) is not connected; using the first connected "
                            f"real device: {devices[0].get('model') or devices[0].get('name')} ({devices[0]['serial']}).")
    return devices[0], (f"No device named in the test plan; using the first connected real device: "
                        f"{devices[0].get('model') or devices[0].get('name')} ({devices[0]['serial']}).")


# ---------------------------------------------------------------- APK / IPA inspection

def _axml_manifest_attrs(data):
    """Minimal Android binary XML reader: attributes of the <manifest> start tag (package, versionCode, versionName)."""
    try:
        pos = 8
        strings = []
        attrs = {}
        while pos < len(data):
            ctype, hsize, csize = struct.unpack_from("<HHI", data, pos)
            if csize == 0:
                break
            if ctype == 0x0001:  # string pool
                count, _styles, flags, str_start, _ = struct.unpack_from("<IIIII", data, pos + 8)
                utf8 = bool(flags & 0x100)
                offs = struct.unpack_from(f"<{count}I", data, pos + hsize)
                base = pos + str_start
                for o in offs:
                    p = base + o
                    if utf8:
                        n = data[p]
                        p += 2 if n & 0x80 else 1
                        n = data[p]
                        if n & 0x80:
                            n = ((n & 0x7F) << 8) | data[p + 1]
                            p += 2
                        else:
                            p += 1
                        strings.append(data[p:p + n].decode("utf-8", "replace"))
                    else:
                        n = struct.unpack_from("<H", data, p)[0]
                        p += 2
                        if n & 0x8000:
                            n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p)[0]
                            p += 2
                        strings.append(data[p:p + n * 2].decode("utf-16-le", "replace"))
            elif ctype == 0x0102:  # start element
                name_idx = struct.unpack_from("<I", data, pos + 20)[0]
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", data, pos + 24)
                if strings[name_idx] == "manifest":
                    a = pos + 16 + attr_start
                    for i in range(attr_count):
                        _ns, aname, raw, _sz, _r, dtype, dval = struct.unpack_from("<IIIHBBI", data, a + i * attr_size)
                        key = strings[aname] if aname < len(strings) else ""
                        if raw != 0xFFFFFFFF and raw < len(strings):
                            val = strings[raw]
                        elif dtype == 0x03 and dval < len(strings):
                            val = strings[dval]
                        else:
                            val = str(dval)
                        attrs[key] = val
                    return attrs
            pos += csize
    except (struct.error, IndexError):
        pass
    return {}


def _aapt():
    home = android_home()
    if not home:
        return None
    for d in sorted(glob.glob(os.path.join(home, "build-tools", "*")), reverse=True):
        for name in ("aapt2.exe", "aapt.exe", "aapt2", "aapt"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None


def _zip_contains(z, names_pred, mark):
    for info in z.infolist():
        if names_pred(info.filename) and info.file_size < 400 * 1024 * 1024:
            with z.open(info) as f:
                tail = b""
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    if mark in tail + chunk:
                        return True
                    tail = chunk[-len(mark):]
    return False


def inspect_apk(path):
    out = {"package": "", "version": "", "build": "", "flutter": False, "test_server": None, "build_mode": ""}
    tool = _aapt()
    if tool:
        code, txt = run([tool, "dump", "badging", path], timeout=60, shell=False)
        m = re.search(r"package: name='([^']*)' versionCode='([^']*)' versionName='([^']*)'", txt)
        if code == 0 and m:
            out.update(package=m.group(1), build=m.group(2), version=m.group(3))
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if not out["package"] and "AndroidManifest.xml" in names:
                attrs = _axml_manifest_attrs(z.read("AndroidManifest.xml"))
                out.update(package=attrs.get("package", ""), build=attrs.get("versionCode", ""),
                           version=attrs.get("versionName", ""))
            out["flutter"] = any(n.endswith("libflutter.so") for n in names) or \
                any(n.startswith("assets/flutter_assets/") for n in names)
            kernel = "assets/flutter_assets/kernel_blob.bin" in names
            out["build_mode"] = "debug" if kernel else ("release" if any(n.endswith("libapp.so") for n in names) else "")
            if out["flutter"]:
                out["test_server"] = _zip_contains(
                    z, lambda n: n.endswith(("kernel_blob.bin", "libapp.so")), TEST_SERVER_MARK)
    except zipfile.BadZipFile:
        out["error"] = "the file is not a valid APK"
    return out


def inspect_ipa(path):
    out = {"package": "", "version": "", "build": "", "flutter": False, "test_server": None, "build_mode": ""}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            plist = next((n for n in names if re.match(r"^Payload/[^/]+\.app/Info\.plist$", n)), None)
            if plist:
                info = plistlib.loads(z.read(plist))
                out.update(package=info.get("CFBundleIdentifier", ""), version=info.get("CFBundleShortVersionString", ""),
                           build=str(info.get("CFBundleVersion", "")))
            out["flutter"] = any("/Frameworks/Flutter.framework/" in n for n in names)
            out["build_mode"] = "release" if any(n.endswith("/App.framework/App") for n in names) else ""
            if out["flutter"]:
                out["test_server"] = _zip_contains(z, lambda n: n.endswith("/App.framework/App") or
                                                   n.endswith("kernel_blob.bin"), TEST_SERVER_MARK)
    except zipfile.BadZipFile:
        out["error"] = "the file is not a valid IPA"
    return out


def installed_android_app(package, serial):
    out = {"package": package, "installed": False, "version": "", "build": "", "sha256": "", "apk_paths": []}
    code, txt = adb(["shell", "pm", "path", package], serial, timeout=30)
    paths = [l.split(":", 1)[1].strip() for l in txt.splitlines() if l.startswith("package:")]
    if not paths:
        return out
    out["installed"] = True
    out["apk_paths"] = paths
    _, dump = adb(["shell", "dumpsys", "package", package], serial, timeout=30)
    m = re.search(r"versionName=(\S+)", dump)
    out["version"] = m.group(1) if m else ""
    m = re.search(r"versionCode=(\d+)", dump)
    out["build"] = m.group(1) if m else ""
    hashes = []
    for p in sorted(paths):
        _, h = adb(["shell", "sha256sum", p], serial, timeout=60)
        m = re.match(r"^([0-9a-f]{64})", h.strip())
        hashes.append(m.group(1) if m else "")
    if all(hashes):
        out["sha256"] = hashes[0] if len(hashes) == 1 else hashlib.sha256("".join(hashes).encode()).hexdigest()
    return out


def scan_installed_android(package, serial, paths):
    """Pull base.apk to a temp dir to check for the Flutter test server (installed app, no file in the plan)."""
    base = next((p for p in paths if p.endswith("base.apk")), paths[0] if paths else None)
    if not base:
        return {}
    tmp = tempfile.mkdtemp(prefix="apkscan-")
    try:
        dest = os.path.join(tmp, "base.apk")
        code, _ = adb(["pull", base, dest], serial, timeout=300)
        if code != 0 or not os.path.exists(dest):
            return {}
        info = inspect_apk(dest)
        libs = [p for p in paths if p != base]
        if info.get("flutter") and not info.get("test_server") and libs:  # split APKs: libapp.so may be in a split
            for i, p in enumerate(libs):
                d = os.path.join(tmp, f"split{i}.apk")
                if adb(["pull", p, d], serial, timeout=300)[0] == 0:
                    with zipfile.ZipFile(d) as z:
                        if _zip_contains(z, lambda n: n.endswith("libapp.so"), TEST_SERVER_MARK):
                            info["test_server"] = True
                            break
        return {k: info[k] for k in ("flutter", "test_server", "build_mode")}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def inspect_app(app, platform, serial=None, scan=True, root=None):
    """App build fingerprint. `app` is a file path (APK/IPA) or an installed package/bundle id."""
    out = {"given": app, "kind": None, "path": None, "exists": False, "package": "", "version": "", "build": "",
           "sha256": "", "flutter": None, "test_server": None, "build_mode": "", "installed": None}
    if not app:
        return out
    root = root or os.getcwd()
    cand = app if os.path.isabs(app) else os.path.join(root, app)
    looks_file = bool(re.search(r"\.(apk|aab|ipa|app|zip)$", app, re.I)) or os.sep in app or "/" in app
    if os.path.isfile(cand):
        out.update(kind="file", path=os.path.abspath(cand), exists=True, sha256=sha256_file(cand))
        ext = os.path.splitext(cand)[1].lower()
        info = inspect_apk(cand) if ext in (".apk", ".aab") else inspect_ipa(cand) if ext in (".ipa", ".zip") else {}
        if not scan:
            info.pop("test_server", None)
        out.update({k: v for k, v in info.items() if v not in (None, "") or k == "test_server"})
        if platform == "android" and serial and out.get("package"):
            out["installed"] = installed_android_app(out["package"], serial)["installed"]
        return out
    if looks_file:
        out.update(kind="file", path=os.path.abspath(cand), exists=False)
        return out
    out.update(kind="installed", package=app)
    if platform == "android" and serial:
        inst = installed_android_app(app, serial)
        out.update(installed=inst["installed"], version=inst["version"], build=inst["build"], sha256=inst["sha256"])
        if inst["installed"] and scan:
            out.update(scan_installed_android(app, serial, inst["apk_paths"]))
    return out


def app_fingerprint(info):
    """The value compared between runs: the file hash, else the installed APK hash, else version+build."""
    if info.get("sha256"):
        return info["sha256"]
    if info.get("version") or info.get("build"):
        return hashlib.sha256(f"{info.get('package')}|{info.get('version')}|{info.get('build')}".encode()).hexdigest()
    return ""


# ---------------------------------------------------------------- appium

def appium_drivers():
    exe = which("appium")
    if not exe:
        return None
    code, out = run(f'"{exe}" driver list --installed --json', timeout=120, shell=True)
    try:
        data = json.loads(out[out.index("{"):])
        return {k: v.get("version", "") for k, v in data.items()}
    except (ValueError, AttributeError):
        names = {}
        for m in re.finditer(r"([\w-]+)@([\d.]+)\s*\[installed", re.sub(r"\x1b\[[0-9;]*m", "", out)):
            names[m.group(1)] = m.group(2)
        return names


def server_status(url):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/status", timeout=5) as r:
            data = json.loads(r.read() or b"{}")
            return True, (data.get("value") or {}).get("build", {}).get("version", "")
    except Exception as e:  # noqa: BLE001 - any failure means "not running"
        return False, str(getattr(e, "reason", e))


def start_server(url, log_path):
    exe = which("appium")
    if not exe:
        return False, "Appium is not installed"
    from urllib.parse import urlparse
    u = urlparse(url)
    args = [exe, "--address", u.hostname or "127.0.0.1", "--port", str(u.port or 4723),
            "--allow-insecure", "*:adb_shell", "--log-timestamp", "--log-no-colors"]
    if u.path and u.path != "/":
        args += ["--base-path", u.path]
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    logf = open(log_path, "a", encoding="utf-8")
    kw = {"stdout": logf, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS
        args = ["cmd", "/c"] + args
    else:
        kw["start_new_session"] = True
    subprocess.Popen(args, **kw)
    for _ in range(60):
        ok, ver = server_status(url)
        if ok:
            return True, ver
        time.sleep(1)
    return False, f"the server did not answer within 60 seconds (log: {log_path})"


# ---------------------------------------------------------------- main

def version_tuple(text):
    m = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else (0, 0, 0)


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--platform", choices=["android", "ios"], required=True)
    ap.add_argument("--app")
    ap.add_argument("--device")
    ap.add_argument("--appium-url", default=os.environ.get("APPIUM_URL", "http://127.0.0.1:4723"))
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--start-server", action="store_true")
    ap.add_argument("--server-log", default=os.path.join(tempfile.gettempdir(), "appium-server.log"))
    ap.add_argument("--skip-app-scan", action="store_true")
    a = ap.parse_args()

    checks, missing, installed = [], [], []

    def add(name, ok, required=True, detail="", fix=""):
        checks.append({"name": name, "ok": bool(ok), "required": required, "detail": detail, "fix": fix})
        if not ok and required:
            missing.append(f"{name}: {fix}" if fix else name)

    # Node / npm / Java
    code, out = run("node -v", shell=True)
    nv = version_tuple(out) if code == 0 else (0, 0, 0)
    add("Node.js 22+", code == 0 and nv[0] >= 22, detail=out.strip(),
        fix="install Node.js 22 or newer from https://nodejs.org (npm comes with it)")
    code, out = run("npm -v", shell=True)
    add("npm", code == 0, detail=out.strip(), fix="install Node.js 22+, which includes npm")
    code, out = run("java -version", shell=True)
    jv = version_tuple(out.split("version", 1)[-1]) if code == 0 else (0, 0, 0)
    java_ok = code == 0 and (jv[0] >= 8 or (jv[0] == 1 and jv[1] >= 8))
    add("Java 8+", java_ok, detail=out.strip().splitlines()[0] if out.strip() else "",
        fix="install a JDK (8 or newer) and make sure `java` is on PATH")

    # platform toolchain
    if a.platform == "android":
        home = android_home()
        add("Android SDK (ANDROID_HOME)", bool(home), detail=home or "",
            fix="install Android Studio / the Android SDK and set ANDROID_HOME to the SDK folder")
        add("adb", bool(adb_path()), detail=adb_path() or "",
            fix="install the Android SDK platform-tools and add <ANDROID_HOME>/platform-tools to PATH")
    else:
        is_mac = pyplatform.system() == "Darwin"
        add("macOS (needed for iOS)", is_mac, detail=pyplatform.system(),
            fix="iOS testing needs a Mac with Xcode; run the iOS suite on a Mac")
        if is_mac:
            code, out = run(["xcodebuild", "-version"], shell=False)
            add("Xcode", code == 0, detail=out.strip().splitlines()[0] if out.strip() else "",
                fix="install Xcode from the App Store and run `sudo xcode-select -s /Applications/Xcode.app`")

    # Appium + drivers
    appium = which("appium")
    if not appium and a.install:
        code, out = run("npm install -g appium", timeout=600, shell=True)
        appium = which("appium")
        if appium:
            installed.append("appium (npm -g)")
    ver = run(f'"{appium}" --version', shell=True)[1].strip() if appium else ""
    add("Appium server", bool(appium), detail=ver, fix="install it with `npm install -g appium`")
    drivers = appium_drivers() if appium else {}
    need = [("uiautomator2", "appium driver install uiautomator2")] if a.platform == "android" else \
        [("xcuitest", "appium driver install xcuitest")]
    need.append(("flutter-integration", f"appium driver install --source npm {FLUTTER_DRIVER}"))
    for name, cmd in need:
        have = drivers is not None and any(k == name or k.startswith(name) for k in drivers)
        if not have and a.install and appium:
            run(cmd.replace("appium", f'"{appium}"', 1), timeout=900, shell=True)
            drivers = appium_drivers() or {}
            have = any(k == name or k.startswith(name) for k in drivers)
            if have:
                installed.append(f"Appium driver {name}")
        add(f"Appium driver {name}", have, detail=(drivers or {}).get(name, ""), fix=f"run `{cmd}`")

    # server
    up, sver = server_status(a.appium_url)
    if not up and a.start_server and appium:
        up, sver = start_server(a.appium_url, a.server_log)
        if up:
            installed.append(f"Appium server started at {a.appium_url} (log: {a.server_log})")
    add("Appium server running", up, required=a.start_server, detail=sver if up else "",
        fix=f"start it with `appium --allow-insecure \"*:adb_shell\"` (expected at {a.appium_url})")

    # devices
    devices, emus, not_ready, device, note = [], [], [], None, None
    if a.platform == "android" and adb_path():
        devices, emus, not_ready = real_android_devices()
    elif a.platform == "ios":
        devices, emus = ios_real_devices()
    if devices:
        device, note = pick_device(devices, a.device)
        if a.platform == "android":
            device.update(android_device_details(device["serial"]))
        add("Real device connected", True, detail=note)
        if device.get("awake") is False or device.get("locked"):
            add("Device awake and unlocked", False, required=False,
                detail="the screen is off or locked",
                fix="unlock the phone and keep it awake during the run (the skill does not change device settings)")
        else:
            add("Device awake and unlocked", True, required=False,
                detail="keep the phone unlocked and awake during the run")
    else:
        reason = REAL_DEVICE_MSG
        if emus and not not_ready:
            reason = f"Only an emulator or simulator is connected ({', '.join(e['serial'] for e in emus)}). {REAL_DEVICE_MSG}"
        elif not_ready:
            reason = "; ".join(f"{d['serial']}: {d['problem']}" for d in not_ready) + f". {REAL_DEVICE_MSG}"
        add("Real device connected", False, detail=reason, fix=reason)

    # ffmpeg (optional)
    add("ffmpeg (optional, shrinks recordings for Jira)", bool(which("ffmpeg")), required=False,
        fix="optional: install ffmpeg to shrink large screen recordings before they go to Jira")

    # app
    app = None
    if a.app:
        app = inspect_app(a.app, a.platform, device["serial"] if device else None, scan=not a.skip_app_scan)
        app["fingerprint"] = app_fingerprint(app)
        if app["kind"] == "file" and not app["exists"]:
            add("App file", False, detail=app["path"], fix=f"the app file in the test plan does not exist: {app['path']}")
        elif app["kind"] == "installed" and app.get("installed") is False:
            add("App installed", False, detail=app["package"],
                fix=f"the app {app['package']} is not installed on the device; install the test build or give its "
                    "APK/IPA path in the test plan")
        else:
            add("App", True, detail=f"{app.get('package')} {app.get('version')} (build {app.get('build')})".strip())
        if app.get("flutter") is False:
            add("Flutter app", False, required=False, detail="no Flutter engine found in the app",
                fix="the app does not look like a Flutter app; only the native fallback can be used")
        if app.get("test_server") is False:
            hint = ("a debug test build (`./gradlew app:assembleDebug -Ptarget=<project>/integration_test/appium_test.dart`)"
                    if a.platform == "android" else
                    "a release test build (`flutter build ipa --release integration_test/appium_test.dart`)")
            add("Flutter test build (appium_flutter_server)", False, required=False,
                detail="the build does not contain appium_flutter_server",
                fix=f"ask the team for {hint} with appium_flutter_server in pubspec.yaml and "
                    "integration_test/appium_test.dart; without it only the native fallback (Semantics labels) is "
                    "possible, with limited coverage")
        elif app.get("test_server"):
            add("Flutter test build (appium_flutter_server)", True, required=False,
                detail=f"{app.get('build_mode') or 'unknown'} build")
            if a.platform == "ios" and app.get("build_mode") == "debug":
                add("iOS release test build", False, required=False,
                    fix="a real iPhone needs a RELEASE test build (`flutter build ipa --release "
                        "integration_test/appium_test.dart`)")

    out = {"ok": not missing, "platform": a.platform, "checks": checks, "missing": missing, "installed": installed,
           "devices": devices, "emulators_ignored": emus, "not_ready": not_ready, "device": device,
           "device_note": note, "app": app, "server": {"url": a.appium_url, "running": up, "version": sver if up else ""}}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    print()
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
