#!/usr/bin/env python3
"""Parse and validate build-mobile-test-cases arguments and print a JSON summary.

Usage:
  python parse_args.py <raw $ARGUMENTS string>          (one quoted string)
  python parse_args.py --project-dir D --test-plan F [--xlsx] [--force-full]

Options for this script itself (not part of the user command):
  --root <dir>   project root where Test Cases/ and Exploration/ live (default: cwd)
  --no-create    do not create Test Cases/ and Exploration/

Exit codes: 0 ok, 2 usage/validation error (usage line printed to stderr).
"""
import json
import os
import re
import shlex
import sys

USAGE = "Usage: /build-mobile-test-cases --project-dir <dir> --test-plan <file> [--xlsx] [--force-full]"


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "plan"


def split_raw(raw):
    """Split a raw argument string; quotes group words, backslashes stay literal (Windows paths)."""
    lex = shlex.shlex(raw, posix=True)
    lex.whitespace_split = True
    lex.escape = ""
    lex.commenters = ""
    return list(lex)


def fail(msg):
    print(json.dumps({"ok": False, "error": msg, "usage": USAGE}))
    print(f"Error: {msg}\n{USAGE}", file=sys.stderr)
    sys.exit(2)


def parse(argv):
    if len(argv) == 1:
        argv = split_raw(argv[0])
    opts = {"project_dir": None, "test_plan": None, "xlsx": False, "force_full": False,
            "root": os.getcwd(), "create": True}
    i = 0
    while i < len(argv):
        tok = argv[i]
        key, val = (tok.split("=", 1) + [None])[:2] if tok.startswith("--") and "=" in tok else (tok, None)
        if key in ("--project-dir", "--test-plan", "--root"):
            if val is None:
                i += 1
                if i >= len(argv) or argv[i].startswith("--"):
                    fail(f"{key} needs a value")
                val = argv[i]
            opts[key[2:].replace("-", "_")] = val
        elif key == "--xlsx":
            opts["xlsx"] = True
        elif key == "--force-full":
            opts["force_full"] = True
        elif key == "--no-create":
            opts["create"] = False
        elif key in ("-h", "--help"):
            print(USAGE)
            sys.exit(0)
        else:
            fail(f"unknown argument: {tok}")
        i += 1
    return opts


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    opts = parse(sys.argv[1:])
    missing = [n for n, k in (("--project-dir", "project_dir"), ("--test-plan", "test_plan")) if not opts[k]]
    if missing:
        fail("missing required argument(s): " + ", ".join(missing))

    root = os.path.abspath(opts["root"])
    pdir = os.path.abspath(os.path.join(root, opts["project_dir"]))
    plan = os.path.abspath(os.path.join(root, opts["test_plan"]))
    if not os.path.isdir(pdir):
        fail(f"--project-dir does not exist or is not a folder: {pdir}")
    docs = [os.path.join(dp, f) for dp, _, fs in os.walk(pdir) for f in fs if not f.startswith(("~$", "."))]
    if not docs:
        fail(f"--project-dir is empty: {pdir}")
    if not os.path.isfile(plan):
        fail(f"--test-plan file does not exist: {plan}")

    plan_key = slugify(os.path.splitext(os.path.basename(plan))[0])
    tc_dir = os.path.join(root, "Test Cases")
    ex_root = os.path.join(root, "Exploration")
    plan_dir = os.path.join(ex_root, plan_key)
    manifest = os.path.join(plan_dir, "manifest.json")
    has_manifest = os.path.isfile(manifest)

    if opts["force_full"]:
        mode = "force-full"
    elif not has_manifest:
        mode = "first"
    else:
        mode = "rerun"

    created = []
    if opts["create"]:
        for d in (tc_dir, ex_root):
            if not os.path.isdir(d):
                os.makedirs(d)
                created.append(d)

    out = {
        "ok": True,
        "root": root,
        "project_dir": pdir,
        "project_docs": sorted(os.path.relpath(d, pdir).replace("\\", "/") for d in docs),
        "test_plan": plan,
        "xlsx": opts["xlsx"],
        "force_full": opts["force_full"],
        "plan_key": plan_key,
        "test_cases_dir": tc_dir,
        "exploration_root": ex_root,
        "plan_exploration_dir": plan_dir,
        "manifest": manifest,
        "manifest_exists": has_manifest,
        "mode": mode,
        "created_dirs": created,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
