#!/usr/bin/env python3
"""Phase 0: read every bug report under bugs/, compare with bugs/jira-sync.json and say what to do.

  python list_bugs.py [--bug-id BUG-003|3] [--link-story PROJ-123] [--out "<scratchpad>/bugs.json"]

Prints (and writes to --out with the full bug data):
  {"ok": true,
   "to_file":        [bug ...],   # Status Open and not in jira-sync.json (and, with --bug-id, only that bug)
   "story_link_only":[bug ...],   # already filed, --link-story given and that story is not linked yet
   "already_filed":  [{id, title, jiraKey, url, status}],
   "skipped":        [{id, title, reason}],
   "close_pending":  [{id, jiraKey, note}],   # closings left unfinished by an earlier test run (finish first)
   "cross_platform": [{id, platform, candidates: [{id, jiraKey, platform, title}]}],  # same problem already filed
                                                  # for the other platform: show as "possible duplicate: PROJ-45 (iOS)"
   "problems":       [...],       # e.g. a test case file that cannot be found
   "available":      ["BUG-001 - <title>", ...]}
Exit 2 with {"error", "available"} when --bug-id names no bug; exit 2 with {"error"} for a malformed --link-story.

Each bug: id, title, severity, priority, status, test_cases, test_case_file (+ testcase_md, how_found), plan_key,
summary, description, steps, expected, actual, environment, insights, evidence_files, file, folder.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fbj import (BUGS_DIR, PLATFORMS, STORY_KEY_RE, SYNC_FILE, bug_dirs, dump, find_root, load_json,  # noqa: E402
                  norm_bug_id, parse_bug, plan_key_for, rel, resolve_testcase_file, same_problem, utf8_stdio,
                  write_json_atomic)

SKIP_STATUSES = {"fixed - verified", "closed", "closed in jira", "rejected"}


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bug-id")
    ap.add_argument("--link-story")
    ap.add_argument("--bugs-dir", default=BUGS_DIR)
    ap.add_argument("--sync", default=SYNC_FILE)
    ap.add_argument("--out")
    a = ap.parse_args()
    root = find_root()

    story = (a.link_story or "").strip()
    if a.link_story is not None and not STORY_KEY_RE.match(story):
        dump({"ok": False, "error": f"'{a.link_story}' does not look like a Jira key (for example PROJ-123)."
                                    " Ask the user for the right story key; do not guess."}, code=2)

    files = bug_dirs(a.bugs_dir)
    bugs = {bid: parse_bug(p) for bid, p in files.items()}
    available = [f"{b['id']} - {b['title']}" for b in bugs.values()]
    if not bugs:
        dump({"ok": True, "to_file": [], "story_link_only": [], "already_filed": [], "skipped": [],
              "close_pending": [], "problems": [], "available": [], "message": "There are no bugs in bugs/."})
        return

    wanted = None
    if a.bug_id is not None:
        wanted = norm_bug_id(a.bug_id)
        if not wanted or wanted not in bugs:
            dump({"ok": False, "error": f"Bug '{a.bug_id}' does not exist in bugs/.", "available": available}, code=2)

    sync = (load_json(a.sync, {}) or {}).get("bugs") or {}
    out = {"ok": True, "story": story or None, "to_file": [], "story_link_only": [], "already_filed": [],
           "skipped": [], "close_pending": [], "cross_platform": [], "problems": [], "available": available}
    for bid, e in sync.items():
        if (e or {}).get("status") == "close_pending":
            out["close_pending"].append({"id": bid, "jiraKey": e.get("jiraKey"), "note": e.get("note")})

    for bid, b in bugs.items():
        if wanted and bid != wanted:
            continue
        e = sync.get(bid)
        if e and e.get("jiraKey"):
            row = {"id": bid, "title": b["title"], "jiraKey": e["jiraKey"], "url": e.get("url"),
                   "status": e.get("status"), "storyLink": e.get("storyLink")}
            out["already_filed"].append(row)
            if story and e.get("storyLink") != story:
                out["story_link_only"].append({**b, "jiraKey": e["jiraKey"], "url": e.get("url")})
            continue
        if b["jira_key_in_file"]:
            out["problems"].append(f"{bid}: the bug file shows Jira {b['jira_key_in_file']} but jira-sync.json has "
                                   "no entry; the label check in Phase 6 will reuse that issue if it exists")
        st = (b["status"] or "").strip().lower()
        if st in SKIP_STATUSES:
            out["skipped"].append({"id": bid, "title": b["title"], "reason": f"Status is {b['status']}"})
            continue
        if st != "open":
            out["skipped"].append({"id": bid, "title": b["title"],
                                   "reason": f"Status is '{b['status'] or 'empty'}', only Open bugs are filed"})
            continue
        md, how, cands = resolve_testcase_file(b, root)
        b["testcase_md"] = rel(md, root) if md else None
        b["how_found"] = how
        if len(cands) > 1:
            b["testcase_candidates"] = [rel(c, root) for c in cands]
        if not md:
            out["problems"].append(f"{bid}: test case file not found ({how}); the Jira links cannot be written "
                                   "back to the test cases and report")
        b["plan_key"] = plan_key_for(md, root) if md else ""
        if b.get("platform"):
            cands = []
            for oid, ob in bugs.items():
                e2 = sync.get(oid) or {}
                if oid == bid or not ob.get("platform") or ob["platform"] == b["platform"]:
                    continue
                if same_problem(b["title"], ob["title"]):
                    cands.append({"id": oid, "jiraKey": e2.get("jiraKey"), "url": e2.get("url"),
                                  "platform": PLATFORMS[ob["platform"]], "title": ob["title"],
                                  "label": f"{e2['jiraKey']} ({PLATFORMS[ob['platform']]})" if e2.get("jiraKey")
                                  else f"{oid} ({PLATFORMS[ob['platform']]}, not in Jira yet)"})
            if cands:
                b["cross_platform"] = cands
                out["cross_platform"].append({"id": bid, "platform": PLATFORMS[b["platform"]], "candidates": cands})
        out["to_file"].append(b)

    if wanted and not out["to_file"] and not out["story_link_only"]:
        out["message"] = (f"{wanted} is already in Jira." if out["already_filed"]
                          else f"{wanted} is not filed: {out['skipped'][0]['reason']}." if out["skipped"] else "")
    elif not out["to_file"] and not out["story_link_only"]:
        out["message"] = "Nothing to file: every open bug is already in Jira."
    if a.out:
        write_json_atomic(a.out, out)
        brief = dict(out)
        brief["to_file"] = [{k: b.get(k) for k in ("id", "title", "severity", "priority", "platform", "test_cases",
                                                     "testcase_md", "how_found", "plan_key", "evidence_files",
                                                     "cross_platform")} for b in out["to_file"]]
        brief["story_link_only"] = [{"id": b["id"], "jiraKey": b["jiraKey"]} for b in out["story_link_only"]]
        brief["out"] = a.out
        dump(brief)
    else:
        dump(out)


if __name__ == "__main__":
    main()
