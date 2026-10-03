#!/usr/bin/env python3
"""Write the Jira link (after filing) or the closed state (after closing) back into the local files.

  python writeback.py filed  --bug BUG-003 [--testcase "<test cases .md>"]
  python writeback.py filed  --all                              # re-apply the links of every filed bug
  python writeback.py closed --bug BUG-003 [--closed-on "<dd-mm-yyyy hh:mm:ss IST>"] [--bug-only]

The Jira key and URL come from bugs/jira-sync.json (record them with sync_state.py first).

filed  - bug report: Jira row = [PROJ-45](url) (Status stays Open; a missing "Test case file" row is added)
       - bugs/bug-index.md: Jira column
       - test case MD: Execution Defects of every linked case -> [PROJ-45](url) (BUG-003)
       - test case XLSX (same name): Execution Defects -> "PROJ-45 (BUG-003)" + cell hyperlink
         (several bugs in one cell: one "PROJ-45 (BUG-003) https://…" line each, no hyperlink)
       - latest test report MD of that test case file: Comments of the linked cases get the link, the
         "Defects raised" table gets a Jira column; its .data JSON is kept in step (results hash unchanged)
       - latest test report XLSX: the same Comments text with the link on the cell
closed - bug report: Status "Closed in Jira" + "Closed on" row; bug index Status; jira-sync.json status closed
       - unless --bug-only: Comments of the linked cases in the test case MD/XLSX and the latest report
         (only rows that show PASS) -> "Retest passed. PROJ-45 closed."; report "Defects raised" Status.
         execute-mobile-test-cases (and execute-test-cases) pass --bug-only, because its own results update and new report follow.

Rows are found by Test Case ID and columns by header name. Before a file changes, its earlier version is copied
to the .history/ folder next to it. Nothing else in the files changes. A file that does not exist is skipped
quietly; a case ID that cannot be found in a file is reported.
"""
import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fbj import (BUGS_DIR, SYNC_FILE, bug_dirs, bug_index, cell_in, dump, find_root, ist_cell, ist_file,  # noqa: E402
                  jira_refs, latest_report, load_json, parse_bug, parse_testcase_md, read_tables, rel,
                  resolve_testcase_file, split_row, utf8_stdio, write_json_atomic, write_text_atomic)
import sync_state  # noqa: E402

CLOSED_STATUS = "Closed in Jira"


