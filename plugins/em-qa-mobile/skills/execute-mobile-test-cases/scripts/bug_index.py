#!/usr/bin/env python3
"""Maintain bugs/bug-index.md and the bug folders (Phase 5).

  python bug_index.py next                                   -> {"next_id": "BUG-004", "folder_prefix": ...}
  python bug_index.py list                                   -> every bug row (for the duplicate check)
  python bug_index.py add --id BUG-004 --title "<Feature> - <what is wrong>" --severity Major --priority High
                          --test-cases "TC-UI-NEG-014" --folder "BUG-004_<slug>" [--status Open] [--reported-on ...]
  python bug_index.py also-seen --id BUG-003 --test-case TC-UI-NEG-020 --note "Same message missing on the footer form"
  python bug_index.py set-status --id BUG-003 --status "Fixed - verified"
  python bug_index.py set-jira --id BUG-003 --key PROJ-45 --url https://site.atlassian.net/browse/PROJ-45
  python bug_index.py slug "<title>"                         -> short folder slug

Bug IDs run BUG-001, BUG-002 … across the project and are never reused. The index is a Markdown table:
| Bug ID | Title | Severity | Priority | Status | Test case(s) | Reported on | Jira | Folder |
Rows are read by header name; an older index without the Jira column gets it (value "Not filed") on the next write.
`set-status`, `set-jira` and `also-seen` also update the bug's own report (Status / Jira field, Test case(s),
"Also seen in"). The Jira column and field are filled by the file-bugs-to-jira skill.
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import dump, ist_cell, ist_date, read_tables, slug, utf8_stdio, write_text_atomic  # noqa: E402

HEADER = ["Bug ID", "Title", "Severity", "Priority", "Status", "Test case(s)", "Reported on", "Jira", "Folder"]
NOT_FILED = "Not filed"


def index_path(a):
    return os.path.join(a.bugs_dir, "bug-index.md")


def load(path):
    """-> (lines, header line index, rows[(line index, cells in HEADER order)]).
    An older layout is mapped by header name and rewritten in the current layout (in memory)."""
    if not os.path.exists(path):
        return ["# Bug Index", "", "| " + " | ".join(HEADER) + " |", "|" + "---|" * len(HEADER)], 2, []
    with open(path, encoding="utf-8") as f:
        lines = f.read().rstrip("\n").split("\n")
    for header, rows, a, _ in read_tables(lines, 0, len(lines)):
        if header and header[0] == "Bug ID":
            if header != HEADER:
                pos = {h: i for i, h in enumerate(header)}
                lines[a] = "| " + " | ".join(HEADER) + " |"
                lines[a + 1] = "|" + "---|" * len(HEADER)
                new_rows = []
                for li, c in rows:
                    d = {h: (c[pos[h]] if h in pos and pos[h] < len(c) else "") for h in HEADER}
                    d["Jira"] = d["Jira"] or NOT_FILED
                    lines[li] = fmt(d)
                    new_rows.append((li, [d[h] for h in HEADER]))
                rows = new_rows
            return lines, a, rows
    lines += ["", "| " + " | ".join(HEADER) + " |", "|" + "---|" * len(HEADER)]
    return lines, len(lines) - 2, []


def row_dict(cells):
    return {HEADER[i]: (cells[i] if i < len(cells) else "") for i in range(len(HEADER))}


def save(path, lines):
    write_text_atomic(path, "\n".join(lines) + "\n")


def fmt(d):
    return "| " + " | ".join(str(d.get(h, "") or "").replace("|", "\\|") for h in HEADER) + " |"


def all_ids(bugs_dir, rows):
    ids = {int(m.group(1)) for _, c in rows for m in [re.match(r"BUG-(\d+)", c[0])] if m}
    for d in glob.glob(os.path.join(bugs_dir, "BUG-*")):
        m = re.match(r"BUG-(\d+)", os.path.basename(d))
        if m:
            ids.add(int(m.group(1)))
    return ids


def find_row(rows, bid):
    for li, c in rows:
        if c and c[0].strip() == bid:
            return li, row_dict(c)
    return None, None


def bug_file(bugs_dir, bid, row=None):
    m = re.search(r"\(([^)]+)\)", (row or {}).get("Folder", ""))
    if m:
        p = os.path.join(bugs_dir, m.group(1).replace("%20", " "))
        if os.path.exists(p):
            return p
    hits = glob.glob(os.path.join(bugs_dir, f"{bid}_*", f"{bid}_*.md"))
    return hits[0] if hits else None


def field_rx(field):
    # [ \t] rather than \s: the match must never run past the end of its own line
    return re.compile(r"^(\|[ \t]*" + re.escape(field) + r"[ \t]*\|[ \t]*)(.*?)([ \t]*\|[ \t]*)$", re.M)


def set_field(text, field, value):
    return field_rx(field).sub(lambda m: m.group(1) + value + m.group(3), text, count=1)


def set_or_add_field(text, field, value, after=("Jira", "Reported on", "Test case file", "Test case(s)", "Status")):
    """Set a row of the bug's field table; add it after the first existing anchor row when it is missing."""
    if field_rx(field).search(text):
        return set_field(text, field, value)
    for anchor in after:
        m = field_rx(anchor).search(text)
        if m:
            return text[:m.end()] + f"\n| {field} | {value} |" + text[m.end():]
    return text


def update_bug_file(bf, changes):
    """changes: [(field, value)] applied with set_or_add_field."""
    if not bf:
        return
    with open(bf, encoding="utf-8") as f:
        text = f.read()
    for field, value in changes:
        text = set_or_add_field(text, field, value)
    write_text_atomic(bf, text)


