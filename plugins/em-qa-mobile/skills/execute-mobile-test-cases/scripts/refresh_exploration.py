#!/usr/bin/env python3
"""Refresh the stored knowledge of ONE screen after a script failed against outdated exploration (Phase 4).

  python refresh_exploration.py --plan-dir "Exploration/<plan-key>" --platform android|ios --flow <flow-key>
                                --screen <screen-name> --new-json <fresh screen.json> --reason "<what changed>"
                                [--screenshot <fresh.png>] [--run-ts <YYYY-MM-DD_HH-MM-SS-IST>]

- The old `<platform>/<flow>/screens/<screen>.json` (and the old refreshed screenshot) move to
  `<platform>/<flow>/history/<ts>/` - nothing is deleted.
- The new JSON is written with `"updated_by": "execute-mobile-test-cases"`, a fresh `captured_ist` and its
  structure `fingerprint`.
- The manifest screen entry of that platform gets the new fingerprint and `last_captured_ist` (same fingerprint
  rules as build-mobile-test-cases, so its light check treats the screen as a valid capture).
- A line is added to `Exploration/<plan-key>/runs/<ts>/changes.md`.
"""
import argparse
import importlib.util
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import dump, ist_cell, ist_file, load_json, utf8_stdio, write_json_atomic, write_text_atomic  # noqa: E402

BUILD_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "build-mobile-test-cases", "scripts")


def fingerprint(structure):
    """The fingerprint of build-mobile-test-cases/scripts/snapshot_diff.py (one algorithm for both skills)."""
    path = os.path.join(BUILD_SCRIPTS, "snapshot_diff.py")
    if BUILD_SCRIPTS not in sys.path:
        sys.path.append(BUILD_SCRIPTS)
    spec = importlib.util.spec_from_file_location("mobile_snapshot_diff", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.fingerprint(structure)


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan-dir", required=True)
    ap.add_argument("--platform", required=True, choices=["android", "ios"])
    ap.add_argument("--flow", required=True)
    ap.add_argument("--screen", required=True)
    ap.add_argument("--new-json", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--screenshot")
    ap.add_argument("--run-ts")
    a = ap.parse_args()
    flow_dir = os.path.join(a.plan_dir, a.platform, a.flow)
    sc_dir = os.path.join(flow_dir, "screens")
    if not os.path.isdir(flow_dir):
        dump({"ok": False, "error": f"Flow folder not found: {flow_dir}"}, code=2)
    new = load_json(a.new_json)
    if not isinstance(new, dict):
        dump({"ok": False, "error": "--new-json must hold one screen object"}, code=2)
    ts = a.run_ts or ist_file()
    now = ist_cell()
    hist = os.path.join(flow_dir, "history", ts)
    old_path = os.path.join(sc_dir, f"{a.screen}.json")
    old = load_json(old_path, {}) or {}
    archived = []
    if os.path.exists(old_path):
        os.makedirs(os.path.join(hist, "screens"), exist_ok=True)
        dst = os.path.join(hist, "screens", f"{a.screen}.json")
        shutil.move(old_path, dst)
        archived.append(dst)
    if a.screenshot:
        shots = os.path.join(flow_dir, "screenshots")
        os.makedirs(shots, exist_ok=True)
        target = os.path.join(shots, f"{a.screen}__refreshed.png")
        if os.path.exists(target):
            os.makedirs(os.path.join(hist, "screenshots"), exist_ok=True)
            dst = os.path.join(hist, "screenshots", os.path.basename(target))
            shutil.move(target, dst)
            archived.append(dst)
        shutil.copyfile(a.screenshot, target)
    new.setdefault("reached_by", old.get("reached_by", ""))
    new["screen"] = a.screen
    new["platform"] = a.platform
    new["captured_ist"] = now
    new["updated_by"] = "execute-mobile-test-cases"
    fp = fingerprint(new)
    new["fingerprint"] = fp
    os.makedirs(sc_dir, exist_ok=True)
    write_json_atomic(old_path, new)
    # manifest (platform part)
    mpath = os.path.join(a.plan_dir, "manifest.json")
    manifest = load_json(mpath, {}) or {}
    part = (manifest.get("platforms") or {}).get(a.platform)
    flow = (part or {}).get("flows", {}).get(a.flow)
    updated = False
    if flow is not None:
        for s in flow.setdefault("screens", []):
            if s.get("screen") == a.screen:
                s.update({"fingerprint": fp, "last_captured_ist": now, "updated_by": "execute-mobile-test-cases"})
                updated = True
                break
        if not updated:
            flow["screens"].append({"screen": a.screen, "reached_by": new.get("reached_by", ""), "fingerprint": fp,
                                    "last_captured_ist": now, "updated_by": "execute-mobile-test-cases"})
            updated = True
        write_json_atomic(mpath, manifest)
    # changes.md
    ch = os.path.join(a.plan_dir, "runs", ts, "changes.md")
    text = ""
    if os.path.exists(ch):
        with open(ch, encoding="utf-8") as f:
            text = f.read()
    if "## Screens refreshed by execute-mobile-test-cases" not in text:
        text = (text.rstrip() + "\n\n" if text.strip() else f"# Changes – {ts}\n\n") + \
               "## Screens refreshed by execute-mobile-test-cases\n"
    text = text.rstrip("\n") + f"\n- {now} – {a.platform}/{a.flow}/{a.screen}: {a.reason}\n"
    write_text_atomic(ch, text)
    dump({"ok": True, "screen_json": old_path, "archived": archived, "fingerprint": fp,
          "manifest_updated": updated, "changes": ch})


if __name__ == "__main__":
    main()
