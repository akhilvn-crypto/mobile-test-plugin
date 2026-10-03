"""Shared helpers for the file-bugs-to-jira scripts (not run directly).

The bug files, the test case files and the reports are written by execute-mobile-test-cases (and, for web bugs in
the shared bugs/ folder, by the web execute-test-cases with the same formats), so the helpers are reused from the
sibling skill folder (`../execute-mobile-test-cases/scripts`): Markdown table parsing, IST times, atomic writes,
bug_index.py, jira_refs.py (link formats) and xlsx_layout.py (every XLSX write ends with it).
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
EXEC_SCRIPTS = os.path.normpath(os.path.join(SKILL, "..", "execute-mobile-test-cases", "scripts"))
if not os.path.isdir(EXEC_SCRIPTS):
    sys.stderr.write(f"execute-mobile-test-cases scripts not found at {EXEC_SCRIPTS}\n")
    sys.exit(2)
# appended (not inserted first) so this skill's own lint_human_text.py wins over the sibling's file of the same name
if EXEC_SCRIPTS not in sys.path:
    sys.path.append(EXEC_SCRIPTS)

import bug_index  # noqa: E402,F401
import jira_refs  # noqa: E402,F401
from _common import (cell_in, dump, find_manifest, find_root, ist_cell, ist_date, ist_file, load_json,  # noqa: E402,F401
                     parse_testcase_md, read_tables, rel, split_row, utf8_stdio, write_json_atomic,
                     write_text_atomic)

# the sibling scripts put their own folder first on import; move it back to the end so this skill's files win
while EXEC_SCRIPTS in sys.path:
    sys.path.remove(EXEC_SCRIPTS)
sys.path.append(EXEC_SCRIPTS)

BUGS_DIR = "bugs"
SYNC_FILE = os.path.join(BUGS_DIR, "jira-sync.json")
TEST_CASES_DIR = "Test Cases"
REPORTS_DIR = "Test Reports"
BUG_ID_RE = re.compile(r"^(?:BUG-)?0*(\d+)$", re.I)
STORY_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
CASE_RE = re.compile(r"TC-[A-Z0-9]+-[A-Z]+-\d+")
EVIDENCE_DIRS = ("screenshots", "recordings", "logs", "attachments")
PLATFORMS = {"android": "Android", "ios": "iOS"}


def norm_bug_id(text):
    m = BUG_ID_RE.match(str(text or "").strip())
    return f"BUG-{int(m.group(1)):03d}" if m else None


# ---------------------------------------------------------------- bug report

def bug_dirs(bugs_dir=BUGS_DIR):
    out = {}
    for d in sorted(glob.glob(os.path.join(bugs_dir, "BUG-*"))):
        m = re.match(r"(BUG-\d+)_", os.path.basename(d))
        if m and os.path.isdir(d):
            md = os.path.join(d, os.path.basename(d) + ".md")
            if not os.path.exists(md):
                hits = glob.glob(os.path.join(d, m.group(1) + "_*.md"))
                md = hits[0] if hits else None
            if md:
                out[m.group(1)] = md
    return out


def _sections(lines):
    out, cur = {}, None
    for l in lines:
        m = re.match(r"^##\s+(.+?)\s*$", l)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(l)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _list_items(text, numbered=False):
    rx = r"^\s*\d+[.)]\s*(.+)$" if numbered else r"^\s*[-*]\s*(.+)$"
    items = []
    for l in (text or "").split("\n"):
        m = re.match(rx, l)
        if m:
            items.append(m.group(1).strip())
        elif l.strip() and items and l.startswith((" ", "\t")):
            items[-1] += " " + l.strip()
    return items


def parse_bug(path):
    """Bug report MD -> dict (fields by name, sections by heading)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = text.replace("\r\n", "\n").split("\n")
    h1 = next((l[2:].strip() for l in lines if l.startswith("# ")), "")
    m = re.match(r"^(BUG-\d+):\s*(.+)$", h1)
    bid, title = (m.group(1), m.group(2).strip()) if m else (os.path.basename(path).split("_")[0], h1)
    fields = {}
    first_h2 = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    for header, rows, _, _ in read_tables(lines, 0, first_h2):
        if header[:2] == ["Field", "Value"]:
            for _, c in rows:
                if len(c) >= 2:
                    fields[c[0]] = cell_in(c[1])
    secs = _sections(lines)
    folder = os.path.dirname(path)
    files = []
    for sub in EVIDENCE_DIRS:
        for p in sorted(glob.glob(os.path.join(folder, sub, "*"))):
            if os.path.isfile(p):
                files.append(f"{sub}/{os.path.basename(p)}")
    jira = fields.get("Jira", "")
    jm = re.match(r"^\[([A-Z][A-Z0-9]+-\d+)\]\((\S+)\)$", jira)
    return {
        "id": bid, "title": title, "file": path.replace("\\", "/"), "folder": folder.replace("\\", "/"),
        "severity": fields.get("Severity", ""), "priority": fields.get("Priority", ""),
        "platform": fields.get("Platform", "").strip().lower() if fields.get("Platform", "").strip().lower() in PLATFORMS
        else "",
        "status": fields.get("Status", ""), "test_cases": CASE_RE.findall(fields.get("Test case(s)", "")),
        "test_case_file": fields.get("Test case file", ""), "reported_on": fields.get("Reported on", ""),
        "jira_field": jira, "jira_key_in_file": jm.group(1) if jm else None,
        "summary": secs.get("Summary", ""), "description": secs.get("Description", ""),
        "steps": _list_items(secs.get("Steps to Reproduce", ""), numbered=True),
        "expected": secs.get("Expected Result", ""), "actual": secs.get("Actual Result", ""),
        "environment": _list_items(secs.get("Environment", "")),
        "insights": _list_items(secs.get("Insights for Developers", "")) or (
            [secs["Insights for Developers"]] if secs.get("Insights for Developers") else []),
        "also_seen": _list_items(secs.get("Also seen in", "")),
        "attachments_listed": _list_items(secs.get("Attachments", "")),
        "evidence_files": files,
    }


