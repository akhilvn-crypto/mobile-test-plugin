# Results update (mobile)

Same as web. Results go into the test case files **in place**: the MD first, then the XLSX (if it exists). The structure never changes; only result cells are filled.

## Column mapping (matched by Test Case ID, columns found by header name)

| Column | Value |
|---|---|
| Actual Result | A short human sentence of what happened, written by you, never pasted from the runner. Pass: `As expected.` (plus a detail only if useful). Fail: the exact behaviour seen. Blocked: the reason. Manual: empty |
| Execution Status | `PASS`, `FAIL`, `BLOCKED`, or left `PENDING` for manual checks (`IN PROGRESS` only when a run was interrupted mid-case) |
| Executed On | End time of the case in IST, `dd-mm-yyyy hh:mm:ss IST` (`endedAtIst` in `results.json`). Empty for manual cases |
| Execution Defects | Bug ID(s), comma-separated: `BUG-007`. A bug filed in Jira is written as `[PROJ-45](https://…/browse/PROJ-45) (BUG-007)` (XLSX: `PROJ-45 (BUG-007)` with the cell hyperlink) by `update_results.py` from `bugs/jira-sync.json`; give plain bug IDs in the results file |
| Comments | Short note when needed (see below). `[NEW]`/`[UPDATED]` tags already there are kept |
| Created By, Reviewed By, Executed By | **Not touched** |

## Comments vocabulary

| Situation | Comment |
|---|---|
| Blocked by the environment | `<reason in plain words>`, e.g. `The phone was disconnected during testing.`, `The app build does not include the test support the Flutter screens need; this case needs it.` |
| Could not be automated after 3 attempts | `Could not be automated: <reason>` |
| The device cannot be put in that condition by the test run | `Needs manual check: <reason>`, e.g. `Needs manual check: an incoming call cannot be triggered on a real device.` |
| Passed on the automatic re-run | `Passed on retry, intermittent. Worth watching.` |
| Test case corrected | `Test case corrected: <what changed and why>` |
| Retest of a failed case passed | `Retest passed. BUG-007 can be closed.` (keep `BUG-007` in Execution Defects) |
| Retest passed and the bug was closed in Jira | `Retest passed. PROJ-45 closed.` |
| Duplicate of an existing bug | `Same problem as BUG-007.` |

The report rewrites "Passed on retry …" and "Could not be automated …" into report wording automatically.

## Actual Result wording

- Pass: `As expected.` or one short line when it adds value (`As expected. 3 notes shown.`).
- Fail: what the user saw, in one or two sentences, with exact quoted text. Crash: `The app closes by itself after tapping Save and returns to the home screen. The entry is not saved.`
- Blocked: the reason in plain words.
- Machine-like (not allowed): *"Control not found within 15000 ms: accessibility id Save."*
- Human-like: *"The Save button never appeared on the Edit note screen."*
- Lint: `python "SKILL/scripts/lint_human_text.py" --testcase "<md>"`.

## How to run the update

1. Write the results file (in the scratchpad or `mobile-automation/test-results/<suite>/`, never in `Test Cases/`):
   ```json
   {"results": [
     {"id": "TC-E2E-POS-001", "actual": "As expected.", "status": "PASS", "executed_on": "03-10-2026 14:30:00 IST"},
     {"id": "TC-E2E-POS-004", "actual": "The app closes by itself after tapping Save.", "status": "FAIL",
      "executed_on": "03-10-2026 14:32:00 IST", "defects": "BUG-007"},
     {"id": "TC-MOB-NEG-012", "status": "PENDING", "comments": "Needs manual check: a low battery warning cannot be triggered on a real device."},
     {"id": "TC-UI-EDG-005", "status": "BLOCKED", "comments": "The phone was disconnected during testing."}
   ]}
   ```
   Only the keys present are written; an empty string clears a cell. `corrections` may change Test Description, Preconditions, Test Steps, Test Data or Expected Result and requires a `Test case corrected:` comment.
2. `python "SKILL/scripts/update_results.py" "<md>" --results <file> [--xlsx "<xlsx>"]` – validates first (nothing written on error), backs up to `Test Cases/.history/`, writes the MD with a refreshed `## Latest execution summary`, then the XLSX by header name (dropdown, colours, bands, frozen header and the Document Control / Version History sheets untouched; wrapping and row heights refreshed).
3. Update **after each flow** finishes, so an interrupted run keeps its results; a new run continues because `PASS` cases are skipped.

## Do not touch

- Created By, Reviewed By, Executed By.
- Any column not listed above (except `corrections`).
- The front matter, header table, Version History, Legend, Coverage Matrix, Mobile Conditions and Observations sections.
- The Document Control and Version History sheets of the XLSX.
- `[OBSOLETE]` cases.
