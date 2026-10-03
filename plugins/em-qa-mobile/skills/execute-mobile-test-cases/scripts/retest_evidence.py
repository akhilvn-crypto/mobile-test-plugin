#!/usr/bin/env python3
"""Retest evidence for bugs filed in Jira (Phase 4 and Phase 5a). Only bugs in bugs/jira-sync.json count.

  python retest_evidence.py ids [--to-run "<cases.json>"]
      -> {"ids": [...], "grep": "TC-A|TC-B", "bugs": {BUG-003: [TC-…]}}
         Case IDs linked to a bug with Jira status filed / close_pending. With --to-run (parse_testcases.py
         output), only the IDs that run in this cycle. Run those first with RETEST_EVIDENCE=1 (from mobile-automation/):
           RETEST_EVIDENCE=1 npx wdio run wdio.<platform>.conf.ts --spec "<suite_dir>/*.spec.ts" --mochaOpts.grep "<grep>"
           npx wdio run wdio.<platform>.conf.ts --spec "<suite_dir>/*.spec.ts" --mochaOpts.grep "<grep>" --mochaOpts.invert

  python retest_evidence.py collect --results "<results_dir>/results.json" [--since <ISO time of the run start>]
      Checks the local closing conditions for every filed bug and copies the evidence of bugs that pass them to
      bugs/<bug>/retest/BUG-003_retest_<dd-mm-yyyy>.png / .mp4 (BUG-003_retest_<TC-ID>_<date>.* when the bug has
      several cases). Prints {"candidates": [...], "stay_open": [...]} for file-bugs-to-jira (closing-fixed-bugs.md).

Local closing conditions (the Jira status is checked later by file-bugs-to-jira):
  1. the bug is in jira-sync.json with status filed or close_pending;
  2. every test case linked to the bug passed in this run (ended after --since when given);
  3. each passed on its first attempt (not flaky, not on the automatic retry) and kept retest evidence.
"""
import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import dump, find_root, ist_date, load_json, rel, utf8_stdio  # noqa: E402
import bug_index  # noqa: E402

OPEN_JIRA = {"filed", "close_pending"}


def filed_bugs(bugs_dir, sync_path):
    sync = (load_json(sync_path, {}) or {}).get("bugs") or {}
    _, _, rows = bug_index.load(os.path.join(bugs_dir, "bug-index.md"))
    index = {c[0].strip(): bug_index.row_dict(c) for _, c in rows if c}
    out = {}
    for bid, e in sync.items():
        if (e or {}).get("status") not in OPEN_JIRA:
            continue
        row = index.get(bid) or {}
        tcs = row.get("Test case(s)", "")
        bf = bug_index.bug_file(bugs_dir, bid, row)
        if bf and not tcs:
            with open(bf, encoding="utf-8") as f:
                m = re.search(r"^\|\s*Test case\(s\)\s*\|\s*(.*?)\s*\|\s*$", f.read(), re.M)
            tcs = m.group(1) if m else ""
        out[bid] = {"jiraKey": e.get("jiraKey"), "cases": re.findall(r"TC-[A-Z0-9]+-[A-Z]+-\d+", tcs),
                    "bug_file": bf}
    return out


def cmd_ids(a):
    bugs = filed_bugs(a.bugs_dir, a.sync)
    to_run = None
    if a.to_run:
        data = load_json(a.to_run, {}) or {}
        to_run = set(data.get("to_run_ids") or [])
        for f in data.get("flows") or []:
            to_run.update(f.get("to_run_ids") or [])
            to_run.update(c["id"] for c in f.get("cases") or [] if c.get("run"))
    ids = []
    for b in bugs.values():
        for c in b["cases"]:
            if (to_run is None or c in to_run) and c not in ids:
                ids.append(c)
    dump({"ids": ids, "grep": "|".join(ids), "bugs": {k: v["cases"] for k, v in bugs.items()}})


def cmd_collect(a):
    root = find_root()
    results_dir = os.path.dirname(os.path.abspath(a.results))
    results = {e["id"]: e for e in (load_json(a.results, {}) or {}).get("results", [])}
    date = ist_date()
    candidates, stay = [], []
    for bid, b in filed_bugs(a.bugs_dir, a.sync).items():
        why = []
        if not b["cases"]:
            why.append("no test case is linked to the bug")
        for cid in b["cases"]:
            e = results.get(cid)
            if not e:
                why.append(f"{cid} was not run in this cycle")
            elif a.since and (e.get("endedAt") or "") < a.since:
                why.append(f"{cid} was not run in this cycle")
            elif e.get("status") != "passed":
                why.append(f"{cid} did not pass ({e.get('status')})")
            elif e.get("flaky") or int(e.get("attempts") or 1) > 1:
                why.append(f"{cid} passed only on the second attempt")
            elif not e.get("retestEvidence"):
                why.append(f"{cid} passed but kept no retest evidence (run it with RETEST_EVIDENCE=1)")
            elif e.get("status") == "manual":
                why.append(f"{cid} needs a manual check")
        if why:
            stay.append({"bug": bid, "jiraKey": b["jiraKey"], "cases": b["cases"], "reasons": why})
            continue
        folder = os.path.dirname(b["bug_file"]) if b["bug_file"] else None
        if not folder:
            stay.append({"bug": bid, "jiraKey": b["jiraKey"], "cases": b["cases"], "reasons": ["bug folder not found"]})
            continue
        retest_dir = os.path.join(folder, "retest")
        os.makedirs(retest_dir, exist_ok=True)
        files = []
        for cid in b["cases"]:
            tag = f"_{cid}" if len(b["cases"]) > 1 else ""
            for src in results[cid]["retestEvidence"]:
                src_abs = os.path.join(root, src)
                if not os.path.exists(src_abs):  # mobile: paths are relative to mobile-automation/
                    src_abs = os.path.join(os.path.dirname(os.path.dirname(results_dir)), src)
                if not os.path.exists(src_abs):
                    continue
                ext = os.path.splitext(src_abs)[1].lower()
                dst = os.path.join(retest_dir, f"{bid}_retest{tag}_{date}{ext}")
                shutil.copyfile(src_abs, dst)
                files.append(rel(dst, root))
        if not any(f.endswith((".png", ".jpg", ".jpeg")) for f in files):
            stay.append({"bug": bid, "jiraKey": b["jiraKey"], "cases": b["cases"],
                         "reasons": ["the retest screenshot is missing"]})
            continue
        candidates.append({"bug": bid, "jiraKey": b["jiraKey"], "cases": b["cases"],
                           "ended_ist": max(results[c].get("endedAtIst", "") for c in b["cases"]),
                           "retest_files": files})
    dump({"ok": True, "candidates": candidates, "stay_open": stay})


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bugs-dir", default="bugs")
    ap.add_argument("--sync", default="bugs/jira-sync.json")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("ids")
    p.add_argument("--to-run")
    p.set_defaults(fn=cmd_ids)
    p = sp.add_parser("collect")
    p.add_argument("--results", required=True)
    p.add_argument("--since")
    p.set_defaults(fn=cmd_collect)
    a = ap.parse_args()
    if not os.path.exists(a.sync):
        dump({"ok": True, "ids": [], "grep": "", "bugs": {}, "candidates": [], "stay_open": [],
              "note": "No bugs/jira-sync.json: no bug has been filed in Jira"})
        return
    a.fn(a)


if __name__ == "__main__":
    main()