def backup(path, done):
    """Copy the file to <dir>/.history/<stem>__<ts><ext> once per run."""
    if not path or not os.path.exists(path) or path in done:
        return
    hist = os.path.join(os.path.dirname(os.path.abspath(path)), ".history")
    os.makedirs(hist, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    shutil.copy2(path, os.path.join(hist, f"{stem}__{ist_file()}{ext}"))
    done.add(path)


def md_cell(text):
    return str(text or "").replace("|", "\\|").replace("\n", "<br>")


def join_cells(cells):
    return "| " + " | ".join(cells) + " |"


def retest_comment(key):
    return f"Retest passed. {key} closed."


def merge_comment(old, new):
    m = re.match(r"^\s*(\[(?:NEW|UPDATED)\])\s*", old or "", re.I)
    return f"{m.group(1).upper()} {new}" if m else new


# ---------------------------------------------------------------- test case MD / XLSX

def testcase_md_update(md, bid, cases, sync, mode, done):
    doc = parse_testcase_md(md)
    lines = list(doc["lines"])
    found, changed = set(), []
    key = (sync.get(bid) or {}).get("jiraKey")
    for f in doc["flows"]:
        cm = f["colmap"]
        for c in f["cases"]:
            cid = c.get("Test Case ID")
            if cid not in cases:
                continue
            found.add(cid)
            cells = list(c["raw_cells"]) + [""] * max(0, len(cm) - len(c["raw_cells"]))
            before = list(cells)
            if mode == "filed" and "Execution Defects" in cm:
                cur = cell_in(cells[cm["Execution Defects"]])
                if bid not in jira_refs.bug_ids(cur):
                    cur = (cur + ", " + bid) if cur.strip() else bid
                cells[cm["Execution Defects"]] = md_cell(jira_refs.render_md(cur, sync))
            passed = (c.get("Execution Status") or "").strip().upper() == "PASS"
            if mode == "closed" and "Comments" in cm and key and passed:
                cells[cm["Comments"]] = md_cell(merge_comment(cell_in(cells[cm["Comments"]]), retest_comment(key)))
            if cells != before:
                lines[c["line"]] = join_cells(cells)
                changed.append(cid)
    if changed:
        backup(md, done)
        write_text_atomic(md, "\n".join(lines))
    return {"file": md, "updated": changed, "not_found": sorted(set(cases) - found)}


def testcase_xlsx_update(xlsx, md, bid, cases, sync, mode, done):
    import openpyxl
    from update_results import find_case_sheet, set_defects_cell
    import xlsx_layout
    from _common import COLUMNS, norm_header
    wb = openpyxl.load_workbook(xlsx)
    ws, hrow = find_case_sheet(wb)
    if ws is None:
        return {"file": xlsx, "error": "no sheet with a 'Test Case ID' header"}
    canon = {norm_header(c): c for c in COLUMNS}
    cols = {canon[norm_header(ws.cell(hrow, c).value)]: c for c in range(1, ws.max_column + 1)
            if norm_header(ws.cell(hrow, c).value) in canon}
    md_cases = {c["Test Case ID"]: c for f in parse_testcase_md(md)["flows"] for c in f["cases"]}
    key = (sync.get(bid) or {}).get("jiraKey")
    found, changed = set(), []
    for r in range(hrow + 1, ws.max_row + 1):
        cid = str(ws.cell(r, cols["Test Case ID"]).value or "").strip()
        if cid not in cases:
            continue
        found.add(cid)
        if mode == "filed" and "Execution Defects" in cols:
            set_defects_cell(ws.cell(r, cols["Execution Defects"]),
                             md_cases.get(cid, {}).get("Execution Defects", ""), sync)
            changed.append(cid)
        passed = (md_cases.get(cid, {}).get("Execution Status") or "").strip().upper() == "PASS"
        if mode == "closed" and "Comments" in cols and key and passed:
            cell = ws.cell(r, cols["Comments"])
            cell.value = merge_comment(str(cell.value or ""), retest_comment(key))
            changed.append(cid)
    if changed:
        xlsx_layout.tidy_workbook(wb)
        backup(xlsx, done)
        tmp = xlsx + ".tmp.xlsx"
        wb.save(tmp)
        os.replace(tmp, xlsx)
    return {"file": xlsx, "updated": changed, "not_found": sorted(set(cases) - found)}


# ---------------------------------------------------------------- report MD / data / XLSX

def report_md_update(path, bid, cases, sync, mode, done):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    key = (sync.get(bid) or {}).get("jiraKey")
    found, changed = set(), []
    in_defects = False
    for header, rows, a, _ in list(read_tables(lines, 0, len(lines))):
        sec = next((lines[i] for i in range(a, -1, -1) if lines[i].startswith("## ")), "")
        in_defects = sec.strip() == "## Defects raised"
        if "Testcase #" in header and "Comments" in header:
            ci, si, ki = header.index("Testcase #"), header.index("Status"), header.index("Comments")
            for li, c in rows:
                if len(c) <= max(ci, ki) or c[ci] not in cases:
                    continue
                found.add(c[ci])
                new = list(c)
                if mode == "filed":
                    new[ki] = jira_refs.render_md(c[ki], sync)
                elif mode == "closed" and key and c[si].strip().upper() == "PASS":
                    new[ki] = retest_comment(key)
                if new != c:
                    lines[li] = join_cells([x.replace("|", "\\|") for x in new])
                    changed.append(c[ci])
        elif in_defects and header and header[0] == "Bug ID":
            hdr = list(header)
            if "Jira" not in hdr:  # add the column before Folder (or at the end)
                at = hdr.index("Folder") if "Folder" in hdr else len(hdr)
                hdr.insert(at, "Jira")
                lines[a] = join_cells(hdr)
                lines[a + 1] = "|" + "---|" * len(hdr)
                for li, c in rows:
                    c = list(c) + [""] * max(0, len(header) - len(c))
                    e = sync.get(c[0])
                    c.insert(at, f"[{e['jiraKey']}]({e['url']})" if e else "Not filed")
                    lines[li] = join_cells([x.replace("|", "\\|") for x in c])
                    changed.append(c[0])
                rows = [(li, split_row(lines[li])) for li, _ in rows]
            ji, st = hdr.index("Jira"), hdr.index("Status") if "Status" in hdr else None
            for li, c in rows:
                if c[0] != bid:
                    continue
                new = list(c)
                if mode == "filed" and sync.get(bid):
                    new[ji] = f"[{sync[bid]['jiraKey']}]({sync[bid]['url']})"
                if mode == "closed" and st is not None:
                    new[st] = CLOSED_STATUS
                if new != c:
                    lines[li] = join_cells([x.replace("|", "\\|") for x in new])
                    changed.append(bid)
    if changed:
        backup(path, done)
        write_text_atomic(path, "\n".join(lines))
    return {"file": path, "updated": sorted(set(changed)), "not_found": sorted(set(cases) - found)}


def report_data_update(report_md, bid, cases, sync, mode):
    """Keep Test Reports/.data/<stem>.json in step (comments, Jira fields); results_hash is left as it is."""
    stem = os.path.splitext(os.path.basename(report_md))[0]
    path = os.path.join(os.path.dirname(report_md), ".data", stem + ".json")
    data = load_json(path, None)
    if not data:
        return None
    key = (sync.get(bid) or {}).get("jiraKey")
    for f in data.get("flows") or []:
        for r in f.get("rows") or []:
            if r.get("id") not in cases:
                continue
            if mode == "filed":
                base = r.get("comment_base") or r.get("comment") or ""
                r["comment_base"] = base
                r["comment_md"] = jira_refs.render_md(base, sync)
                r["comment"] = jira_refs.render_plain(base, sync)[0]
                r["links"] = [sync[b]["url"] for b in jira_refs.bug_ids(base) if b in sync]
            elif mode == "closed" and key and r.get("status") == "PASS":
                r["comment"] = r["comment_md"] = r["comment_base"] = retest_comment(key)
    for d in data.get("defects") or []:
        if d.get("id") == bid:
            if sync.get(bid):
                d["jira_key"], d["jira_url"] = sync[bid]["jiraKey"], sync[bid]["url"]
            if mode == "closed":
                d["status"] = CLOSED_STATUS
    write_json_atomic(path, data)
    return path


def report_xlsx_update(xlsx, bid, cases, sync, mode, done):
    import openpyxl
    import xlsx_layout
    wb = openpyxl.load_workbook(xlsx)
    key = (sync.get(bid) or {}).get("jiraKey")
    found, changed = set(), []
    for ws in wb.worksheets:
        idc = comc = stc = None
        for r in range(1, ws.max_row + 1):
            vals = {str(ws.cell(r, c).value or "").strip(): c for c in range(1, min(ws.max_column, 30) + 1)}
            if "Testcase #" in vals and "Comments" in vals:
                idc, comc, stc = vals["Testcase #"], vals["Comments"], vals.get("Status")
                continue
            if not idc:
                continue
            cid = str(ws.cell(r, idc).value or "").strip()
            if cid not in cases:
                continue
            found.add(cid)
            cell = ws.cell(r, comc)
            if mode == "filed":
                value, link = jira_refs.render_plain(str(cell.value or ""), sync)
                cell.value = value or None
                cell.hyperlink = link
                changed.append(cid)
            elif mode == "closed" and key and stc and str(ws.cell(r, stc).value or "").upper() == "PASS":
                cell.value = retest_comment(key)
                cell.hyperlink = None
                changed.append(cid)
    if changed:
        xlsx_layout.tidy_workbook(wb)
        backup(xlsx, done)
        tmp = xlsx + ".tmp.xlsx"
        wb.save(tmp)
        os.replace(tmp, xlsx)
    return {"file": xlsx, "updated": changed, "not_found": sorted(set(cases) - found)}


# ---------------------------------------------------------------- driver

def linked_cases(bug, md):
    """Cases named by the bug, plus cases of the file whose Execution Defects already mention the bug."""
    cases = list(bug["test_cases"])
    if md:
        for f in parse_testcase_md(md)["flows"]:
            for c in f["cases"]:
                if bug["id"] in jira_refs.bug_ids(c.get("Execution Defects", "")) and c["Test Case ID"] not in cases:
                    cases.append(c["Test Case ID"])
    return cases


def run(bid, mode, a, root, sync_all, done):
    files = bug_dirs(BUGS_DIR)
    if bid not in files:
        return {"bug": bid, "ok": False, "error": f"{bid} not found in bugs/"}
    e = sync_all.get(bid)
    if not e or not e.get("jiraKey") or not e.get("url"):
        return {"bug": bid, "ok": False, "error": f"{bid} has no Jira key in jira-sync.json; record it first"}
    sync = jira_refs.load_sync(SYNC_FILE)
    bug = parse_bug(files[bid])
    out = {"bug": bid, "ok": True, "jira": e["jiraKey"], "files": [], "problems": []}
    if a.testcase:
        md = a.testcase if os.path.isabs(a.testcase) else os.path.join(root, a.testcase)
        how = "given with --testcase"
    else:
        md, how, _ = resolve_testcase_file(bug, root)
    backup(files[bid], done)
    backup(os.path.join(BUGS_DIR, "bug-index.md"), done)
    if mode == "filed":
        bug_index.set_jira(BUGS_DIR, bid, e["jiraKey"], e["url"])
        if md and not bug["test_case_file"]:
            with open(files[bid], encoding="utf-8") as f:
                text = f.read()
            text = bug_index.set_or_add_field(text, "Test case file", os.path.basename(md), after=("Test case(s)",))
            write_text_atomic(files[bid], text)
        out["files"] += [rel(files[bid], root), "bugs/bug-index.md"]
    else:
        closed_on = a.closed_on or ist_cell()
        bug_index.set_status(BUGS_DIR, bid, CLOSED_STATUS, extra=[("Closed on", closed_on)])
        data = sync_state.load(SYNC_FILE)
        ent = sync_state.entry(data, bid)
        ent["status"], ent["closedOn"] = "closed", closed_on
        ent.pop("note", None)
        sync_state.save(data, SYNC_FILE)
        out["files"] += [rel(files[bid], root), "bugs/bug-index.md", "bugs/jira-sync.json"]
        if a.bug_only:
            return out
    if not md or not os.path.exists(md):
        out["problems"].append(f"test case file not found ({how}); test cases and report were not updated")
        return out
    cases = linked_cases(bug, md)
    r = testcase_md_update(md, bid, cases, sync, mode, done)
    out["files"].append(rel(md, root))
    if r["not_found"]:
        out["problems"].append(f"not found in {os.path.basename(md)}: {', '.join(r['not_found'])}")
    x = os.path.splitext(md)[0] + ".xlsx"
    if os.path.exists(x):
        r = testcase_xlsx_update(x, md, bid, cases, sync, mode, done)
        out["files"].append(rel(x, root))
        if r.get("error"):
            out["problems"].append(f"{os.path.basename(x)}: {r['error']}")
        elif r["not_found"]:
            out["problems"].append(f"not found in {os.path.basename(x)}: {', '.join(r['not_found'])}")
    rep_md, rep_x = latest_report(md, root)
    if rep_md:
        r = report_md_update(rep_md, bid, cases, sync, mode, done)
        out["files"].append(rel(rep_md, root))
        if r["not_found"]:
            out["problems"].append(f"not found in {os.path.basename(rep_md)}: {', '.join(r['not_found'])}")
        report_data_update(rep_md, bid, cases, sync, mode)
    if rep_x:
        r = report_xlsx_update(rep_x, bid, cases, sync, mode, done)
        out["files"].append(rel(rep_x, root))
        if r["not_found"]:
            out["problems"].append(f"not found in {os.path.basename(rep_x)}: {', '.join(r['not_found'])}")
    return out


def main():
    utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="mode", required=True)
    p = sp.add_parser("filed")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--bug")
    g.add_argument("--all", action="store_true")
    p.add_argument("--testcase")
    p = sp.add_parser("closed")
    p.add_argument("--bug", required=True)
    p.add_argument("--closed-on")
    p.add_argument("--bug-only", action="store_true")
    p.add_argument("--testcase")
    a = ap.parse_args()
    root = find_root()
    sync_all = sync_state.load(SYNC_FILE).get("bugs") or {}
    done = set()
    if getattr(a, "all", False):
        ids = [b for b, e in sync_all.items() if e.get("jiraKey")]
    else:
        ids = [a.bug]
    results = [run(b, a.mode, a, root, sync_all, done) for b in ids]
    ok = all(r["ok"] for r in results)
    dump({"ok": ok, "results": results}, code=0 if ok else 1)


if __name__ == "__main__":
    main()
