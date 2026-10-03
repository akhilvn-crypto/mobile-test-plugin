#!/usr/bin/env python3
"""Resolve the execute-mobile-test-cases arguments (Phase 0).

  python find_testcase.py '<raw arguments text>'

Pass the user's argument text unchanged as ONE single-quoted string, e.g.
  python find_testcase.py '--testcase "Demo App Plan_Android_2026-10-03_10-44-55-IST" --test-report xlsx'

- `--testcase` (required): a file in `Test Cases/` (with or without `.md`, case-insensitive,
  any dash style) or a path. A `.xlsx` argument is mapped to its `.md`.
- `--test-report` (optional): only `xlsx` (any case) is accepted.

Prints JSON: md, xlsx (same base name, or null), platform, plan name/key, manifest, exploration folder of the
platform, test plan path, app (file, id, hash, version, build from the manifest), device, test_report_xlsx,
framework state (mobile-automation/), suite name (<Plan>_<Platform>), today's suite folder
(mobile-automation/tests/<Suite>_<date>) and the latest earlier suite folder of the same plan and platform. Exit 2 on a usage error or when the file is not found (the JSON lists the
available test case files).
"""
import glob
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (FRAMEWORK_DIR, PLATFORM_NAMES, dump, find_manifest, find_root, iso_date, load_json,  # noqa: E402
                     parse_testcase_md, platform_of, platform_part, rel, utf8_stdio)

USAGE = 'Usage: /execute-mobile-test-cases --testcase "<file name>" [--test-report xlsx]'


def split_raw(raw):
    lex = shlex.shlex(raw, posix=True)
    lex.whitespace_split = True
    lex.escape = ""  # keep Windows backslashes literal
    lex.quotes = '"\''
    return list(lex)


def usage_error(msg, **extra):
    dump({"ok": False, "error": msg, "usage": USAGE, **extra}, code=2)


def parse_args(tokens):
    out = {"testcase": None, "test_report": None}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        name, eq, val = t.partition("=")
        if name in ("--testcase", "--test-report"):
            if not eq:
                if i + 1 >= len(tokens) or tokens[i + 1].startswith("--"):
                    usage_error(f"{name} needs a value")
                val = tokens[i + 1]
                i += 1
            key = name[2:].replace("-", "_")
            if out[key] is not None:
                usage_error(f"{name} given twice")
            out[key] = val
        else:
            usage_error(f"Unknown argument: {t}")
        i += 1
    if not out["testcase"]:
        usage_error("--testcase is required")
    if out["test_report"] is not None and out["test_report"].strip().lower() != "xlsx":
        usage_error(f"--test-report only accepts 'xlsx' (got '{out['test_report']}')")
    return out


