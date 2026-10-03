#!/usr/bin/env python3
"""Build the MD Test Report (Phase 7 of execute-mobile-test-cases) and the data used by build_report_xlsx.py.

  python build_report_md.py "<test cases .md>" [--context <context.json>] [--check] [--force]
                            [--bug-index bugs/bug-index.md] [--reports-dir "Test Reports"]

The report shows the CURRENT state of every non-obsolete case in the test case file (not only this run).

--check   Print {up_to_date, next_version, last_report, results_hash} and write nothing (refresh rule).
--force   Build even when the results are unchanged since the last report.

context.json (written by Claude, all keys optional):
  {"summary": "3-5 plain sentences (default: generated from the numbers)",
   "environment": "Development", "device": "Pixel 7", "os_version": "Android 14",
   "build": "2.4.1 (build 123)", "network": "Wi-Fi",
   "observations": ["..."], "testability": ["Login screen: the eye icon of the Password field has no label"],
   "device_results": ["All cases ran on one device (Pixel 7, Android 14)."],
   "ux_suggestions": ["..."],
   "reasons": {"TC-…": "plain reason for a blocked or unexecuted case"},
   "version_comment": "Updated after retest of 3 failed cases"}
The platform comes from the test case file (header row Platform); cases left for a manual check are listed
automatically under Observations.

Writes `Test Reports/<Plan>_<Platform>_Test_Report_<YYYY-MM-DD>_<HH-MM-SS>-IST.md` (never overwrites), the data file
`Test Reports/.data/<same stem>.json` (pass it to build_report_xlsx.py) and updates `Test Reports/.state.json`.
Statuses use the report wording: PENDING -> UNEXECUTED.
Jira: bugs recorded in bugs/jira-sync.json are shown as "[PROJ-45](<url>) (BUG-003) - <title>" in Comments and get a
Jira column in "Defects raised" (jira_refs.py). The results hash ignores Jira keys, so filing a bug in Jira does not
by itself make the last report out of date.
"""
import argparse
import os
import re
import sys
import time
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (PLATFORM_NAMES, REPORT_STATUS, dump, find_manifest, find_root, ist_cell, ist_date,  # noqa: E402
                     ist_file, is_obsolete, load_json, parse_front_matter, parse_testcase_md, platform_of,
                     platform_part, rel, safe_name, sha, utf8_stdio, write_json_atomic, write_text_atomic)
from update_results import read_bug_index  # noqa: E402
import jira_refs  # noqa: E402

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(SKILL, "assets", "test-report-template.md")
SEVERITY_ORDER = ["Critical", "Major", "Minor", "Trivial"]

# runner-flavoured notes from the test case Comments -> report wording
COMMENT_REWRITES = [
    (re.compile(r"^Passed on retry, intermittent\.?\s*Worth watching\.?", re.I),
     "Passed on the second attempt; the result is intermittent and worth watching."),
    (re.compile(r"^Could not be automated:\s*", re.I), "Could not be completed: "),
    (re.compile(r"^\s*\[(NEW|UPDATED)\]\s*", re.I), ""),
]


def clean_comment(text):
    t = (text or "").replace("\n", " ").strip()
    for rx, rep in COMMENT_REWRITES:
        t = rx.sub(rep, t)
    return t.strip()


def md_cell(text):
    return str(text or "").replace("|", "\\|").replace("\n", "<br>")


def bump(version):
    m = re.match(r"^V(\d+)\.(\d+)$", (version or "").strip())
    return f"V{m.group(1)}.{int(m.group(2)) + 1}" if m else "V1.0"


# ---------------------------------------------------------------- data

