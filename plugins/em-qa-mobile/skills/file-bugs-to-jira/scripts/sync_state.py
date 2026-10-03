#!/usr/bin/env python3
"""Read and write bugs/jira-sync.json safely (atomic write, one entry per bug). The file never holds credentials.

  python sync_state.py show [--id BUG-003]
  python sync_state.py init --site https://x.atlassian.net --cloud-id <id> --project PROJ
  python sync_state.py set --id BUG-003 [--key PROJ-45] [--url <url>] [--status filed|close_pending|closed]
                       [--filed-on now|"<cell time>"] [--story PROJ-10] [--closed-on now|"<cell time>"]
                       [--note "<what is still needed>"] [--platform android|ios|web]
                       [--attached "<file>" ...] [--related PROJ-46]
  python sync_state.py project-fields --project PROJ [--set '{"customfield_10001": {"value": "QA"}}']
  python sync_state.py remove --id BUG-003            # only when a create was proven to have failed

Layout:
{"site": "...", "cloudId": "...", "projectKey": "PROJ",
 "projects": {"PROJ": {"extraFields": {...}, "issueType": "Bug"}},
 "bugs": {"BUG-003": {"jiraKey": "PROJ-45", "url": "...", "status": "filed", "filedOn": "...",
                      "storyLink": "PROJ-10", "closedOn": null, "platform": "android",
                      "attached": ["BUG-003_crash.mp4"], "related": ["PROJ-46"]}}}
`platform` is web for web bugs, android or ios for mobile bugs. `attached` lists files uploaded through the Jira REST
settings (mobile); without them the files are attached by hand and nothing is tracked.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fbj import SYNC_FILE, dump, ist_cell, load_json, utf8_stdio, write_json_atomic  # noqa: E402

STATUSES = ("filed", "close_pending", "closed")
SECRET_RX = re.compile(r"(?i)(token|password|secret|api[_-]?key|authorization)")


def load(path=SYNC_FILE):
    data = load_json(path, None) or {}
    data.setdefault("site", "")
    data.setdefault("cloudId", "")
    data.setdefault("projectKey", "")
    data.setdefault("bugs", {})
    for e in data["bugs"].values():  # attachment state of older versions; uploads are tracked in "attached" now
        if isinstance(e, dict):
            e.pop("attachments", None)
    return data


def save(data, path=SYNC_FILE):
    if SECRET_RX.search(" ".join(_keys(data))):
        raise SystemExit("refusing to write a credential-like key into jira-sync.json")
    write_json_atomic(path, data)


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def entry(data, bid):
    return data["bugs"].setdefault(bid, {"jiraKey": None, "url": None, "status": None, "filedOn": None,
                                         "storyLink": None, "closedOn": None})


def when(v):
    return ist_cell() if v == "now" else v


def cmd_show(a):
    data = load(a.file)
    if a.id:
        dump({"ok": True, "bug": a.id, "entry": data["bugs"].get(a.id)})
        return
    dump({"ok": True, "exists": os.path.exists(a.file), **data})


def cmd_init(a):
    data = load(a.file)
    data["site"], data["cloudId"], data["projectKey"] = a.site.rstrip("/"), a.cloud_id, a.project
    save(data, a.file)
    dump({"ok": True, "site": data["site"], "projectKey": a.project})


def cmd_set(a):
    data = load(a.file)
    e = entry(data, a.id)
    if a.key:
        if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", a.key):
            dump({"ok": False, "error": f"'{a.key}' is not a Jira key"}, code=1)
        if e.get("jiraKey") and e["jiraKey"] != a.key:
            dump({"ok": False, "error": f"{a.id} is already recorded as {e['jiraKey']}"}, code=1)
        e["jiraKey"] = a.key
    if a.url:
        e["url"] = a.url
    elif a.key and not e.get("url") and data.get("site"):
        e["url"] = f"{data['site']}/browse/{a.key}"
    if a.status:
        e["status"] = a.status
    if a.filed_on:
        e["filedOn"] = when(a.filed_on)
    if a.story:
        e["storyLink"] = a.story
    if a.closed_on:
        e["closedOn"] = when(a.closed_on)
    if a.note is not None:
        e["note"] = a.note or None
    if a.platform:
        e["platform"] = a.platform
    for f in a.attached or []:
        e.setdefault("attached", [])
        if f not in e["attached"]:
            e["attached"].append(f)
    for r in a.related or []:
        e.setdefault("related", [])
        if r not in e["related"]:
            e["related"].append(r)
    save(data, a.file)
    dump({"ok": True, "bug": a.id, "entry": e})


def cmd_project_fields(a):
    data = load(a.file)
    p = data.setdefault("projects", {}).setdefault(a.project, {})
    if a.set:
        p["extraFields"] = json.loads(a.set)
        save(data, a.file)
    if a.issue_type:
        p["issueType"] = a.issue_type
        save(data, a.file)
    dump({"ok": True, "project": a.project, **p})


def cmd_remove(a):
    data = load(a.file)
    e = data["bugs"].pop(a.id, None)
    save(data, a.file)
    dump({"ok": True, "removed": e})


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sync", dest="file", default=SYNC_FILE, help="state file (default bugs/jira-sync.json)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("show")
    p.add_argument("--id")
    p.set_defaults(fn=cmd_show)
    p = sp.add_parser("init")
    p.add_argument("--site", required=True)
    p.add_argument("--cloud-id", required=True)
    p.add_argument("--project", required=True)
    p.set_defaults(fn=cmd_init)
    p = sp.add_parser("set")
    p.add_argument("--id", required=True)
    p.add_argument("--key")
    p.add_argument("--url")
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--filed-on")
    p.add_argument("--story")
    p.add_argument("--closed-on")
    p.add_argument("--note")
    p.add_argument("--platform", choices=("web", "android", "ios"))
    p.add_argument("--attached", action="append", help="a file uploaded to the issue (repeatable)")
    p.add_argument("--related", action="append", help="key of a related issue linked with Relates (repeatable)")
    p.set_defaults(fn=cmd_set)
    p = sp.add_parser("project-fields")
    p.add_argument("--project", required=True)
    p.add_argument("--set")
    p.add_argument("--issue-type")
    p.set_defaults(fn=cmd_project_fields)
    p = sp.add_parser("remove")
    p.add_argument("--id", required=True)
    p.set_defaults(fn=cmd_remove)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
