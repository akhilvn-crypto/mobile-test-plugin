---
name: execute-mobile-test-cases
description: Use when the user runs execute-mobile-test-cases with --testcase (and optionally --test-report xlsx). Finds the written mobile test cases (one platform), checks the real device and the app, writes WebdriverIO + TypeScript (Appium) scripts from the stored exploration knowledge, runs them sequentially on the real device and fixes them, updates results in the MD and XLSX, files genuine bugs (with screenshot, MP4 recording and device log), and produces a human-written test report (MD, plus XLSX on request).
---

# execute-mobile-test-cases

`SKILL` below means this skill's base directory (shown as "Base directory for this skill" when it loads; inside the plugin it is `${CLAUDE_PLUGIN_ROOT}/skills/execute-mobile-test-cases`); `BUILD` is the sibling `SKILL/../build-mobile-test-cases`. Run scripts with `python "SKILL/scripts/<name>.py"` from the project root (the current working directory). Run `npx` commands from `mobile-automation/`. Paths contain spaces and en dashes – always quote them. This skill consumes what `build-mobile-test-cases` produced: the test case MD/XLSX in `Test Cases/` and the knowledge in `Exploration/<plan-key>/<platform>/`.

Same structure, phases, rules and output formats as the web `execute-test-cases`; this file states the whole mobile flow.

## 1. Usage

```
/execute-mobile-test-cases --testcase "<file name>" [--test-report xlsx]
```

| Argument | Required | Meaning |
|---|---|---|
| `--testcase "<file name>"` | Yes | The mobile test case `.md` in `Test Cases/` (with or without extension, or a path; the plan name alone picks its newest file – add `_Android` / `_iOS` to choose a platform). A same-named `.xlsx` is updated too |
| `--test-report xlsx` | No | Also generate the test report as Excel. Without it only the MD report. Only `xlsx` is accepted |

Decisions already made (do not ask): WebdriverIO + TypeScript with Appium in `mobile-automation/`; Flutter Integration Driver, native fallback when the build lacks the test server; **real devices only**, one device, cases run **sequentially**; one automatic re-run of a failed case; one dated run folder per plan, platform and day; reuse the stored exploration (no re-exploration); MD first, then XLSX; only genuine bugs are filed; human wording everywhere a person reads; `Executed By` and the report's people fields stay empty; no API, security or accessibility cases in this version.

## 2. Phases

Get one run timestamp at the start: `python "SKILL/scripts/ist_timestamp.py"` → `file`, `cell`, `date`.

### Phase 0 – Locate, device and app readiness
1. `python "SKILL/scripts/find_testcase.py" '<the raw arguments text>'` (one single-quoted string). Exit 2 → print its `error`, `usage` and `available`; **stop**.
2. Keep: `md`, `xlsx`, `test_report_xlsx`, `platform`, `plan_name`, `plan_key`, `exploration_dir`, `platform_dir`, `test_plan_path`, `app` (file path, id, hash, version, build), `device`, `flows`, `suite`, `suite_dir`, `results_dir`, `previous_suite_dir`, `framework_exists`, `wdio_config`.
   - No `exploration_dir` / `has_platform_exploration` false → stop: "No exploration knowledge found for this plan and platform. Run /build-mobile-test-cases first."
   - `test_plan_exists` false → ask the user for the test plan path (it holds the app, device, roles and credentials).