def norm_name(s):
    s = os.path.splitext(os.path.basename(s))[0] if s.lower().endswith((".md", ".xlsx")) else os.path.basename(s)
    s = re.sub(r"[–—‐-]", "-", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def resolve(arg, root):
    tc_dir = os.path.join(root, "Test Cases")
    available = sorted(os.path.basename(p) for p in glob.glob(os.path.join(tc_dir, "*.md")))
    cand = arg.strip().strip('"')
    if cand.lower().endswith(".xlsx"):
        cand = cand[:-5] + ".md"
    # 1. a path (absolute or relative to the root)
    for p in (cand, cand + ".md"):
        full = p if os.path.isabs(p) else os.path.join(root, p)
        if os.path.isfile(full) and full.lower().endswith(".md"):
            return os.path.abspath(full), available
    # 2. a name inside Test Cases/
    target = norm_name(cand)
    hits = [a for a in available if norm_name(a) == target]
    if not hits:
        # plan name without the timestamp: take the newest file of that plan (names end in a sortable timestamp)
        pref = [a for a in available if norm_name(a).startswith(target)
                and re.fullmatch(r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-ist", norm_name(a)[len(target):])]
        if pref:
            return os.path.join(tc_dir, sorted(pref)[-1]), available
        hits = [a for a in available if norm_name(a).startswith(target)]
    if len(hits) == 1:
        return os.path.join(tc_dir, hits[0]), available
    if len(hits) > 1:
        usage_error(f"'{arg}' matches more than one test case file; give the full name",
                    matches=hits, available=available)
    usage_error(f"Test case file not found: {arg}", available=available,
                searched=rel(tc_dir, root))


def suite_name(plan_name):
    s = re.sub(r"\s*[–—‐-]\s*", "-", plan_name.strip())
    return re.sub(r"[^A-Za-z0-9-]+", "_", s).strip("_-") or "Suite"


def main():
    utf8_stdio()
    if len(sys.argv) != 2:
        usage_error("Pass the arguments text as one quoted string")
    args = parse_args(split_raw(sys.argv[1]))
    root = find_root()
    md, _ = resolve(args["testcase"], root)
    xlsx = os.path.splitext(md)[0] + ".xlsx"
    doc = parse_testcase_md(md)
    platform = platform_of(doc, md)
    if not platform:
        usage_error("The test case file names no platform (header row 'Platform' must be Android or iOS); "
                    "it does not look like a build-mobile-test-cases file")
    plan_name = (doc["header"].get("Plan name") or (doc["h1"] or "").split(" – Test Cases")[0]).strip()
    plan_key, manifest_path = find_manifest(root, md, doc)
    manifest = load_json(manifest_path, {}) if manifest_path else {}
    part = platform_part(manifest, platform)
    plan_path = manifest.get("test_plan_path") or manifest.get("plan_file")
    suite = f"{suite_name(plan_name)}_{PLATFORM_NAMES[platform]}"
    today = f"{suite}_{iso_date()}"
    fw = os.path.join(root, FRAMEWORK_DIR)
    earlier = sorted(d for d in glob.glob(os.path.join(fw, "tests", f"{suite}_*"))
                     if os.path.isdir(d) and os.path.basename(d) != today
                     and re.fullmatch(re.escape(suite) + r"_\d{4}-\d{2}-\d{2}", os.path.basename(d)))
    flows = []
    for f in doc["flows"]:
        mf = (part.get("flows") or {}).get(f["key"], {})
        flows.append({"key": f["key"], "name": f["name"], "cases": len(f["cases"]),
                      "user_story_ref": f["user_story_ref"] or mf.get("user_story_ref", ""),
                      "user_story_title": f["user_story_title"] or mf.get("user_story_title", ""),
                      "status": mf.get("status", "active"),
                      "screens": [s.get("screen") for s in mf.get("screens", [])]})
    exploration_dir = os.path.dirname(manifest_path) if manifest_path else None
    dump({
        "ok": True,
        "md": rel(md, root),
        "xlsx": rel(xlsx, root) if os.path.exists(xlsx) else None,
        "test_report_xlsx": args["test_report"] is not None,
        "platform": platform,
        "plan_name": plan_name,
        "plan_key": plan_key,
        "plan_key_source": "header" if doc["header"].get("Plan key") else ("manifest" if manifest_path else None),
        "manifest": rel(manifest_path, root) if manifest_path else None,
        "exploration_dir": rel(exploration_dir, root) if exploration_dir else None,
        "platform_dir": rel(os.path.join(exploration_dir, platform), root) if exploration_dir else None,
        "has_platform_exploration": bool(part.get("flows")),
        "test_plan_path": plan_path,
        "test_plan_exists": bool(plan_path and os.path.exists(os.path.join(root, plan_path))),
        "project": doc["header"].get("Project", ""),
        "device": doc["header"].get("Device", "") or part.get("device", ""),
        "os_version": doc["header"].get("OS version", "") or part.get("os_version", ""),
        "app": {"file_path": part.get("app_file_path"), "app_id": part.get("app_id", ""),
                "hash": part.get("app_hash", ""), "version": part.get("app_version", ""),
                "build": part.get("app_build", ""), "header": doc["header"].get("App version and build", ""),
                "flutter_layer": part.get("flutter_layer")},
        "run_mode": doc["header"].get("Run mode", ""),
        "version": doc["front_matter"].get("version", ""),
        "flows": flows,
        "framework_dir": FRAMEWORK_DIR,
        "framework_exists": os.path.exists(os.path.join(fw, "package.json"))
                            and os.path.exists(os.path.join(fw, f"wdio.{platform}.conf.ts")),
        "node_modules": os.path.isdir(os.path.join(fw, "node_modules", "@wdio", "cli")),
        "wdio_config": f"wdio.{platform}.conf.ts",
        "suite": suite,
        "suite_dir": f"{FRAMEWORK_DIR}/tests/{today}",
        "suite_dir_exists": os.path.isdir(os.path.join(fw, "tests", today)),
        "results_dir": f"{FRAMEWORK_DIR}/test-results/{today}",
        "previous_suite_dir": rel(earlier[-1], root) if earlier else None,
    })


if __name__ == "__main__":
    main()
