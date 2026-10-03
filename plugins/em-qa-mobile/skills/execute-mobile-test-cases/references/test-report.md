# Test report (mobile)

Same as web, with the mobile differences below. At the end of every run that has new results, a Test Report is produced: **always as MD** (with property keys), and **also as XLSX** when the user passed `--test-report xlsx`. Both come from one data file, so their numbers always match. The report shows the **current state of every non-obsolete case in the test case file** (one platform), not only the cases run today.

## Commands

```
python "SKILL/scripts/build_report_md.py" "<test cases .md>" --check            # refresh rule, writes nothing
python "SKILL/scripts/build_report_md.py" "<test cases .md>" --context <ctx.json>
python "SKILL/scripts/build_report_xlsx.py" --data "Test Reports/.data/<report>.json"   # only with --test-report xlsx
python "SKILL/scripts/lint_human_text.py" --report "Test Reports/<report>.md" --bugs bugs --testcase "<md>"
```

`build_report_md.py` writes `Test Reports/<PlanName>_<Platform>_Test_Report_<YYYY-MM-DD>_<HH-MM-SS>-IST.md`, the data file `Test Reports/.data/<same name>.json`, and updates `Test Reports/.state.json` (one entry per plan **and platform**). It never overwrites a report.

## Context file (written by you, all keys optional)

```json
{
  "summary": "24 test cases were run on a Pixel 7 (Android 14) across 3 flows. 19 passed and 2 failed. ...",
  "environment": "Test build from the QA channel",
  "device": "Google Pixel 7",
  "os_version": "Android 14",
  "build": "2.4.1 (build 123)",
  "network": "Wi-Fi",
  "observations": ["TC-E2E-POS-002 passed on the second attempt; worth watching.",
                   "The app build differs from the one the exploration was made with (2.4.0 → 2.4.1)."],
  "testability": ["Login screen: the eye icon next to Password has no label or key."],
  "device_results": ["All cases ran on one device. BUG-007 was also tried on a Galaxy A54 (Android 14) and happened there too."],
  "ux_suggestions": ["On the Sign in screen, the keyboard covers the Sign in button. ..."],
  "reasons": {"TC-MOB-NEG-012": "Not executed: a low battery warning cannot be triggered on a real device; needs a manual check."},
  "version_comment": "Updated after retest of 3 failed cases"
}
```

Device, OS and build come from `device_info.py` (Phase 0). Cases left for a manual check are listed automatically under Observations; write `testability` from the flows' `testability.md` and the `knowledge_gaps` the script writers returned.

## MD report: property keys

| Key | Value |
|---|---|
| `title` | `<Project Name> – <Test plan name> <Platform> Test Report` |
| `document_type` | `Test Report` |
| `project_id`, `document_id`, `approved_date` | **empty** |
| `version` | `V1.0` for the first report of the plan and platform, then V1.1, V1.2 … |
| `privacy` | `Confidential` |
| `tags` | `test-report`, `qa`, `mobile`, `android` or `ios`, `flutter` |

## MD report body (in this order)

1. **Header** (Field/Value): test plan, test case file, **Platform**, **Device** (`<model> (real device)`), **OS version**, **App version and build**, environment, network, execution date (IST), `Executed by` (empty), `Overall testing by lead` (empty). Then the line **"Out of scope for now: API, security and accessibility"**.
2. **Summary**: 3 to 5 plain sentences: cases, flows, the device, passed/failed/blocked/not executed, bugs and the most serious one. **No release approval.**
3. **Results at a glance**: Passed, Failed, Total (Passed+Failed), Unexecuted, In Progress, Blocked, Total.
4. **Results by test suite**: one `## TestSuite : <flow>` per flow with `#`, `User Story #`, `User Story Description`, `Test Cases/Test Scenarios`, `Testcase #`, `Status`, `Comments`.
5. **Defects raised**: Bug ID, title, severity, status, test case(s), (Jira), folder link.
6. **Blocked and unexecuted cases**: each with the reason in plain words.
7. **Observations**: general observations (intermittent results, corrected cases, screens that looked different, a build different from the explored one), then **Testability findings**, **Device-specific results**, and **Left for a manual check** (cases the device could not be put in).
8. **UX suggestions**: up to 5, including mobile points (`ux-suggestions.md`).

## Status mapping and row mapping

Same as web: PASS → PASS, FAIL → FAIL, BLOCKED → BLOCKED, IN PROGRESS → IN PROGRESS, PENDING → **UNEXECUTED**, `[OBSOLETE]` left out. Comments: FAIL with a bug `BUG-007 - <bug title>` (with the Jira key once filed); BLOCKED / UNEXECUTED the reason (context `reasons` wins); intermittent pass "Passed on the second attempt; the result is intermittent and worth watching."; `Could not be automated:` becomes `Could not be completed:`.

## XLSX report (copy of `assets/Test_Report_Template.xlsx`)

Structure unchanged from web: Document Control, Version History, the report sheet (`Report Template` renamed `Test Report`), **no 4th sheet**. Differences:
- Document Control **Description**: `Test report for <plan>, Android, Google Pixel 7, Android 14, app 2.4.1 (build 123)`.
- Version History **comment**: the version comment followed by the same platform/device/build line in brackets.
Everything else (title band, header rows, summary formulas, green flow bands, status dropdown and colours, layout tidy) is as on web.

## Versioning and refresh rule

- One version line per plan **and platform**. `.state.json` stores the last report name, results hash and version per `<plan-key>::<platform>`.
- When a run executed nothing (all PASS): `--check`. If `up_to_date`, do not build a report; say "All test cases are already passed and the latest report is up to date." Otherwise build a new one.
- Earlier reports are never overwritten or deleted.

## Wording rules

- Write like a QA lead summarising a test cycle: plain, specific, short sentences, real numbers, the device named.
- Never use the terms in `assets/banned-terms.txt` (tool terms of web and mobile). Say "tested", "checked", "re-tested", "could not be completed", "needs a manual check".
- Human-like: *"24 test cases were run on a Pixel 7 with Android 14 across 3 flows. 19 passed and 2 failed. 2 could not be completed because the phone disconnected, and 1 needs a manual check (incoming call). Two defects were raised, one Critical (BUG-007: the app closes after tapping Save)."*
- The report states facts and numbers. It does not approve a release and does not fill the people fields.