def collect(md, ctx, bug_index, root, sync=None):
    sync = sync or {}
    doc = parse_testcase_md(md)
    _, manifest_path = find_manifest(root, md, doc)
    platform = platform_of(doc, md)
    manifest = platform_part(load_json(manifest_path, {}) if manifest_path else {}, platform)
    bugs = read_bug_index(bug_index)
    plan_name = (doc["header"].get("Plan name") or (doc["h1"] or "").split(" – Test Cases")[0]).strip()
    flows, all_cases, referenced = [], [], OrderedDict()
    for f in doc["flows"]:
        mf = (manifest.get("flows") or {}).get(f["key"], {})
        ref = f["user_story_ref"] or mf.get("user_story_ref", "")
        title = f["user_story_title"] or mf.get("user_story_title", "")
        rows = []
        for c in f["cases"]:
            if is_obsolete(c):
                continue
            cid = c.get("Test Case ID", "")
            status = (c.get("Execution Status") or "PENDING").strip().upper()
            rstatus = REPORT_STATUS.get(status, "UNEXECUTED")
            bug_ids = re.findall(r"BUG-\d+", c.get("Execution Defects", "") or "")
            for b in bug_ids:
                referenced.setdefault(b, []).append(cid)
            note = clean_comment(c.get("Comments", ""))
            links = []
            if rstatus == "FAIL" and bug_ids:
                def bug_note(ref):
                    return "; ".join(f"{ref(b)} - {bugs[b].get('title', '')}".rstrip(" -") if b in bugs else ref(b)
                                     for b in bug_ids)
                base = bug_note(lambda b: b)
                plain = bug_note(lambda b: jira_refs.plain_ref(b, sync))
                linked = bug_note(lambda b: jira_refs.md_ref(b, sync))
                links = [sync[b]["url"] for b in bug_ids if b in sync]
                comment_base = base if not note else f"{base}. {note}"
                comment = plain if not note else f"{plain}. {note}"
                comment_md = linked if not note else f"{linked}. {note}"
            elif rstatus in ("BLOCKED", "UNEXECUTED") and cid in (ctx.get("reasons") or {}):
                comment = comment_base = comment_md = ctx["reasons"][cid]
            else:
                comment = comment_base = comment_md = note
            row = {"n": len(rows) + 1, "story_ref": ref, "story_desc": title or f["name"],
                   "scenario": (c.get("Test Description") or c.get("Test Case Title") or "").replace("\n", " "),
                   "id": cid, "title": c.get("Test Case Title", ""), "status": rstatus, "comment": comment,
                   "comment_md": comment_md, "comment_base": comment_base, "links": links,
                   "actual": c.get("Actual Result", ""), "executed_on": c.get("Executed On", ""),
                   "defects": bug_ids}
            rows.append(row)
            all_cases.append(row)
        flows.append({"key": f["key"], "name": f["name"], "story_ref": ref, "story_title": title, "rows": rows})
    # bugs that name a case of this file in the index, even if the case no longer lists them
    ids = {r["id"] for r in all_cases}
    for b, row in bugs.items():
        tcs = re.findall(r"TC-[A-Z0-9]+-[A-Z]+-\d+", row.get("test case", "") or "")
        if any(t in ids for t in tcs):
            referenced.setdefault(b, [])
            for t in tcs:
                if t in ids and t not in referenced[b]:
                    referenced[b].append(t)
    defects = []
    for b in sorted(referenced, key=lambda x: int(x.split("-")[1])):
        row = bugs.get(b, {})
        defects.append({"id": b, "title": row.get("title", ""), "severity": row.get("severity", ""),
                        "priority": row.get("priority", ""), "status": row.get("status", ""),
                        "test_cases": row.get("test case", "") or ", ".join(referenced[b]),
                        "folder": row.get("folder", ""),
                        "jira_key": (sync.get(b) or {}).get("jiraKey", ""),
                        "jira_url": (sync.get(b) or {}).get("url", "")})
    cnt = Counter(r["status"] for r in all_cases)
    counts = {"passed": cnt.get("PASS", 0), "failed": cnt.get("FAIL", 0), "unexecuted": cnt.get("UNEXECUTED", 0),
              "in_progress": cnt.get("IN PROGRESS", 0), "blocked": cnt.get("BLOCKED", 0)}
    counts["executed"] = counts["passed"] + counts["failed"]
    counts["total"] = counts["executed"] + counts["unexecuted"] + counts["in_progress"] + counts["blocked"]
    hash_src = "\n".join(f"{r['id']}|{r['status']}|{r['actual']}|{','.join(r['defects'])}|{r['comment_base']}|"
                         f"{r['executed_on']}" for r in all_cases)
    hash_src += "\n" + "\n".join(f"{d['id']}|{d['status']}|{d['severity']}|{d['title']}" for d in defects)
    return {
        "plan_name": plan_name,
        "plan_key": doc["header"].get("Plan key") or (os.path.basename(os.path.dirname(manifest_path))
                                                      if manifest_path else ""),
        "project": doc["header"].get("Project", ""),
        "platform": platform,
        "platform_name": PLATFORM_NAMES.get(platform, platform),
        "device": doc["header"].get("Device", "") or manifest.get("device", ""),
        "os_version": doc["header"].get("OS version", "") or manifest.get("os_version", ""),
        "app_build": doc["header"].get("App version and build", ""),
        "testcase_file": rel(md, root),
        "flows": flows, "counts": counts, "defects": defects,
        "results_hash": sha(hash_src),
    }


