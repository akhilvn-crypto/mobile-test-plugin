"""Shared helpers for the execute-mobile-test-cases scripts (not run directly). Also used by file-bugs-to-jira.

- IST timestamps (fixed UTC+05:30 offset, no tzdata needed on Windows)
- Markdown table reading/writing (cells use <br> for line breaks and \\| for pipes)
- Test case MD parsing by header name
- Project paths (Test Cases/, Exploration/, bugs/, Test Reports/, mobile-automation/)
- Platform of a test case file and the matching part of a (mobile) manifest
"""
import hashlib
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")

STATUSES = ["PASS", "FAIL", "IN PROGRESS", "PENDING", "BLOCKED"]
RUN_STATUSES = {"PENDING", "IN PROGRESS", "BLOCKED", "FAIL"}
REPORT_STATUS = {"PASS": "PASS", "FAIL": "FAIL", "BLOCKED": "BLOCKED", "IN PROGRESS": "IN PROGRESS",
                 "PENDING": "UNEXECUTED", "": "UNEXECUTED"}
ID_RE = re.compile(r"^TC-(CMP|INT|E2E|API|SEC|ACC|UI|MOB)-(POS|NEG|EDG|BND|VAL|ERR)-(\d{3,})$")
PLATFORM_NAMES = {"android": "Android", "ios": "iOS"}
FRAMEWORK_DIR = "mobile-automation"
FLOW_MARK = re.compile(r"<!--\s*flow-key:\s*([a-z0-9-]+)\s*-->")
STORY_RE = re.compile(r"^\s*User story:\s*(.+?)\s*$", re.I)
BAD_NAME_CHARS = re.compile(r'[<>:"/\\|?*]')

# canonical column names of the test case table (build-test-cases / build-mobile-test-cases schema)
COLUMNS = ["Test Case ID", "Test Case Title", "Test Description", "Preconditions", "Test Steps", "Test Data",
           "Expected Result", "Actual Result", "Execution Status", "Comments", "Created By", "Reviewed By",
           "Executed By", "Executed On", "Execution Defects"]
# columns this skill writes; everything else is never touched
WRITABLE = ["Actual Result", "Execution Status", "Executed On", "Execution Defects", "Comments"]
PROTECTED = ["Created By", "Reviewed By", "Executed By"]


def utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def dump(obj, code=0):
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
    print()
    if code:
        sys.exit(code)


# ---------------------------------------------------------------- time

def now_ist():
    return datetime.now(IST)


def ist_file(dt=None):
    return (dt or now_ist()).strftime("%Y-%m-%d_%H-%M-%S") + "-IST"


def ist_cell(dt=None):
    return (dt or now_ist()).strftime("%d-%m-%Y %H:%M:%S") + " IST"


def ist_date(dt=None):
    return (dt or now_ist()).strftime("%d-%m-%Y")


def iso_date(dt=None):
    return (dt or now_ist()).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- names and paths

def norm_header(h):
    """'Execution\\nStatus' / 'Executed On (dd-mm-yyyy …)' -> canonical comparable key."""
    h = re.sub(r"\(.*?\)", "", str(h or ""))
    return re.sub(r"\s+", " ", h).strip().lower()


def safe_name(name):
    return BAD_NAME_CHARS.sub("-", name).strip()


def slug(text, maxlen=60):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if len(s) > maxlen:  # cut at a word boundary
        cut = s[:maxlen + 1]
        s = cut[:cut.rfind("-")] if "-" in cut else s[:maxlen]
    return s.rstrip("-") or "item"


def find_root(start=None):
    """Project root = the current working directory (where the command runs)."""
    return os.path.abspath(start or os.getcwd())