3. Read the test plan's common part: app file / id, device, Appium address, roles and credentials, allowed actions, permissions the tester may grant.
4. `python "SKILL/scripts/check_prerequisites.py" --platform <p> --app "<app>" --device "<device>" --appium-url <url> --install --start-server --server-log "<scratchpad>/appium.log"` – starts the Appium server if it is not running, installs missing Appium drivers, confirms a **real** device is connected (only an emulator/simulator → stop with `A real device is required for now. Please connect one.`). Exit 1 → print `missing` and stop. Remind the user to keep the phone unlocked and awake.
5. `python "SKILL/scripts/device_info.py" --platform <p> --serial <serial> --app "<app>" --expected-hash <app.hash> --install --out "<scratchpad>/device.json"` – records model, OS, screen, language, dark mode, network; installs the app from the plan when it is missing (or a different build is installed); compares the build with the one the exploration used. Keep `environment_lines`. A build different from the explored one → say so in the report's Observations ("the knowledge may be older than the build").
6. Framework: if `framework_exists` is false, bootstrap (`references/framework-structure.md` → Bootstrap): copy `SKILL/assets/framework-template/` (including dot files) to `mobile-automation/` without overwriting, `npm install`, `npx tsc --noEmit`. If it exists, reuse it and never overwrite the user's config. Record what was installed.
7. `.env` (in `mobile-automation/`, git-ignored): `APPIUM_URL`, `PLATFORM`, `DEVICE_UDID=<serial>`, `APP_PATH` / `APP_ID`, `RETRIES=1`, `<ROLE>_USER` / `<ROLE>_PASSWORD` per role (values only here), and `test-data/credentials.map.json` (role → variable **names**). Keep existing values the user put there. Never echo values.
8. **Open a test session**: `cd mobile-automation && npx tsx tools/session-check.ts --platform <p>`.
   - `flutterLayer: true` → `FLUTTER_MODE=integration` in `.env`.
   - `flutterLayer: false`, `nativeLayer: true` → the build does not contain the test dependency: say so, set `FLUTTER_MODE=native`, continue with the native fallback for the cases that allow it (labels, identifiers, visible text); cases that need keys or widget types the accessibility tree does not show become `BLOCKED` with `The app build does not include the test support this case needs (appium_flutter_server); ask the team for a test build.`
   - `ok: false` → environment problem: print the reason (device locked? Appium error?) and stop.

### Phase 1 – Load the test cases
1. `python "SKILL/scripts/parse_testcases.py" "<md>" --out "<scratchpad>/cases.json"` → per flow totals, `to_run_ids`, problems (stop and report them).
2. **Which cases run:** status `PENDING`, `IN PROGRESS`, `BLOCKED` or `FAIL` (retest). `PASS` is not re-run. `[OBSOLETE]` is skipped and left out of the report.
3. **Nothing to run:** skip Phases 2–6. `python "SKILL/scripts/build_report_md.py" "<md>" --check`: `up_to_date` → stop with exactly `All test cases are already passed and the latest report is up to date.` (plus the last report name). Otherwise go to Phase 7.

### Phase 2 – Load exploration knowledge (no new exploration)
Per flow to run: `Exploration/<plan-key>/<platform>/<flow-key>/screens/*.json`, `observations.md`, `testability.md`; screenshots only where a visual reference helps. Also `project-understanding.md`. Note forbidden actions (payments, deletes, messages to real people) and treat cases needing them as manual/blocked.

### Phase 3 – Write the scripts (delegate to `em-qa-mobile:qa-mobile-script-writer`, one per flow, in parallel)
1. Run folder `suite_dir` (`mobile-automation/tests/<Suite>_<YYYY-MM-DD>/`). Same day → reuse it. New day with a `previous_suite_dir` → copy the specs of flows whose cases did not change, then write only new or changed cases.
2. Per flow with cases to run: `parse_testcases.py "<md>" --flow <key> --to-run --out "<scratchpad>/<key>.json"`, then launch `em-qa-mobile:qa-mobile-script-writer` with `skill_dir`, `project_root`, `platform`, `flutter_mode`, flow key/name, `cases_json`, `flow_dir`, `spec_path`, test case file + version, role names, the screen objects other writers are creating, and `existing_spec` when present. Writers run in parallel – they do not need the device.
3. Collect each return: spec path, `manual` cases (→ `PENDING` + `Needs manual check: <reason>`, not a failure), `knowledge_gaps` (→ report testability observations), `doubts`. Confirm yourself: `npx tsc --noEmit` passes and every case ID to run appears in an `it('<ID> - …')` title.

### Phase 4 – Execute and fix (the QA loop, sequential on the one device)
Note the run start time (ISO, UTC) for Phase 5a. **Only one thing drives the device at a time**: the suite run, a single-case re-run, a reviewer reproduction or an Appium MCP look – never two together.
1. **Retest of bugs filed in Jira first.** If `bugs/jira-sync.json` exists: `python "SKILL/scripts/retest_evidence.py" ids --to-run "<scratchpad>/cases.json"` → `grep`. When it is not empty run those cases with retest evidence kept even when they pass, then the rest:
   `RETEST_EVIDENCE=1 npx wdio run <wdio_config> --spec "<suite rel>/*.spec.ts" --mochaOpts.grep "<grep>"` and `npx wdio run <wdio_config> --spec "<suite rel>/*.spec.ts" --mochaOpts.grep "<grep>" --mochaOpts.invert`.
   Otherwise run per flow: `npx wdio run <wdio_config> --spec "<suite rel>/<flow>.spec.ts"` (so results can be written after each flow). PowerShell sets variables with `$env:RETEST_EVIDENCE='1';`.