# ---------------------------------------------------------------- state / version

def state_key(data):
    return f"{data['plan_key'] or data['plan_name']}::{data.get('platform') or ''}"


def report_prefix(data):
    return f"{safe_name(data['plan_name'])}_{data.get('platform_name') or ''}_Test_Report_"


def previous(reports_dir, data):
    state = load_json(os.path.join(reports_dir, ".state.json"), {}) or {}
    entry = (state.get("plans") or {}).get(state_key(data))
    if entry and entry.get("last_report") and os.path.exists(os.path.join(reports_dir, entry["last_report"])):
        with open(os.path.join(reports_dir, entry["last_report"]), encoding="utf-8") as f:
            fm, _ = parse_front_matter(f.read())
        return state, entry, fm.get("version") or entry.get("version")
    # no state: fall back to the newest report of this plan in the folder
    prefix = report_prefix(data)
    found = sorted(x for x in os.listdir(reports_dir) if x.startswith(prefix) and x.endswith(".md")) \
        if os.path.isdir(reports_dir) else []
    if found:
        with open(os.path.join(reports_dir, found[-1]), encoding="utf-8") as f:
            fm, _ = parse_front_matter(f.read())
        return state, {"last_report": found[-1], "results_hash": None}, fm.get("version")
    return state, None, None


# ---------------------------------------------------------------- rendering

def default_summary(data):
    c, flows = data["counts"], data["flows"]
    nflows = sum(1 for f in flows if f["rows"])
    s = [f"This report covers {c['total']} test case{'s' if c['total'] != 1 else ''} across "
         f"{nflows} flow{'s' if nflows != 1 else ''} of {data['plan_name']}."]
    if c["executed"] + c["blocked"] + c["in_progress"] == 0:
        s.append("None of the test cases have been executed yet.")
    else:
        s.append(f"{c['passed']} passed and {c['failed']} failed.")
        rest = []
        if c["blocked"]:
            rest.append(f"{c['blocked']} could not be completed (blocked)")
        if c["in_progress"]:
            rest.append(f"{c['in_progress']} are still in progress")
        if c["unexecuted"]:
            manual = sum(1 for f in flows for r in f["rows"]
                         if r["status"] == "UNEXECUTED" and r["comment"].lower().startswith("needs manual check"))
            extra = f", {manual} of them waiting for a manual check" if manual else ""
            rest.append(f"{c['unexecuted']} have not been executed{extra}")
        if rest:
            s.append(", ".join(rest[:-1]) + (" and " if len(rest) > 1 else "") + rest[-1] + ".")
            s[-1] = s[-1][0].upper() + s[-1][1:]
    d = data["defects"]
    if d:
        worst = sorted(d, key=lambda x: SEVERITY_ORDER.index(x["severity"]) if x["severity"] in SEVERITY_ORDER else 9)[0]
        sev = f" ({worst['severity']})" if worst["severity"] else ""
        s.append(f"{len(d)} defect{'s were' if len(d) != 1 else ' was'} raised; the most serious is "
                 f"{worst['id']}{sev}: {worst['title']}.")
    else:
        s.append("No defects were raised.")
    return " ".join(s)


def render_suites(data, exec_date):
    out = []
    for f in data["flows"]:
        if not f["rows"]:
            continue
        out.append(f"## TestSuite : {f['name']}")
        out.append("")
        story = f"{f['story_ref']} - {f['story_title']}".strip(" -") if (f["story_ref"] or f["story_title"]) else ""
        out.append(f"Execution date: {exec_date}" + (f"  \nUser story: {story}" if story else ""))
        out.append("")
        out.append("| # | User Story # | User Story Description | Test Cases/Test Scenarios | Testcase # | Status | Comments |")
        out.append("|---|---|---|---|---|---|---|")
        for r in f["rows"]:
            out.append(f"| {r['n']} | {md_cell(r['story_ref'])} | {md_cell(r['story_desc'])} | {md_cell(r['scenario'])} | "
                       f"{r['id']} | {r['status']} | {md_cell(r.get('comment_md', r['comment']))} |")
        out.append("")
    return "\n".join(out).rstrip() or "No test cases in this file."