def rel(path, root=None):
    root = root or find_root()
    try:
        return os.path.relpath(os.path.abspath(path), root).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_text_atomic(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def write_json_atomic(path, data):
    write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- markdown tables

def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, i = [], "", 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if s[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += s[i]
        i += 1
    cells.append(cur.strip())
    return cells


def is_sep(line):
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$", line))


def read_tables(lines, start, end):
    """Yield (header, rows[(line_index, cells)], first_index, last_index) for tables in lines[start:end]."""
    i = start
    while i < end:
        if lines[i].lstrip().startswith("|") and i + 1 < end and is_sep(lines[i + 1]):
            header = split_row(lines[i])
            rows, j = [], i + 2
            while j < end and lines[j].lstrip().startswith("|"):
                rows.append((j, split_row(lines[j])))
                j += 1
            yield header, rows, i, j - 1
            i = j
        else:
            i += 1


def cell_out(value):
    """Plain text -> one MD table cell (newlines -> <br>, pipes escaped)."""
    v = str(value or "").replace("\r\n", "\n").strip()
    v = v.replace("|", "\\|")
    return "<br>".join(x.strip() for x in v.split("\n"))


def cell_in(value):
    """MD table cell -> plain text."""
    return re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.I).strip()


def join_row(cells):
    return "| " + " | ".join(cells) + " |"


def parse_front_matter(text):
    fm = OrderedDict()
    m = re.match(r"^﻿?---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return fm, ""
    key = None
    for line in m.group(1).splitlines():
        if re.match(r"^\s+-\s*", line) and key:
            if not isinstance(fm[key], list):
                fm[key] = []
            fm[key].append(line.strip()[1:].strip().strip("\"'"))
            continue
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            key = km.group(1)
            v = km.group(2).strip()
            if v.startswith("[") and v.endswith("]"):
                fm[key] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
            else:
                fm[key] = v.strip("\"'")
    return fm, m.group(0)


# ---------------------------------------------------------------- test case MD

def parse_testcase_md(path):
    """Read a build-(mobile-)test-cases MD by header name.

    Returns {path, front_matter, h1, header{Field: Value}, flows[{name, key, user_story_ref,
    user_story_title, h2_index, table:(first,last), colmap{canonical: index}, cases[...]}]}.
    Each case: canonical column -> plain text, plus 'line' (0-based index) and 'raw_cells'.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, _ = parse_front_matter(text)
    lines = text.replace("\r\n", "\n").split("\n")
    doc = {"path": path, "front_matter": fm, "h1": None, "header": OrderedDict(), "flows": [], "lines": lines}
    h2 = [i for i, l in enumerate(lines) if l.startswith("## ")]
    for i, l in enumerate(lines):
        if l.startswith("# ") and doc["h1"] is None:
            doc["h1"] = l[2:].strip()
    first_h2 = h2[0] if h2 else len(lines)
    for header, rows, _, _ in read_tables(lines, 0, first_h2):
        if header[:2] == ["Field", "Value"]:
            for _, c in rows:
                if len(c) >= 2:
                    doc["header"][c[0]] = c[1]
    canon = {norm_header(c): c for c in COLUMNS}
    for n, i in enumerate(h2):
        end = h2[n + 1] if n + 1 < len(h2) else len(lines)
        mark = None
        for j in range(i + 1, min(i + 4, end)):
            m = FLOW_MARK.search(lines[j])
            if m:
                mark = m.group(1)
                break
        if not mark:
            continue
        flow = {"name": lines[i][3:].strip(), "key": mark, "h2_index": i, "user_story_ref": "",
                "user_story_title": "", "table": None, "colmap": {}, "cases": []}
        for j in range(i + 1, min(i + 6, end)):
            sm = STORY_RE.match(lines[j])
            if sm:
                ref, title = split_story(sm.group(1))
                flow["user_story_ref"], flow["user_story_title"] = ref, title
                break
        for header, rows, a, b in read_tables(lines, i, end):
            keys = [norm_header(h) for h in header]
            if "test case id" not in keys:
                continue
            flow["table"] = (a, b)
            flow["colmap"] = {canon[k]: idx for idx, k in enumerate(keys) if k in canon}
            for li, cells in rows:
                case = OrderedDict()
                for col, idx in flow["colmap"].items():
                    case[col] = cell_in(cells[idx]) if idx < len(cells) else ""
                case["line"] = li
                case["raw_cells"] = cells
                flow["cases"].append(case)
            break
        doc["flows"].append(flow)
    return doc


def split_story(text):
    """'#234 - Login page update' -> ('#234', 'Login page update'); 'Login page update' -> ('', ...)."""
    text = text.strip()
    m = re.match(r"^([#A-Za-z]*[-_]?\d[\w-]*|#\w+)\s*[-–—:]\s*(.+)$", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^([#A-Za-z]*[-_]?\d[\w-]*|#\w+)$", text)
    if m:
        return m.group(1), ""
    return "", text


def is_obsolete(case):
    return "[OBSOLETE]" in (case.get("Comments") or "").upper()


def id_parts(cid):
    m = ID_RE.match(cid or "")
    return (m.group(1), m.group(2), int(m.group(3))) if m else ("", "", 0)


# ---------------------------------------------------------------- exploration / manifest

def find_manifest(root, md_path, doc):
    """Locate Exploration/<plan-key>/manifest.json for a test case file.
    Order: 'Plan key' header row -> manifest that lists this file -> manifest with the same plan name."""
    exp = os.path.join(root, "Exploration")
    key = (doc["header"].get("Plan key") or "").strip()
    if key and os.path.exists(os.path.join(exp, key, "manifest.json")):
        return key, os.path.join(exp, key, "manifest.json")
    if not os.path.isdir(exp):
        return key or None, None
    base = os.path.basename(md_path)
    stem = os.path.splitext(base)[0]
    plan_name = (doc["header"].get("Plan name") or "").strip()
    by_name = None
    for d in sorted(os.listdir(exp)):
        mp = os.path.join(exp, d, "manifest.json")
        if not os.path.exists(mp):
            continue
        try:
            m = load_json(mp, {}) or {}
        except (OSError, json.JSONDecodeError):
            continue
        parts = [m] + list((m.get("platforms") or {}).values())
        files = [p.get("last_output_file") or "" for p in parts]
        files += [r.get("output") or "" for p in parts for r in p.get("runs", [])]
        files += [o.get("file") or "" for p in parts for o in p.get("outputs", [])]
        if any(os.path.splitext(os.path.basename(f))[0] == stem for f in files if f):
            return d, mp
        if plan_name and m.get("plan_name") == plan_name and by_name is None:
            by_name = (d, mp)
    if by_name:
        return by_name
    return key or None, None


# ---------------------------------------------------------------- platform (mobile)

def platform_of(doc, md_path=""):
    """'android' | 'ios' | '' from the header row 'Platform', else from the file name (<Plan>_<Platform>_<ts>)."""
    v = (doc.get("header", {}).get("Platform") or "").strip().lower()
    if v in PLATFORM_NAMES:
        return v
    m = re.search(r"_(Android|iOS)_\d{4}-\d{2}-\d{2}_", os.path.basename(md_path or ""), re.I)
    return m.group(1).lower() if m else ""


def platform_part(manifest, platform):
    """The platform's part of a mobile manifest (flows, app build, outputs); the manifest itself for a web one."""
    manifest = manifest or {}
    if "platforms" in manifest:
        return (manifest.get("platforms") or {}).get(platform) or {}
    return manifest


def platform_flow_dir(exploration_dir, platform, flow_key):
    return os.path.join(exploration_dir, platform, flow_key) if platform else os.path.join(exploration_dir, flow_key)