2. Read `<results_dir>/results.json` (statuses `passed`, `failed`, `manual`, `blocked`; `flaky`, `evidenceFiles`, `appCrashed`, `crashLines`, `appState`). A session that cannot start (device gone, Appium down) → environment problem → affected cases `BLOCKED`.
3. Triage every failure with `references/failure-triage.md`:

| Cause | Action |
|---|---|
| Script problem (control not found, scroll/keyboard, gesture missed, wrong wait, unanswered pop-up) | Fix (yourself, or re-invoke the script writer with a `fix_request`), re-run that case only (`--mochaOpts.grep "<ID>"`). Max **3 attempts** per case |
| Environment problem (device disconnected or locked, server error, device frozen, app cannot be installed, no network on the device) | `BLOCKED`, Comment with the reason. Not a bug |
| Test case problem | Correct the wording via `corrections`, Comment `Test case corrected: …`, run again |
| **App crash or freeze** | Candidate bug: reproduce again from a fresh app state before filing (Phase 5) |
| Genuine bug candidate | Phase 5 |
| Still failing after 3 attempts, unclear | `BLOCKED`, `Could not be automated: <reason>`. Not a bug |

4. Outdated knowledge for one screen → look at **that screen only** (Appium MCP, own session, deleted after), fix the screen object, then `refresh_exploration.py --plan-dir … --platform <p> --flow … --screen … --new-json … --reason … --run-ts <ts>`. Add an observation for the report.
5. `flaky: true` (failed, then passed on the automatic re-run) → `PASS` with Comment `Passed on retry, intermittent. Worth watching.`; list it under Observations.
6. `manual` entries → `PENDING` with `Needs manual check: <reason>` (shown as `UNEXECUTED`). `blocked` entries → `BLOCKED` with the reason.
7. Evidence of passing cases is discarded automatically; failed attempts keep a screenshot, the MP4 recording and the device log excerpt. While looking at them, note UX suggestions (`references/ux-suggestions.md`, max 5) – keyboard covering fields, behaviour after rotation, layout on the device.

### Phase 5 – Verify and file genuine bugs (delegate to `em-qa-mobile:qa-mobile-bug-reviewer`, one at a time)
1. For each candidate launch `em-qa-mobile:qa-mobile-bug-reviewer` with the case, the failure in plain words, the `results.json` entry, `spec_path`, `wdio_config`, `platform`, `device_serial`, `other_real_devices` (other connected real devices from `check_prerequisites.py` → `devices`; usually empty), `appium_url`, `project-understanding.md`, `flow_dir`, role name, run time (IST cell), `environment_lines`, `testcase_file`, `skill_dir` and `build_skill_dir` (BUILD). The device is the reviewer's while it works.
2. A candidate becomes a bug only if all hold: fails again from a fresh app state (a crash: twice); not caused by the script, the device or the test data; expected result backed by the case and (where available) the PRD/BRD; not a duplicate. The reviewer files `bugs/BUG-<NNN>_<slug>/` (report with Platform, Test case file and Jira rows and the mobile Environment section; `screenshots/`, `recordings/` MP4, optional `logs/`), adds the index row and passes `lint_human_text.py`. The report always names the device; with a second real device it says whether it happened on one or both.
3. Verdicts: `genuine` → case `FAIL`, Execution Defects = bug ID, Actual Result = the reviewer's sentence. `duplicate` → `FAIL`, existing bug ID, Comment `Same problem as BUG-xxx.`. `not a bug` → back to triage.
4. **Retest:** a case that was `FAIL` with a bug and now passes keeps the bug ID in Execution Defects.
   - Bug **not** in `bugs/jira-sync.json`: Comment `Retest passed. BUG-007 can be closed.` and `python "SKILL/scripts/bug_index.py" set-status --id BUG-007 --status "Fixed - verified"`.
   - Bug filed in Jira: Phase 5a decides (`Retest passed. PROJ-45 closed.` or `Retest passed. BUG-007 can be closed.`).
   - A case linked to a bug already `Closed in Jira` fails again → file a **new** bug whose Description says "This looks like PROJ-45, which was closed on <date>."

### Phase 5a – Close fixed bugs in Jira (only when `bugs/jira-sync.json` exists)
1. `python "SKILL/scripts/retest_evidence.py" collect --results "<results_dir>/results.json" --since <run start ISO>` → `candidates` (every linked case passed on a fresh first attempt; the passing-run screenshot and recording copied to `bugs/<bug>/retest/`) and `stay_open`.
2. Candidates: load the `em-qa-mobile:file-bugs-to-jira` skill and follow its `references/closing-fixed-bugs.md` (the retest comment names the device, OS and build of this run from `device.json`).
3. Connector not connected or no direct close → `close_pending`; the run continues and the summary says what is needed.