def set_status(bugs_dir, bid, status, extra=None):
    path = os.path.join(bugs_dir, "bug-index.md")
    lines, _, rows = load(path)
    li, row = find_row(rows, bid)
    if row:
        row["Status"] = status
        lines[li] = fmt(row)
        save(path, lines)
    bf = bug_file(bugs_dir, bid, row)
    update_bug_file(bf, [("Status", status)] + list(extra or []))
    return {"index_row": bool(row), "bug_file": bf}


def set_jira(bugs_dir, bid, key, url):
    """Index Jira cell and the bug report's Jira field -> [KEY](url). Used by file-bugs-to-jira."""
    path = os.path.join(bugs_dir, "bug-index.md")
    lines, _, rows = load(path)
    li, row = find_row(rows, bid)
    link = f"[{key}]({url})"
    if row:
        row["Jira"] = link
        lines[li] = fmt(row)
        save(path, lines)
    bf = bug_file(bugs_dir, bid, row)
    update_bug_file(bf, [("Jira", link)])
    return {"index_row": bool(row), "bug_file": bf}


def cmd_next(a):
    _, _, rows = load(index_path(a))
    n = max(all_ids(a.bugs_dir, rows) or {0}) + 1
    dump({"next_id": f"BUG-{n:03d}"})


def cmd_list(a):
    _, _, rows = load(index_path(a))
    dump({"bugs": [row_dict(c) for _, c in rows]})


def cmd_add(a):
    path = index_path(a)
    lines, _, rows = load(path)
    li, existing = find_row(rows, a.id)
    if existing:
        dump({"ok": False, "error": f"{a.id} already exists in the index"}, code=1)
    if int(a.id.split("-")[1]) in all_ids(a.bugs_dir, rows) and not os.path.isdir(os.path.join(a.bugs_dir, a.folder)):
        dump({"ok": False, "error": f"{a.id} is already used by another folder"}, code=1)
    folder = a.folder.rstrip("/")
    d = {"Bug ID": a.id, "Title": a.title, "Severity": a.severity, "Priority": a.priority, "Status": a.status,
         "Test case(s)": a.test_cases, "Reported on": a.reported_on or ist_cell(), "Jira": NOT_FILED,
         "Folder": f"[{folder}]({folder.replace(' ', '%20')}/{folder.replace(' ', '%20')}.md)"}
    insert_at = (rows[-1][0] + 1) if rows else len(lines)
    lines.insert(insert_at, fmt(d))
    save(path, lines)
    dump({"ok": True, "index": path, "row": d})


def cmd_also_seen(a):
    path = index_path(a)
    lines, _, rows = load(path)
    li, row = find_row(rows, a.id)
    if not row:
        dump({"ok": False, "error": f"{a.id} not found"}, code=1)
    tcs = [t.strip() for t in row["Test case(s)"].split(",") if t.strip()]
    if a.test_case not in tcs:
        tcs.append(a.test_case)
    row["Test case(s)"] = ", ".join(tcs)
    lines[li] = fmt(row)
    save(path, lines)
    bf = bug_file(a.bugs_dir, a.id, row)
    if bf:
        with open(bf, encoding="utf-8") as f:
            text = f.read()
        text = set_field(text, "Test case(s)", row["Test case(s)"])
        note = f"- {a.test_case} ({ist_date()}): {a.note}".rstrip(": ")
        if "## Also seen in" in text:
            text = re.sub(r"(## Also seen in\n(?:.*\n)*?)(?=\n## |\Z)", lambda m: m.group(1).rstrip("\n") + "\n" + note + "\n",
                          text, count=1)
        else:
            text = text.replace("\n## Attachments", f"\n## Also seen in\n{note}\n\n## Attachments", 1)
        write_text_atomic(bf, text)
    dump({"ok": True, "bug": a.id, "test_cases": row["Test case(s)"], "bug_file": bf})


def cmd_set_status(a):
    out = set_status(a.bugs_dir, a.id, a.status)
    if not out["index_row"] and not out["bug_file"]:
        dump({"ok": False, "error": f"{a.id} not found"}, code=1)
    dump({"ok": True, "bug": a.id, "status": a.status, "bug_file": out["bug_file"]})


def cmd_set_jira(a):
    out = set_jira(a.bugs_dir, a.id, a.key, a.url)
    if not out["index_row"] and not out["bug_file"]:
        dump({"ok": False, "error": f"{a.id} not found"}, code=1)
    dump({"ok": True, "bug": a.id, "jira": a.key, **out})


def cmd_slug(a):
    dump({"slug": slug(a.title, 40)})


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bugs-dir", default="bugs")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("next").set_defaults(fn=cmd_next)
    sp.add_parser("list").set_defaults(fn=cmd_list)
    p = sp.add_parser("add")
    for k in ("--id", "--title", "--severity", "--priority", "--test-cases", "--folder"):
        p.add_argument(k, required=True)
    p.add_argument("--status", default="Open")
    p.add_argument("--reported-on")
    p.set_defaults(fn=cmd_add)
    p = sp.add_parser("also-seen")
    p.add_argument("--id", required=True)
    p.add_argument("--test-case", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_also_seen)
    p = sp.add_parser("set-status")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True)
    p.set_defaults(fn=cmd_set_status)
    p = sp.add_parser("set-jira")
    p.add_argument("--id", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--url", required=True)
    p.set_defaults(fn=cmd_set_jira)
    p = sp.add_parser("slug")
    p.add_argument("title")
    p.set_defaults(fn=cmd_slug)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
