#!/usr/bin/env python3
"""Lint a build-mobile-test-cases Markdown file (one platform per file).

  python lint_testcases.py <file.md>                 lint; exit 1 on errors (2 on unreadable file)
  python lint_testcases.py <file.md> --strict        warnings also fail
  python lint_testcases.py <file.md> --json          findings as JSON
  python lint_testcases.py <file.md> --write-matrix  (re)build every flow's coverage matrix from the IDs and add the
                                                     mobile conditions table skeleton where it is missing, then lint
  python lint_testcases.py <file.md> --stats         JSON counts per flow / level / type, max running number

Checks: front-matter keys and mobile tags, header rows (Plan key, Platform, Device, OS version, App version and
build) and the out-of-scope line, column headers and order, ID format and uniqueness, the five in-scope levels
(CMP, INT, E2E, UI, MOB; API, SEC and ACC are reserved and flagged), banned automation and mobile tool terms,
network words, filler, step count/length, "Verify that" descriptions, duplicate titles, empty required columns,
MOB preconditions, Execution Status values, Executed On format, unmasked secrets, coverage-matrix gaps and the
mobile conditions table of every flow.
md_to_xlsx.py imports parse_md() from here.
"""
import argparse
import json
import re
import sys
from collections import OrderedDict

COLUMNS = ["Test Case ID", "Test Case Title", "Test Description", "Preconditions", "Test Steps", "Test Data",
           "Expected Result", "Actual Result", "Execution Status", "Comments", "Created By", "Reviewed By",
           "Executed By", "Executed On", "Execution Defects"]
LEVELS = OrderedDict([("CMP", "Component"), ("INT", "Integration"), ("E2E", "End-to-end"),
                      ("UI", "UI/UX"), ("MOB", "Mobile conditions")])
RESERVED_LEVELS = ("API", "SEC", "ACC")  # out of scope for mobile for now; the codes stay reserved
CONDITIONS = ["App lifecycle", "Permissions", "Interruptions", "Network", "Orientation", "Device settings",
              "Navigation"]
HEADER_ROWS = ["Plan name", "Plan key", "Platform", "Device", "OS version", "App version and build"]
OUT_OF_SCOPE_LINE = "Out of scope for now: API, security and accessibility"
PLATFORM_TAGS = {"android", "ios"}
TYPES = OrderedDict([("POS", "Positive"), ("NEG", "Negative"), ("EDG", "Edge"), ("BND", "Boundary"),
                     ("VAL", "Validation"), ("ERR", "Error")])
STATUSES = ["PASS", "FAIL", "IN PROGRESS", "PENDING", "BLOCKED"]
TAGS = ["[NEW]", "[UPDATED]", "[OBSOLETE]"]
ID_RE = re.compile(r"^TC-(CMP|INT|E2E|UI|MOB)-(POS|NEG|EDG|BND|VAL|ERR)-(\d{3,})$")
ID_FIND = re.compile(r"TC-(?:CMP|INT|E2E|UI|MOB)-(?:POS|NEG|EDG|BND|VAL|ERR)-\d{3,}")
# API, SEC and ACC cases are out of scope for mobile for now (a number used by one is never reused)
LEGACY_API_RE = re.compile(r"^TC-(?:API|SEC|ACC)-(POS|NEG|EDG|BND|VAL|ERR)-(\d{3,})$")
EXEC_ON_RE = re.compile(r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2} IST$")
FLOW_MARK = re.compile(r"<!--\s*flow-key:\s*([a-z0-9-]+)\s*-->")
NA_RE = re.compile(r"^N/?A\s*[–—:\-]+\s*(.+)$", re.I)