### Phase 6 – Update the results (MD first, then XLSX)
1. Write the results file (`references/results-update.md`).
2. `python "SKILL/scripts/update_results.py" "<md>" --results "<file>" [--xlsx "<xlsx>"]` (Jira links kept from `bugs/jira-sync.json`; MD backup to `Test Cases/.history/`; XLSX by header name, layout refreshed).
3. Do this **after each flow** finishes so an interrupted run keeps its results.
4. `python "SKILL/scripts/lint_human_text.py" --testcase "<md>"` → fix any wording error and update again.

### Phase 7 – Test report and summary
1. Write the report context (`references/test-report.md`): summary (3–5 sentences, naming the device), environment, `device`, `os_version`, `build`, `network` (from `device.json`), observations (intermittent results, corrected cases, refreshed screens, a build different from the explored one, the native fallback if used), `testability` (from the flows' `testability.md` and the writers' `knowledge_gaps`), `device_results` (one device / both devices for a bug), up to 5 UX suggestions, plain reasons for blocked/unexecuted cases, and a version comment.
2. `python "SKILL/scripts/build_report_md.py" "<md>" --context "<ctx.json>"` → `Test Reports/<Plan>_<Platform>_Test_Report_<ts>.md`, data file in `Test Reports/.data/`, version continued per plan and platform.
3. Only with `--test-report xlsx`: `python "SKILL/scripts/build_report_xlsx.py" --data "<data file>"` → same name `.xlsx` (3 sheets, template layout; Description and Version History comment carry platform, device and build).
4. `python "SKILL/scripts/lint_human_text.py" --report "<report.md>" --bugs bugs --testcase "<md>"` → fix every finding until it passes. A rebuilt report gets a new timestamp; delete only the report you just created and are replacing in this same step, never an earlier one.
5. If any screen was refreshed, make sure `Exploration/<plan-key>/runs/<ts>/changes.md` mentions it.
6. Print the final summary (§6).

## 3. Rules
- Columns are always found by header name; IDs are the only key between test cases, scripts, results, bugs and the report.
- Test titles start with the case ID: `TC-MOB-NEG-014 - Store finder - location permission denied`.
- Each case starts from its declared app state (`fresh install`, `logged out`, `logged in`) and never depends on another case.
- `PASS` cases are skipped; `[OBSOLETE]` cases are skipped and left out of the report. `PENDING` shows as `UNEXECUTED` in the report.
- Reports and test case history copies are never overwritten. Bug IDs are never reused (one running `BUG-nnn` across web and mobile).
- Ask the user only when something is genuinely ambiguous: no test plan path, credentials missing for a role the cases need, a case that needs a destructive action the plan does not clearly allow.

## 4. Guardrails
- Real devices only; never an emulator or simulator. Never change device settings to make a case pass; put back anything a case changed (orientation, network).
- Credentials only in `mobile-automation/.env`. Never in scripts, test cases, bug reports, reports, chat output, screenshots, recordings or logs; scrub device logs before they leave `test-results/`.
- Stay inside the plan's app and flows. No destructive actions unless the plan explicitly allows them.
- Unique data for create flows.
- Never edit an expected result just to make a case pass.
- Never file a bug from a script failure, an environment or device problem, test data or an intermittent result.
- Do not mention Appium, WebdriverIO, scripts, runners or evidence tooling inside test cases, bug reports, the test report or the Actual Result.
- The report states facts and numbers. It does not approve a release and leaves `Executed by`, `Overall testing by lead` and approvals empty.
- Delete every Appium MCP session you open; leave the Appium server running only if it was running before (otherwise say in the summary that it was started and can be stopped).

## 5. References, scripts, assets and agents