def render_defects(data, reports_dir, root):
    if not data["defects"]:
        return "No defects were raised."
    jira = any(d.get("jira_key") for d in data["defects"])
    lines = ["| Bug ID | Title | Severity | Status | Test case(s) |" + (" Jira |" if jira else "") + " Folder |",
             "|---|---|---|---|---|" + ("---|" if jira else "") + "---|"]
    for d in data["defects"]:
        folder = ""
        m = re.search(r"\(([^)]+)\)", d["folder"] or "")
        target = m.group(1) if m else (d["folder"] or "")
        if target:
            abs_t = os.path.join(root, "bugs", target) if not target.startswith("bugs") else os.path.join(root, target)
            link = os.path.relpath(abs_t, reports_dir).replace("\\", "/")
            folder = f"[{os.path.dirname(target).split('/')[-1] or d['id']}]({link.replace(' ', '%20')})"
        jcell = ""
        if jira:
            jcell = f" [{d['jira_key']}]({d['jira_url']}) |" if d.get("jira_key") else " Not filed |"
        lines.append(f"| {d['id']} | {md_cell(d['title'])} | {d['severity']} | {d['status']} | "
                     f"{md_cell(d['test_cases'])} |{jcell} {folder} |")
    return "\n".join(lines)


def render_blocked(data):
    rows = [r for f in data["flows"] for r in f["rows"] if r["status"] in ("BLOCKED", "UNEXECUTED", "IN PROGRESS")]
    if not rows:
        return "None. Every test case in the file was executed."
    lines = ["| Testcase # | Test case | Status | Reason |", "|---|---|---|---|"]
    for r in rows:
        reason = r["comment"] or ("Not executed yet." if r["status"] == "UNEXECUTED" else "")
        lines.append(f"| {r['id']} | {md_cell(r['title'])} | {r['status']} | {md_cell(reason)} |")
    return "\n".join(lines)


def bullets(items, empty):
    items = [str(x).strip() for x in (items or []) if str(x).strip()]
    return "\n".join(f"- {x}" for x in items) if items else empty


def render_observations(data, ctx):
    """General observations, then the mobile parts: testability findings, device-specific results and the cases
    left for a manual check because the device could not be put in that condition by the test run."""
    out = [bullets(ctx.get("observations"), "No general observations in this cycle.")]
    out += ["", "**Testability findings** (controls without a label or key; adding one makes testing more reliable)",
            "", bullets(ctx.get("testability"), "None recorded.")]
    device = (data.get("device") or "the connected device").replace(" (real device)", "")
    osv = f", {data['os_version']}" if data.get("os_version") else ""
    out += ["", "**Device-specific results**", "",
            bullets(ctx.get("device_results"), f"All results come from one real device: {device}{osv}.")]
    manual = []
    for f in data["flows"]:
        for r in f["rows"]:
            if r["status"] == "UNEXECUTED" and r["comment"].lower().startswith("needs manual check"):
                why = r["comment"][len("Needs manual check:"):].strip() or "it needs a person"
                manual.append(f"{r['id']} – {r['title']}: {why}")
    out += ["", "**Left for a manual check** (the device could not be put in that condition by the test run)", "",
            bullets(manual, "None.")]
    return "\n".join(out)