BANNED = [
    (r"\bplaywright\b", "Playwright"), (r"\blocators?\b", "locator"), (r"\bselectors?\b", "selector"),
    (r"\bxpath\b", "XPath"), (r"\bDOM\b", "DOM"), (r"\bgetBy\w*", "getByRole"), (r"\btest[ -]?ids?\b", "test id"),
    (r"data-testid", "test id"), (r"page\.goto", "page.goto"), (r"\bwaitFor\w*", "waitFor"),
    (r"\bheadless\b", "headless"), (r"\bfixtures?\b", "fixture"), (r"\bHARs?\b", "HAR"), (r"\.har\b", "HAR"),
    (r"\bsnapshots?\b", "snapshot"), (r"(?<!stack )\btraces?\b", "trace"), (r"\bscreenshots?\b", "screenshot"),
    (r"\bexplor(ation|ed|er)\b", "exploration files"), (r"page-structure", "exploration files"),
    (r"observations\.md|api-calls\.md|console-errors\.md|manifest\.json", "exploration files"),
    (r"\b(recorded|recording of the|captured) videos?\b|\bvideos?/", "video reference"),
    (r"\bassert(s|ed|ion)?\b", "assert"),
]
# mobile tool terms (plan section 6.7). Exact app text in double quotes is exempt, so a message such as
# "Your session has expired." can still be quoted.
MOBILE_BANNED = [
    (r"\bappium\b", "Appium"), (r"\bwebdriver(io)?\b|\bwdio\b", "WebdriverIO"), (r"\bdrivers?\b", "driver"),
    (r"\bcapabilit(y|ies)\b", "capabilities"), (r"\bsessions?\b", "session"), (r"\bresource[ -]?ids?\b", "resource id"),
    (r"\bcontent[ -]?desc(ription)?s?\b", "content description"), (r"\baccessibility[ -]?ids?\b", "accessibility id"),
    (r"\buiselector\b|\buiautomator2?\b|\bxcuitest\b", "UiSelector"), (r"\bwidget[ -]?tree\b", "widget tree"),
    (r"\bcontexts?\b", "context"), (r"\bnative_app\b", "NATIVE_APP"), (r"\bflutter\b", "FLUTTER"),
    (r"\badb\b", "adb"), (r"\blogcat\b", "logcat"), (r"\bsemantics?\b", "Semantics"),
]
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”")
UI_ONLY_BANNED = [(r"\bnetwork (call|request)s?\b", "network call"), (r"\bXHR\b", "XHR"),
                  (r"\bintercept(s|ed|ing)?\b", "intercept"), (r"\bmock(s|ed|ing)?\b", "mock")]
FILLER = [(r"\bensure that\b", "ensure that"), (r"\bsuccessfully validate", "successfully validate")]
SECRET_LABEL = re.compile(r"pass(word)?|pwd|token|secret|otp|api[ _-]?key|pin\b", re.I)
MASKED = re.compile(r"^(\*{3,}|<[^>]*>|\[[^\]]*\]|masked|from test plan.*|n/?a|—|-)$", re.I)
MAX_STEP_CHARS = 120
TEXT_COLS = ["Test Case Title", "Test Description", "Preconditions", "Test Steps", "Test Data",
             "Expected Result", "Comments"]


# ---------------------------------------------------------------- parsing

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
    """Yield (header_cells, rows[(line_no, cells)], first_line, last_line) for tables in lines[start:end]."""
    i = start
    while i < end:
        if lines[i].lstrip().startswith("|") and i + 1 < end and is_sep(lines[i + 1]):
            header = split_row(lines[i])
            rows, j = [], i + 2
            while j < end and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, split_row(lines[j])))
                j += 1
            yield header, rows, i, j - 1
            i = j
        else:
            i += 1