# ---------------------------------------------------------------- test case file / report lookup

def testcase_files(root):
    return sorted(glob.glob(os.path.join(root, TEST_CASES_DIR, "*.md")))


def resolve_testcase_file(bug, root):
    """-> (path or None, how, candidates). 'Test case file' row first, else the newest file holding every case."""
    name = (bug.get("test_case_file") or "").strip()
    if name:
        p = os.path.join(root, TEST_CASES_DIR, os.path.basename(name))
        if not p.lower().endswith(".md"):
            p += ".md"
        if os.path.exists(p):
            return p, "Test case file row", [p]
        return None, f"Test case file row names '{name}', which is not in {TEST_CASES_DIR}/", []
    cases = set(bug.get("test_cases") or [])
    if not cases:
        return None, "the bug lists no test case", []
    hits = []
    for p in testcase_files(root):
        with open(p, encoding="utf-8") as f:
            text = f.read()
        if all(re.search(r"^\|\s*" + re.escape(c) + r"\s*\|", text, re.M) for c in cases):
            hits.append(p)
    if not hits:
        return None, "no test case file contains the bug's test cases", []
    hits.sort(key=os.path.getmtime)
    how = "found by test case ID" + (" (several files match; newest used)" if len(hits) > 1 else "")
    return hits[-1], how, hits


def plan_key_for(md, root):
    try:
        doc = parse_testcase_md(md)
    except OSError:
        return ""
    key, _ = find_manifest(root, md, doc)
    return key or ""


def latest_report(testcase_md, root):
    """Newest Test Reports/*.md whose 'Test case file' row names this test case file -> (md, xlsx or None)."""
    base = os.path.basename(testcase_md)
    found = []
    for p in sorted(glob.glob(os.path.join(root, REPORTS_DIR, "*_Test_Report_*.md"))):
        with open(p, encoding="utf-8") as f:
            head = f.read(4000)
        m = re.search(r"^\|\s*Test case file\s*\|\s*(.*?)\s*\|\s*$", head, re.M)
        if m and m.group(1).strip() == base:
            found.append(p)
    if not found:
        return None, None
    md = found[-1]  # names carry the timestamp, so the last one is the newest
    x = os.path.splitext(md)[0] + ".xlsx"
    return md, (x if os.path.exists(x) else None)


# ---------------------------------------------------------------- .env (REST fallback)

def read_env(path=".env"):
    """Root .env (web framework) and mobile-automation/.env (mobile framework); the first value found wins."""
    env = {}
    for p in dict.fromkeys([path, ".env", os.path.join("mobile-automation", ".env")]):
        if not p or not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#") and m.group(2).strip() and m.group(1) not in env:
                    env[m.group(1)] = m.group(2).strip().strip("\"'")
    return env


# ---------------------------------------------------------------- cross-platform duplicates (mobile)

def _title_words(title):
    t = re.sub(r"^[^-]*-\s*", "", title or "", count=1)  # drop the "<Feature> -" prefix for the comparison
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2 and w not in
            {"the", "and", "for", "with", "after", "when", "not", "does", "app", "screen", "shown", "tap", "tapping"}}


def same_problem(a, b):
    """Two bug titles describe the same problem: same feature prefix and most of the words shared."""
    fa = (a or "").split(" - ")[0].strip().lower()
    fb = (b or "").split(" - ")[0].strip().lower()
    wa, wb = _title_words(a), _title_words(b)
    if not wa or not wb:
        return False
    overlap = len(wa & wb) / max(1, min(len(wa), len(wb)))
    return (fa == fb and overlap >= 0.5) or overlap >= 0.75
