# Write-back

Run after each bug is filed **and verified**: `python "SKILL/scripts/writeback.py" filed --bug <ID>`. After a closing: `writeback.py closed --bug <ID> --closed-on "<cell time>" [--bug-only]`. The Jira key and URL come from `bugs/jira-sync.json`, so record them with `sync_state.py` first. `writeback.py filed --all` re-applies every recorded link (for example after a test case file was regenerated).

Columns are found **by header name** and rows **by Test Case ID**. Before a file changes, its earlier version is copied to the `.history/` folder next to it. Running it twice changes nothing the second time.

## After filing

| File | Change |
|---|---|
| `bugs/BUG-003_…/BUG-003_….md` | `Jira` row → `[PROJ-45](https://…/browse/PROJ-45)`; Status stays `Open`. A bug written before the `Test case file` row existed gets that row (the file found by case ID) |
| `bugs/bug-index.md` | `Jira` column (added to an older index, `Not filed` for the others) |
| `bugs/jira-sync.json` | Written by `sync_state.py` right after creation and after each step |
| Test case MD (the bug's `Test case file`) | **Execution Defects** of every linked case: `[PROJ-45](https://…/browse/PROJ-45) (BUG-003)` |
| Test case XLSX (same name) | **Execution Defects**: `PROJ-45 (BUG-003)` with the issue as the cell hyperlink. A cell holds one link only, so a case with several bugs lists one `PROJ-45 (BUG-003) https://…` line per bug, without a hyperlink |
| Latest test report MD of that test case file (newest `Test Reports/*_Test_Report_*.md` whose `Test case file` row matches) | **Comments** of the linked cases: `[PROJ-45](…) (BUG-003) - <title>`. "Defects raised" gets a `Jira` column. Its `.data/<report>.json` is kept in step |
| Latest test report XLSX (same name) | The same Comments text, plain, with the hyperlink on the cell |

"Linked cases" = the bug's `Test case(s)` plus any case whose Execution Defects already names the bug.

## After closing

| File | Change |
|---|---|
| Bug report | Status `Closed in Jira`, `Closed on` row |
| `bug-index.md` | Status `Closed in Jira` |
| `jira-sync.json` | `status: closed`, `closedOn` |
| Test case MD/XLSX (not with `--bug-only`) | Comments of linked cases that show `PASS`: `Retest passed. PROJ-45 closed.` (`[NEW]`/`[UPDATED]` tags kept) |
| Latest report MD/XLSX (not with `--bug-only`) | Comments of linked rows that show `PASS`: the same note; "Defects raised" Status `Closed in Jira` |

`--bug-only` is used from `/execute-mobile-test-cases` and `/execute-test-cases`: its own results update writes the comment and its new report shows the closed state, so old reports are not touched.

## Rules

- Only these cells change. Statuses, numbers, dropdowns, colours, merged cells, Document Control and Version History sheets, and the people columns stay as they are; every XLSX write ends with `xlsx_layout.tidy_workbook` (row heights refit for the longer text).
- The test report is updated in place; its results hash does not change (`build_report_md.py` ignores Jira keys in the hash), so `--check` still says "up to date".
- A case linked to several bugs shows all of them.
- A file that does not exist (no XLSX, no report yet) is skipped quietly. A case ID missing from a file is listed under `problems` — report it to the user.
- The test file is found through the bug's `Test case file` row, which also keeps Android and iOS files apart (`<Plan>_Android_….md` / `<Plan>_iOS_….md`); the report is the newest one whose `Test case file` row names that file.
- `execute-mobile-test-cases` and `execute-test-cases` keep the links on later runs: `update_results.py`, `build_report_md.py` and `build_report_xlsx.py` read `jira-sync.json` themselves.