| Kind | Path | Use |
|---|---|---|
| Reference | `references/framework-structure.md` | `mobile-automation/` layout, bootstrap, .env, naming, dated folders, commands |
| Reference | `references/script-writing-guide.md` | Specs, screen objects, locator order, app state, MOB through device controls, manual checks |
| Reference | `references/failure-triage.md` | Cause table incl. app crash/freeze, outdated screen, retries, attempt limit, one device |
| Reference | `references/bug-writing-guide.md` | Mobile bug template, Environment, attachments (MP4, logs), wording |
| Reference | `references/results-update.md` | Column mapping, Comments vocabulary, Actual Result wording, update steps |
| Reference | `references/test-report.md` | MD/XLSX report structure with platform/device/build, observations, versioning |
| Reference | `references/ux-suggestions.md` | Mobile UX points, wording, max 5 |
| Script | `scripts/find_testcase.py` | Phase 0: arguments, file lookup, platform, plan key, suite folders |
| Script | `scripts/check_prerequisites.py` | Tools, drivers, Appium server (start), real device, app inspection (same file as in BUILD) |
| Script | `scripts/device_info.py` | Device and app readiness, install, build vs exploration, Environment lines |
| Script | `scripts/parse_testcases.py` | MD tables → JSON by header name; which cases run; app state and condition hints |
| Script | `scripts/update_results.py` | Results → MD (+ summary, history) → XLSX |
| Script | `scripts/build_report_md.py` | MD report + shared data file; `--check` refresh rule; versioning per plan and platform |
| Script | `scripts/build_report_xlsx.py` | XLSX report from the template |
| Script | `scripts/xlsx_layout.py` | Wrapping, alignment, widths, row heights for every XLSX |
| Script | `scripts/lint_human_text.py` | Wording/secret lint for bugs (mobile fields, Environment, MP4), report and Actual Result |
| Script | `scripts/bug_index.py` | Next bug ID, index rows, duplicates, status, `set-jira` (shared with web) |
| Script | `scripts/retest_evidence.py` | Retest case IDs of bugs filed in Jira; closing candidates and `bugs/<bug>/retest/` evidence |
| Script | `scripts/jira_refs.py` | Jira link formats for cells, from `bugs/jira-sync.json` |
| Script | `scripts/refresh_exploration.py` | Refresh one screen's stored knowledge |
| Script | `scripts/ist_timestamp.py` | IST `--file` / `--cell` / `--date` |
| Asset | `assets/framework-template/` | WebdriverIO + TypeScript + Appium framework for `mobile-automation/` |
| Asset | `assets/Test_Report_Template.xlsx` | The user's report template |
| Asset | `assets/test-report-template.md` | MD report skeleton with property keys and the mobile header |
| Asset | `assets/bug-template.md` | Mobile bug report skeleton |
| Asset | `assets/banned-terms.txt` | Terms the wording lint rejects (web + mobile; shared list) |
| Agent | `em-qa-mobile:qa-mobile-script-writer` | Phase 3, one per flow, in parallel |
| Agent | `em-qa-mobile:qa-mobile-bug-reviewer` | Phase 5, per candidate bug, one at a time |
| Skill | `em-qa-mobile:file-bugs-to-jira` | Phase 5a, closing fixed bugs filed in Jira (`references/closing-fixed-bugs.md`) |

Orchestration: locate → prerequisites, device, app, session check → parse → load knowledge → script writers (parallel) → sequential run/triage/fix loop on the device (bug retests first) → bug reviewers one by one → close fixed Jira bugs → results update (per flow) → report → lint → summary.

## 6. Final summary format (printed to the user)

```
execute-mobile-test-cases – <Test plan name> (Android)
Device: Google Pixel 7 (real device), Android 14 – app 2.4.1 (build 123) – Flutter layer: reachable | native fallback
Test case file: Test Cases/<name>.md (+ .xlsx updated)
Framework: created (npm packages, Appium drivers installed) | reused
Scripts: mobile-automation/tests/<Suite>_<date>/ (<n> spec files)

| Flow | Run | PASS | FAIL | BLOCKED | Manual (PENDING) |
|---|---|---|---|---|---|

Bugs raised:
  - BUG-007 (Critical): Notes - App closes after tapping Save (happened on Pixel 7; one device tried)
Duplicates linked: BUG-001 ← TC-…
Retests passed: BUG-002 → Fixed - verified
Closed in Jira: BUG-003 → PROJ-45 (retest comment and evidence added)
Waiting to be closed in Jira: BUG-005 → PROJ-38 – <what is needed>
Blocked: TC-… – <reason>
Left for a manual check: TC-… – <reason>
Screens refreshed in Exploration/: <platform>/<flow>/<screen> – <what changed>

Test report: Test Reports/<name>_Android_Test_Report_<ts>.md  (V1.x)
             Test Reports/<name>_Android_Test_Report_<ts>.xlsx   (only with --test-report xlsx)
```

When nothing ran and the report is up to date, print only: `All test cases are already passed and the latest report is up to date.` and the last report name.
