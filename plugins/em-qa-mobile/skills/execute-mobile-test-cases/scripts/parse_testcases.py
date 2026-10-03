#!/usr/bin/env python3
"""Test case MD -> JSON (Phase 1). Columns are found by header name, never by position.

  python parse_testcases.py "<test cases .md>" [--out <file.json>] [--flow <flow-key>] [--to-run]

Per case: flow_key, flow_name, id, level, type, number, title, description, preconditions, steps[],
test_data{label: value}, expected, actual, status, comments, executed_on, defects, obsolete, run,
app_state (fresh install | logged out | logged in - a hint from the preconditions; the script writer confirms it)
and device_condition (for MOB cases: what the case needs from the device, e.g. permissions, network).

`run` is true when the status is PENDING, IN PROGRESS, BLOCKED or FAIL and the case is not [OBSOLETE].
PASS cases are not re-run.

With --out the full JSON goes to the file and a short summary is printed; otherwise the full JSON is printed.
"""
import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (COLUMNS, RUN_STATUSES, dump, id_parts, is_obsolete, norm_header,  # noqa: E402
                     parse_testcase_md, utf8_stdio, write_json_atomic)

LEVELS = {"CMP": "Component", "INT": "Integration", "E2E": "End-to-end", "API": "API", "SEC": "Security",
          "ACC": "Accessibility", "UI": "UI/UX", "MOB": "Mobile conditions"}
CONDITION_WORDS = [
    ("interruption", r"incoming call|phone call|notification arrives|low battery|battery warning|alarm"),
    ("network", r"airplane|aeroplane|offline|no (internet|connection|network)|wi-?fi|mobile data|slow (connection|network)"),
    ("permissions", r"permission|allow|deny|don.t allow"),
    ("orientation", r"landscape|portrait|rotate"),
    ("lifecycle", r"background|minimi[sz]e|reopen|force stop|close the app|first launch|relaunch|restart"),
    ("device settings", r"dark mode|language|font size|display size"),
    ("navigation", r"back button|back gesture|deep link|pull to refresh|scroll to the end"),
]


def app_state(pre, steps):
    t = f"{pre} {steps}".lower()
    if re.search(r"fresh(ly)? install|first launch|first time|new install|app data cleared", t):
        return "fresh install"
    if re.search(r"(signed|logged) in|sign(ed)? in as|log(ged)? in as", pre.lower()):
        return "logged in"
    return "logged out"


def device_condition(level, pre, steps, expected):
    if level != "MOB":
        return ""
    t = f"{pre} {steps} {expected}".lower()
    return next((name for name, rx in CONDITION_WORDS if re.search(rx, t)), "other")
TYPES = {"POS": "Positive", "NEG": "Negative", "EDG": "Edge", "BND": "Boundary", "VAL": "Validation",
         "ERR": "Error"}


def steps_list(text):
    out = []
    for line in (text or "").split("\n"):
        line = line.strip()
        if line:
            out.append(re.sub(r"^\d+[.)]\s*", "", line))
    return out


def data_dict(text):
    out = {}
    for line in (text or "").split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
        elif line.strip():
            out.setdefault("_notes", []).append(line.strip())
    return out


def build(md):
    doc = parse_testcase_md(md)
    flows, problems = [], []
    for f in doc["flows"]:
        missing = [c for c in ("Test Case ID", "Execution Status", "Actual Result") if c not in f["colmap"]]
        if f["table"] is None:
            problems.append(f"Flow '{f['name']}': no test case table found")
        elif missing:
            problems.append(f"Flow '{f['name']}': missing columns {missing}")
        cases = []
        for c in f["cases"]:
            cid = (c.get("Test Case ID") or "").strip()
            level, typ, num = id_parts(cid)
            if not level:
                problems.append(f"Flow '{f['name']}': unrecognised Test Case ID '{cid}'")
            status = (c.get("Execution Status") or "PENDING").strip().upper() or "PENDING"
            obsolete = is_obsolete(c)
            cases.append({
                "flow_key": f["key"], "flow_name": f["name"], "id": cid, "level": level,
                "level_name": LEVELS.get(level, ""), "type": typ, "type_name": TYPES.get(typ, ""), "number": num,
                "title": c.get("Test Case Title", ""), "description": c.get("Test Description", ""),
                "preconditions": c.get("Preconditions", ""), "steps": steps_list(c.get("Test Steps", "")),
                "test_data": data_dict(c.get("Test Data", "")), "test_data_raw": c.get("Test Data", ""),
                "expected": c.get("Expected Result", ""), "actual": c.get("Actual Result", ""),
                "status": status, "comments": c.get("Comments", ""), "executed_on": c.get("Executed On", ""),
                "defects": c.get("Execution Defects", ""), "obsolete": obsolete,
                "run": (not obsolete) and status in RUN_STATUSES,
                "app_state": app_state(c.get("Preconditions", ""), c.get("Test Steps", "")),
                "device_condition": device_condition(level, c.get("Preconditions", ""), c.get("Test Steps", ""),
                                                     c.get("Expected Result", "")),
            })
        flows.append({"key": f["key"], "name": f["name"], "user_story_ref": f["user_story_ref"],
                      "user_story_title": f["user_story_title"],
                      "unknown_columns": [h for h in f["colmap"] if h not in COLUMNS], "cases": cases})
    return doc, flows, problems


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md")
    ap.add_argument("--out")
    ap.add_argument("--flow", help="only this flow key")
    ap.add_argument("--to-run", action="store_true", help="only cases that should run")
    a = ap.parse_args()
    if not os.path.isfile(a.md):
        dump({"ok": False, "error": f"File not found: {a.md}"}, code=2)
    doc, flows, problems = build(a.md)
    if a.flow:
        flows = [f for f in flows if f["key"] == a.flow]
    if a.to_run:
        for f in flows:
            f["cases"] = [c for c in f["cases"] if c["run"]]
    result = {
        "ok": not problems,
        "problems": problems,
        "md": a.md,
        "plan_name": doc["header"].get("Plan name", ""),
        "plan_key": doc["header"].get("Plan key", ""),
        "project": doc["header"].get("Project", ""),
        "application_url": doc["header"].get("Application URL", ""),
        "version": doc["front_matter"].get("version", ""),
        "flows": flows,
    }
    summary = {
        "ok": result["ok"], "problems": problems,
        "flows": [{
            "key": f["key"], "name": f["name"], "total": len(f["cases"]),
            "to_run": sum(c["run"] for c in f["cases"]),
            "obsolete": sum(c["obsolete"] for c in f["cases"]),
            "status": dict(Counter(c["status"] for c in f["cases"] if not c["obsolete"])),
            "to_run_ids": [c["id"] for c in f["cases"] if c["run"]],
        } for f in flows],
    }
    summary["to_run_total"] = sum(f["to_run"] for f in summary["flows"])
    if a.out:
        write_json_atomic(a.out, result)
        summary["out"] = a.out
        dump(summary)
    else:
        dump(result)


if __name__ == "__main__":
    main()