def parse_front_matter(text):
    fm = OrderedDict()
    m = re.match(r"^﻿?---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None, 0
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
    return fm, m.group(0).count("\n")


def parse_md(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, _ = parse_front_matter(text)
    lines = text.replace("\r\n", "\n").split("\n")
    doc = {"path": path, "front_matter": fm, "lines": lines, "h1": None, "header": OrderedDict(),
           "version_history": [], "flows": [], "sections": OrderedDict(), "legend": False,
           "out_of_scope_line": any(OUT_OF_SCOPE_LINE.lower() in l.lower() for l in lines[:80])}
    h2 = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    h1 = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    doc["h1"] = h1
    first_h2 = h2[0][0] if h2 else len(lines)
    for header, rows, _, _ in read_tables(lines, 0, first_h2):
        if header[:2] == ["Field", "Value"]:
            for _, c in rows:
                if len(c) >= 2:
                    doc["header"][c[0]] = c[1]
    for n, (i, title) in enumerate(h2):
        end = h2[n + 1][0] if n + 1 < len(h2) else len(lines)
        mark = None
        for k in range(i + 1, min(i + 4, end)):
            mm = FLOW_MARK.search(lines[k])
            if mm:
                mark = mm.group(1)
                break
        if mark is None:
            doc["sections"][title] = (i, end)
            if title.lower().startswith("version history"):
                for header, rows, _, _ in read_tables(lines, i, end):
                    for ln, c in rows:
                        doc["version_history"].append(OrderedDict(zip(header, c)))
            if title.lower().startswith("legend"):
                doc["legend"] = True
            continue
        flow = {"name": title, "key": mark, "line": i + 1, "start": i, "end": end, "header": None,
                "cases": [], "table_span": None, "matrix": None, "matrix_span": None, "matrix_heading": None,
                "conditions": None, "conditions_span": None, "conditions_heading": None}
        for header, rows, a, b in read_tables(lines, i, end):
            if header and header[0] == "Test Case ID" and flow["header"] is None:
                flow["header"], flow["table_span"] = header, (a, b)
                for ln, c in rows:
                    c = (c + [""] * len(COLUMNS))[:max(len(COLUMNS), len(header))]
                    case = OrderedDict((col, c[k] if k < len(c) else "") for k, col in enumerate(COLUMNS))
                    case["_line"] = ln
                    flow["cases"].append(case)
            elif header and header[0] == "Level" and flow["matrix"] is None:
                flow["matrix_span"] = (a, b)
                mx = OrderedDict()
                for ln, c in rows:
                    lvl = level_code(c[0])
                    mx[lvl or c[0]] = OrderedDict(
                        (type_code(header[k]) or header[k], c[k] if k < len(c) else "")
                        for k in range(1, len(header)))
                flow["matrix"] = mx
                for k in range(a - 1, i, -1):
                    if lines[k].startswith("### "):
                        flow["matrix_heading"] = k
                        break
            elif header and header[0] == "Condition" and flow["conditions"] is None:
                flow["conditions_span"] = (a, b)
                flow["conditions"] = OrderedDict(
                    (c[0], {"covered": c[1] if len(c) > 1 else "", "notes": c[2] if len(c) > 2 else "", "line": ln})
                    for ln, c in rows)
                for k in range(a - 1, i, -1):
                    if lines[k].startswith("### "):
                        flow["conditions_heading"] = k
                        break
        doc["flows"].append(flow)
    return doc


def level_code(s):
    s = s.strip()
    m = re.search(r"\(([A-Z0-9]{2,3})\)", s)
    if m and m.group(1) in LEVELS:
        return m.group(1)
    up = s.upper().strip("* ")
    if up in LEVELS:
        return up
    for code, name in LEVELS.items():
        if s.lower().startswith(name.lower()):
            return code
    return None


def type_code(s):
    up = s.strip().upper().strip("* ")
    if up in TYPES:
        return up
    m = re.search(r"\(([A-Z]{3})\)", s)
    if m and m.group(1) in TYPES:
        return m.group(1)
    for code, name in TYPES.items():
        if s.strip().lower().startswith(name.lower()):
            return code
    return None


def br_lines(cell):
    return [x.strip() for x in re.split(r"<br\s*/?>", cell or "", flags=re.I) if x.strip()]


def is_obsolete(case):
    return case.get("Comments", "").strip().upper().startswith("[OBSOLETE]")


# ---------------------------------------------------------------- matrix

def computed_matrix(flow):
    mx = OrderedDict((lv, OrderedDict((t, []) for t in TYPES)) for lv in LEVELS)
    for c in flow["cases"]:
        m = ID_RE.match(c["Test Case ID"])
        if m and not is_obsolete(c):
            mx[m.group(1)][m.group(2)].append(c["Test Case ID"])
    return mx


def render_matrix(flow):
    comp = computed_matrix(flow)
    old = flow["matrix"] or {}
    archived = flow["cases"] and all(is_obsolete(c) for c in flow["cases"])
    out = [f"### Coverage Matrix – {flow['name']}", "",
           "| Level | " + " | ".join(TYPES) + " |", "|" + "---|" * (len(TYPES) + 1)]
    for lv, name in LEVELS.items():
        cells = []
        for t in TYPES:
            ids = comp[lv][t]
            if ids:
                cells.append(", ".join(ids))
            elif archived:
                cells.append("N/A – flow removed from the test plan (all cases obsolete)")
            else:
                prev = (old.get(lv) or {}).get(t, "")
                nm = NA_RE.match(prev.strip()) if prev else None
                cells.append(prev.strip() if nm and not ID_FIND.search(prev) else "N/A – TODO")
        out.append(f"| {name} ({lv}) | " + " | ".join(cells) + " |")
    return out


def render_conditions(flow):
    """Mobile conditions by flow: one row per condition group, covered by case IDs or 'N/A – <reason>'.
    Existing rows are kept as they are; missing rows get 'N/A – TODO' so a reason or a case must be written."""
    old = flow["conditions"] or {}
    archived = flow["cases"] and all(is_obsolete(c) for c in flow["cases"])
    out = [f"### Mobile Conditions – {flow['name']}", "", "| Condition | Covered by | Notes |", "|---|---|---|"]
    for cond in CONDITIONS:
        row = old.get(cond)
        if archived:
            covered, notes = "N/A – flow removed from the test plan (all cases obsolete)", ""
        elif row:
            obsolete = {c["Test Case ID"] for c in flow["cases"] if is_obsolete(c)}
            ids = [x for x in ID_FIND.findall(row["covered"]) if x not in obsolete]
            covered = ", ".join(ids) if ID_FIND.search(row["covered"]) and ids else (
                row["covered"] if not ID_FIND.search(row["covered"]) else "N/A – TODO")
            notes = row["notes"]
        else:
            covered, notes = "N/A – TODO", ""
        out.append(f"| {cond} | {covered} | {notes} |")
    return out


def write_matrix(path):
    doc = parse_md(path)
    lines = doc["lines"]
    for flow in reversed(doc["flows"]):
        if flow["table_span"] is None:
            continue
        cond = render_conditions(flow)
        if flow["conditions_span"]:
            a = flow["conditions_heading"] if flow["conditions_heading"] is not None else flow["conditions_span"][0]
            lines[a:flow["conditions_span"][1] + 1] = cond
            cond = None
        new = render_matrix(flow)
        if flow["matrix_span"]:
            a = flow["matrix_heading"] if flow["matrix_heading"] is not None else flow["matrix_span"][0]
            b = flow["matrix_span"][1]
            lines[a:b + 1] = new + ([""] + cond if cond else [])
        else:
            b = flow["table_span"][1]
            lines[b + 1:b + 1] = [""] + new + ([""] + cond if cond else [])
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------- lint

def lint(doc):
    F = []

    def add(sev, line, cid, msg):
        F.append({"severity": sev, "line": line, "id": cid, "message": msg})

    fm = doc["front_matter"]
    if fm is None:
        add("ERROR", 1, "", "missing YAML front-matter")
    else:
        for k in ("title", "document_type", "project_id", "document_id", "version", "approved_date", "privacy", "tags"):
            if k not in fm:
                add("ERROR", 1, "", f"front-matter key missing: {k}")
        for k in ("project_id", "document_id", "approved_date"):
            if fm.get(k):
                add("ERROR", 1, "", f"front-matter {k} must be left empty")
        if fm.get("document_type") and fm["document_type"] != "Test Cases":
            add("ERROR", 1, "", "document_type must be 'Test Cases'")
        if fm.get("privacy") and fm["privacy"] != "Confidential":
            add("ERROR", 1, "", "privacy must be 'Confidential'")
        if fm.get("version") and not re.match(r"^V\d+\.\d+$", fm["version"]):
            add("ERROR", 1, "", "version must look like V1.0")
        tags = fm.get("tags") or []
        tags = tags if isinstance(tags, list) else [tags]
        if not ({"test-cases", "qa", "mobile", "flutter"} <= set(tags) and len(PLATFORM_TAGS & set(tags)) == 1):
            add("ERROR", 1, "", "tags must be test-cases, qa, mobile, android or ios (one), flutter")
        if fm.get("title") and not fm["title"].endswith("Test Cases"):
            add("WARN", 1, "", "title should be '<Project Name> – <Test plan name> Test Cases'")
    for row in HEADER_ROWS:
        if row not in doc["header"]:
            add("ERROR", 1, "", f"header table row missing: {row}")
        elif row in ("Plan key", "Platform") and not doc["header"][row].strip():
            add("ERROR", 1, "", f"header row '{row}' must be filled")
    plat = doc["header"].get("Platform", "").strip()
    if plat and plat not in ("Android", "iOS"):
        add("ERROR", 1, "", "header Platform must be 'Android' or 'iOS' (one platform per file)")
    if not doc["out_of_scope_line"]:
        add("ERROR", 1, "", f"missing the line '{OUT_OF_SCOPE_LINE}' in the header part")
    if not doc["legend"]:
        add("ERROR", 1, "", "missing '## Legend' section with Execution Status values")
    if not any(t.lower().startswith("observations") for t in doc["sections"]):
        add("WARN", 1, "", "missing '## Observations and Assumptions' section")
    if not doc["version_history"]:
        add("WARN", 1, "", "missing or empty '## Version History' table")
    if not doc["flows"]:
        add("ERROR", 1, "", "no flow sections found (H2 followed by <!-- flow-key: ... -->)")

    ids, numbers, titles = {}, {}, {}
    for flow in doc["flows"]:
        if flow["header"] is None:
            add("ERROR", flow["line"], "", f"flow '{flow['name']}' has no test case table")
            continue
        if flow["header"] != COLUMNS:
            add("ERROR", flow["line"], "", "test case table columns must be exactly: " + " | ".join(COLUMNS))
        for c in flow["cases"]:
            ln, cid = c["_line"], c["Test Case ID"]
            m = ID_RE.match(cid)
            legacy = LEGACY_API_RE.match(cid)
            if legacy:
                add("ERROR", ln, cid, "API, security and accessibility cases are out of scope for mobile for now "
                                      "(level codes API, SEC, ACC are reserved) - remove this case")
                numbers.setdefault(int(legacy.group(2)), (ln, cid))
            elif not m:
                add("ERROR", ln, cid, "ID must match TC-<LEVEL>-<TYPE>-<NNN>")
            else:
                num = int(m.group(3))
                if cid in ids:
                    add("ERROR", ln, cid, f"duplicate ID (also line {ids[cid]})")
                elif num in numbers:
                    add("ERROR", ln, cid, f"running number {m.group(3)} already used by {numbers[num][1]}")
                ids.setdefault(cid, ln)
                numbers.setdefault(num, (ln, cid))
            for col in ("Test Case ID", "Test Case Title", "Test Description", "Test Steps", "Expected Result",
                        "Execution Status"):
                if not c[col].strip():
                    add("ERROR", ln, cid, f"required column empty: {col}")

            title = c["Test Case Title"]
            if title:
                key = re.sub(r"\s+", " ", title.lower()).strip()
                if key in titles:
                    add("ERROR", ln, cid, f"duplicate title (also {titles[key]})")
                titles.setdefault(key, cid)
                if " - " not in title:
                    add("ERROR", ln, cid, "title must be '<Feature> - <what is verified>'")
                if re.search(r"\[[A-Z ]+\]", title):
                    add("ERROR", ln, cid, "title must not contain tags")
            desc = c["Test Description"]
            if desc and not desc.startswith("Verify that"):
                add("ERROR", ln, cid, "description must start with 'Verify that'")
            if desc and len(re.findall(r"[.!?](\s|$)", desc)) > 1:
                add("WARN", ln, cid, "description should be one sentence")

            steps = br_lines(c["Test Steps"])
            if steps:
                if not all(re.match(r"^\d+[.)]\s+\S", s) for s in steps):
                    add("ERROR", ln, cid, "steps must be numbered lines ('1. ...') separated by <br>")
                if len(steps) > 6:
                    add("ERROR", ln, cid, f"{len(steps)} steps (max 6) - split the case")
                elif len(steps) < 3:
                    add("WARN", ln, cid, f"only {len(steps)} step(s); aim for 3 to 6")
                for s in steps:
                    if len(s) > MAX_STEP_CHARS:
                        add("ERROR", ln, cid, f"step too long ({len(s)} chars > {MAX_STEP_CHARS}): '{s[:50]}...'")

            for dl in br_lines(c["Test Data"]):
                lm = re.match(r"^([^:]{1,40}):\s*(.*)$", dl)
                if not lm:
                    add("WARN", ln, cid, f"test data line should be 'Label: value': '{dl[:40]}'")
                    continue
                if SECRET_LABEL.search(lm.group(1)) and lm.group(2).strip() and not MASKED.match(lm.group(2).strip()):
                    add("ERROR", ln, cid, f"unmasked secret in test data: '{lm.group(1)}' (use ********)")

            status = c["Execution Status"].strip()
            if status and status not in STATUSES:
                add("ERROR", ln, cid, f"Execution Status '{status}' not in {', '.join(STATUSES)}")
            com = c["Comments"].strip()
            # execute-test-cases writes execution notes (blocked reason, retest, manual check, …) into Comments
            exec_note = (c.get("Executed On", "").strip() or status not in ("", "PENDING")
                         or com.lower().startswith(("needs manual check", "test case corrected")))
            if com and not exec_note and not any(com.upper().startswith(t) for t in TAGS):
                add("WARN", ln, cid, "Comments should be empty or start with [NEW], [UPDATED] or [OBSOLETE]")
            for col in ("Created By", "Reviewed By", "Executed By"):
                if c[col].strip():
                    add("WARN", ln, cid, f"{col} should be left empty")
            eo = c["Executed On"].strip()
            if eo and not EXEC_ON_RE.match(eo):
                add("ERROR", ln, cid, "Executed On must be 'dd-mm-yyyy hh:mm:ss IST'")

            blob = "\n".join(c[col] for col in TEXT_COLS)
            for pat, term in BANNED + FILLER:
                if re.search(pat, blob, re.I if term != "DOM" else 0):
                    add("ERROR", ln, cid, f"banned term: '{term}'")
            for pat, term in UI_ONLY_BANNED:
                if re.search(pat, blob, re.I):
                    add("ERROR", ln, cid, f"banned term: '{term}'")
            unquoted = QUOTED.sub('""', blob)
            for pat, term in MOBILE_BANNED:
                if re.search(pat, unquoted, re.I):
                    add("ERROR", ln, cid, f"banned mobile tool term: '{term}' (write what the user does or sees)")
            if m and m.group(1) == "MOB" and not c["Preconditions"].strip() and not is_obsolete(c):
                add("WARN", ln, cid, "MOB case: say in Preconditions what the condition needs (for example "
                                     "'Location permission not yet granted', 'Device in airplane mode')")

        # mobile conditions by flow
        conds = flow["conditions"]
        flow_ids = {c["Test Case ID"] for c in flow["cases"] if not is_obsolete(c)}
        if conds is None:
            add("ERROR", flow["line"], "", f"flow '{flow['name']}' has no '### Mobile Conditions' table "
                                           "(run --write-matrix)")
        else:
            for cond in CONDITIONS:
                row = conds.get(cond)
                if row is None:
                    add("ERROR", flow["line"], "", f"mobile conditions '{flow['name']}': row '{cond}' missing")
                    continue
                cell = row["covered"].strip()
                found = ID_FIND.findall(cell)
                if found:
                    for fid in found:
                        if fid not in flow_ids:
                            add("ERROR", row["line"], fid, f"conditions row '{cond}' lists an ID that is not an "
                                                            "active case of this flow")
                else:
                    nm = NA_RE.match(cell) or re.match(r"^Not applicable\s*[–—:\-]+\s*(.+)$", cell, re.I)
                    if not nm or len(nm.group(1).strip()) < 5 or "TODO" in nm.group(1).upper():
                        add("ERROR", row["line"], "", f"conditions row '{cond}' in '{flow['name']}': list case IDs "
                                                      "or write 'N/A – <reason>'")

        # coverage matrix
        mx = flow["matrix"]
        if mx is None:
            add("ERROR", flow["line"], "", f"flow '{flow['name']}' has no coverage matrix (run --write-matrix)")
            continue
        comp = computed_matrix(flow)
        all_ids = {c["Test Case ID"] for c in flow["cases"]}
        obsolete = {c["Test Case ID"] for c in flow["cases"] if is_obsolete(c)}
        for lv in LEVELS:
            row = mx.get(lv)
            if row is None:
                add("ERROR", flow["line"], "", f"coverage matrix '{flow['name']}' missing level row {lv}")
                continue
            for t in TYPES:
                cell = (row.get(t) or "").strip()
                found = ID_FIND.findall(cell)
                if not found:
                    nm = NA_RE.match(cell)
                    if not comp[lv][t] and (not cell or not nm or len(nm.group(1).strip()) < 5
                                            or "TODO" in nm.group(1).upper()):
                        add("ERROR", flow["line"], "", f"matrix gap in '{flow['name']}' {lv}×{t}: "
                            "list case IDs or write 'N/A – <reason>'")
                for fid in found:
                    if fid not in all_ids:
                        add("ERROR", flow["line"], fid, f"matrix {lv}×{t} lists an ID not in this flow")
                    elif fid in obsolete:
                        add("ERROR", flow["line"], fid, f"[OBSOLETE] case listed in matrix {lv}×{t} (run --write-matrix)")
                    elif not fid.startswith(f"TC-{lv}-{t}-"):
                        add("ERROR", flow["line"], fid, f"ID placed in wrong matrix cell {lv}×{t}")
                missing = set(comp[lv][t]) - set(found)
                for mid in sorted(missing):
                    add("ERROR", flow["line"], mid, f"case missing from matrix cell {lv}×{t} (run --write-matrix)")
    return F


def stats(doc):
    out = {"max_number": 0, "total": 0, "by_level": OrderedDict((l, 0) for l in LEVELS),
           "by_type": OrderedDict((t, 0) for t in TYPES), "tags": {"NEW": 0, "UPDATED": 0, "OBSOLETE": 0},
           "flows": OrderedDict(), "version": (doc["front_matter"] or {}).get("version")}
    for flow in doc["flows"]:
        fs = {"key": flow["key"], "total": 0, "by_level": OrderedDict((l, 0) for l in LEVELS),
              "obsolete": 0, "ids": []}
        for c in flow["cases"]:
            m = ID_RE.match(c["Test Case ID"])
            fs["ids"].append(c["Test Case ID"])
            com = c["Comments"].upper()
            for t in out["tags"]:
                if com.startswith(f"[{t}]"):
                    out["tags"][t] += 1
            legacy = LEGACY_API_RE.match(c["Test Case ID"])
            if legacy:
                out["max_number"] = max(out["max_number"], int(legacy.group(2)))
            if not m:
                continue
            out["max_number"] = max(out["max_number"], int(m.group(3)))
            if is_obsolete(c):
                fs["obsolete"] += 1
                continue
            fs["total"] += 1
            fs["by_level"][m.group(1)] += 1
            out["by_level"][m.group(1)] += 1
            out["by_type"][m.group(2)] += 1
            out["total"] += 1
        out["flows"][flow["name"]] = fs
    return out


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-matrix", action="store_true")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    try:
        if a.write_matrix:
            write_matrix(a.file)
        doc = parse_md(a.file)
    except OSError as e:
        print(f"cannot read {a.file}: {e}", file=sys.stderr)
        sys.exit(2)
    if a.stats:
        json.dump(stats(doc), sys.stdout, indent=2)
        print()
        return
    findings = lint(doc)
    errors = [f for f in findings if f["severity"] == "ERROR"]
    warns = [f for f in findings if f["severity"] == "WARN"]
    if a.json:
        json.dump({"errors": len(errors), "warnings": len(warns), "findings": findings}, sys.stdout, indent=2)
        print()
    else:
        for f in findings:
            idp = f" {f['id']}:" if f["id"] else ""
            print(f"{a.file}:{f['line']}: [{f['severity']}]{idp} {f['message']}")
        print(f"\n{len(errors)} error(s), {len(warns)} warning(s)" + (" - lint passed" if not errors and not (a.strict and warns) else ""))
    sys.exit(1 if errors or (a.strict and warns) else 0)


if __name__ == "__main__":
    main()
