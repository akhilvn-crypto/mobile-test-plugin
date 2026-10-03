#!/usr/bin/env python3
"""Turn one bug report into the Jira payload (section 7 of the plan, references/jira-field-mapping.md).

  python bug_to_jira.py --bugs-json "<scratchpad>/bugs.json" --id BUG-003 --meta "<scratchpad>/meta.json"
                        [--out "<scratchpad>/BUG-003.payload.json"]

--bugs-json: the --out file of list_bugs.py.  --meta: what Phase 3 found in the project (written by Claude):
  {"projectKey": "PROJ", "issueType": "Bug",
   "priorities": ["Highest", "High", "Medium", "Low", "Lowest"],      # allowed values, highest first
   "environmentField": true,                                           # the create screen has Environment
   "severityField": {"key": "customfield_10040", "values": ["Critical", "Major", "Minor", "Trivial"]} | null,
   "extraFields": {"customfield_10001": {"value": "QA"}}}              # required fields the user answered

Output payload (pass the parts to createJiraIssue exactly as given):
  {"summary", "description" (markdown), "issueTypeName", "additional_fields": {priority, labels, environment?,
   <severity field>?, ...extraFields}, "evidence_files": [local paths the user attaches by hand],
   "checks": {...what to compare in the read-back...}, "notes": [...], "lint": {...}}
Exit 1 when the text fails the wording/secret lint (nothing may be sent to Jira then).
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fbj import SKILL, dump, find_root, load_json, utf8_stdio, write_json_atomic  # noqa: E402
import lint_human_text  # noqa: E402

TEMPLATE = os.path.join(SKILL, "assets", "jira-description-template.md")
PRIORITY_ALIASES = {"high": ["high", "major"], "medium": ["medium", "normal"], "low": ["low", "minor"]}


def label(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(text).strip()).strip("-")[:255]


def map_priority(bug, allowed):
    """-> (value or None, note)."""
    if not allowed:
        return None, "The project lists no Priority values; Jira's default priority is used."
    if (bug.get("severity") or "").lower() == "critical":
        return allowed[0], f"Severity is Critical, so the highest priority '{allowed[0]}' is used."
    want = (bug.get("priority") or "").strip().lower()
    by_lower = {v.lower(): v for v in allowed}
    for alias in PRIORITY_ALIASES.get(want, [want]):
        if alias in by_lower:
            return by_lower[alias], ""
    return None, (f"Priority '{bug.get('priority')}' has no match in {allowed}; Jira's default priority is used.")


def map_severity(bug, field):
    if not field:
        return None
    sev = (bug.get("severity") or "").strip().lower()
    for v in field.get("values") or []:
        if str(v).strip().lower() == sev:
            return v
    return None


def adf_bullets(lines):
    return {"type": "doc", "version": 1, "content": [{"type": "bulletList", "content": [
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": l}]}]}
        for l in lines]}]}


def render(bug, meta):
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    env_field = bool(meta.get("environmentField"))
    env_lines = [l for l in bug.get("environment") or [] if l.strip()]
    env_section = ""
    if env_lines and not env_field:
        env_section = "\n## Environment\n" + "\n".join(f"- {l}" for l in env_lines) + "\n"
    sev_field = map_severity(bug, meta.get("severityField"))
    sev_line = "" if sev_field else f"\nSeverity: {bug.get('severity') or 'not set'}\n"
    files = [os.path.basename(f) for f in bug.get("evidence_files") or []]
    att = "Screenshots, recordings and logs: " + ", ".join(files) + "." if files else "No screenshots or recordings."
    if meta.get("attachmentNote"):  # e.g. a recording too large for Jira: its local path
        att += "\n" + meta["attachmentNote"]
    insights = bug.get("insights") or []
    values = {
        "summary": bug.get("summary") or "", "description": bug.get("description") or "",
        "steps": "\n".join(f"{i}. {s}" for i, s in enumerate(bug.get("steps") or [], 1)),
        "expected": bug.get("expected") or "", "actual": bug.get("actual") or "",
        "environment_section": env_section,
        "insights": "\n".join(f"- {x}" for x in insights) if insights else "None.",
        "severity_line": sev_line, "attachments": att,
        "test_cases": ", ".join(bug.get("test_cases") or []) or "none",
        "test_case_file": os.path.basename(bug.get("testcase_md") or bug.get("test_case_file") or "") or "unknown",
        "reported_on": bug.get("reported_on") or "", "bug_id": bug["id"],
    }
    text = re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m.group(1), "")), tpl)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text, env_lines, sev_field


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bugs-json", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    find_root()
    data = load_json(a.bugs_json, {}) or {}
    bug = next((b for b in (data.get("to_file") or []) + (data.get("story_link_only") or []) if b["id"] == a.id), None)
    if not bug:
        dump({"ok": False, "error": f"{a.id} is not in {a.bugs_json} (run list_bugs.py --out first)"}, code=2)
    meta = load_json(a.meta, {}) or {}
    description, env_lines, sev_value = render(bug, meta)
    evidence = [f"{bug['folder']}/{f}".replace("\\", "/") for f in bug.get("evidence_files") or []]
    summary = bug["title"].strip()[:255]
    notes = []
    prio, note = map_priority(bug, meta.get("priorities") or [])
    if note:
        notes.append(note)
    labels = [x for x in ("qa-found", label(bug["id"]), label(f"sev-{(bug.get('severity') or 'unknown').lower()}"),
                          label(bug.get("plan_key") or "")) if x]
    if bug.get("platform"):  # mobile bug: mobile + android|ios
        labels += ["mobile", bug["platform"]]
    fields = {"labels": labels}
    if prio:
        fields["priority"] = {"name": prio}
    if meta.get("environmentField") and env_lines:
        fields["environment"] = adf_bullets(env_lines)
    sev_field = meta.get("severityField")
    if sev_field and sev_value:
        fields[sev_field["key"]] = {"value": sev_value}
    elif sev_field:
        notes.append(f"Severity '{bug.get('severity')}' is not one of {sev_field.get('values')}; it is given as a "
                     "label and a line in the description instead.")
    for k, v in (meta.get("extraFields") or {}).items():
        fields.setdefault(k, v)
    # wording and secrets: everything that goes to Jira
    to_check = [("summary", summary), ("description", description)] + [("environment", l) for l in env_lines]
    lint = lint_human_text.check_texts(to_check)
    payload = {
        "ok": not lint["errors"], "bug": bug["id"], "projectKey": meta.get("projectKey"),
        "issueTypeName": meta.get("issueType") or "Bug", "summary": summary, "description": description,
        "contentFormat": "markdown", "additional_fields": fields, "evidence_files": evidence,
        "checks": {"summary": summary, "priority": prio, "labels": labels,
                   "description_sections": ["Steps to Reproduce", "Expected Result", "Actual Result",
                                            "Notes for Developers"] + ([] if fields.get("environment") or not env_lines
                                                                       else ["Environment"]),
                   "environment_field": bool(fields.get("environment")),
                   "severity_field": {sev_field["key"]: sev_value} if sev_field and sev_value else None},
        "notes": notes, "lint": lint,
    }
    if a.out:
        write_json_atomic(a.out, payload)
        payload = {"ok": payload["ok"], "out": a.out, "summary": summary, "priority": prio, "labels": labels,
                   "evidence_files": evidence, "notes": notes, "lint": lint}
    dump(payload, code=0 if not lint["errors"] else 1)


if __name__ == "__main__":
    main()