def render(data, ctx, version, exec_date, reports_dir, root):
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    project = data["project"]
    pn = data.get("platform_name") or ""
    title = (f"{project} – {data['plan_name']} {pn} Test Report" if project
             else f"{data['plan_name']} {pn} Test Report").replace("  ", " ")
    c = data["counts"]
    ux = (ctx.get("ux_suggestions") or [])[:5]
    device = (ctx.get("device") or data.get("device") or "").replace(" (real device)", "")
    values = {
        "title": title.replace('"', "'"), "version": version, "platform_tag": data.get("platform") or "android",
        "platform_name": data.get("platform_name") or "", "plan_name": data["plan_name"],
        "testcase_file": os.path.basename(data["testcase_file"]),
        "device": f"{device} (real device)" if device else "",
        "os_version": ctx.get("os_version") or data.get("os_version", ""),
        "environment": ctx.get("environment", ""), "network": ctx.get("network", ""),
        "execution_date": exec_date,
        "build": ctx.get("build") or data.get("app_build") or "Not shown by the application",
        "summary": (ctx.get("summary") or default_summary(data)).strip(),
        "passed": c["passed"], "failed": c["failed"], "executed": c["executed"], "unexecuted": c["unexecuted"],
        "in_progress": c["in_progress"], "blocked": c["blocked"], "total": c["total"],
        "suites_intro": "One table per flow. Statuses: PASS, FAIL, BLOCKED, IN PROGRESS and UNEXECUTED "
                        "(not executed yet).",
        "suites": render_suites(data, exec_date),
        "defects": render_defects(data, reports_dir, root),
        "blocked_unexecuted": render_blocked(data),
        "observations": render_observations(data, ctx),
        "ux_suggestions": bullets(ux, "No suggestions in this cycle."),
    }
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m.group(1), "")), tpl)
    return out.rstrip() + "\n"


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md")
    ap.add_argument("--context")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--bug-index", default="bugs/bug-index.md")
    ap.add_argument("--reports-dir", default="Test Reports")
    ap.add_argument("--jira-sync", default="bugs/jira-sync.json")
    a = ap.parse_args()
    root = find_root()
    if not os.path.isfile(a.md):
        dump({"ok": False, "error": f"File not found: {a.md}"}, code=2)
    ctx = load_json(a.context, {}) if a.context else {}
    reports_dir = os.path.abspath(a.reports_dir)
    data = collect(a.md, ctx, a.bug_index, root, jira_refs.load_sync(a.jira_sync))
    state, prev, prev_version = previous(reports_dir, data)
    up_to_date = bool(prev and prev.get("results_hash") == data["results_hash"])
    next_version = bump(prev_version) if prev_version else "V1.0"
    if a.check:
        dump({"ok": True, "up_to_date": up_to_date, "next_version": next_version,
              "last_report": prev.get("last_report") if prev else None, "results_hash": data["results_hash"],
              "counts": data["counts"]})
        return
    if up_to_date and not a.force:
        dump({"ok": True, "skipped": True, "reason": "All results are unchanged since the last report",
              "last_report": prev.get("last_report")})
        return
    os.makedirs(reports_dir, exist_ok=True)
    while True:
        ts = ist_file()
        stem = f"{report_prefix(data)}{ts}"
        path = os.path.join(reports_dir, stem + ".md")
        if not os.path.exists(path) and not os.path.exists(os.path.join(reports_dir, stem + ".xlsx")):
            break
        time.sleep(1)
    exec_date = ist_date()
    data["version"] = next_version
    data["execution_date"] = exec_date
    data["created_on"] = exec_date
    data["version_comment"] = ctx.get("version_comment") or (
        "First report for this plan" if next_version == "V1.0" else "Updated after a new test cycle")
    dev = (ctx.get("device") or data.get("device") or "").replace(" (real device)", "")
    data["device"] = dev
    data["os_version"] = ctx.get("os_version") or data.get("os_version", "")
    data["app_build"] = ctx.get("build") or data.get("app_build", "")
    data["mobile_line"] = ", ".join(x for x in (data.get("platform_name"), dev, data["os_version"],
                                                  f"app {data['app_build']}" if data["app_build"] else "") if x)
    write_text_atomic(path, render(data, ctx, next_version, exec_date, reports_dir, root))
    data_file = os.path.join(reports_dir, ".data", stem + ".json")
    write_json_atomic(data_file, data)
    plans = state.setdefault("plans", {})
    plans[state_key(data)] = {"last_report": os.path.basename(path), "results_hash": data["results_hash"],
                              "version": next_version, "updated_ist": ist_cell()}
    write_json_atomic(os.path.join(reports_dir, ".state.json"), state)
    dump({"ok": True, "report": rel(path, root), "data": rel(data_file, root), "version": next_version,
          "counts": data["counts"], "defects": [d["id"] for d in data["defects"]],
          "xlsx_path": rel(os.path.join(reports_dir, stem + ".xlsx"), root)})


if __name__ == "__main__":
    main()
