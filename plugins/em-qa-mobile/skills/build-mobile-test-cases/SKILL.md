---
name: build-mobile-test-cases
description: Use when the user runs build-mobile-test-cases with --project-dir and --test-plan. Reads the project docs and a mobile test plan, checks the Appium/Flutter prerequisites and the real device, explores the Flutter app per flow on a real Android phone or iPhone with the Appium MCP tools, stores the knowledge per platform, and writes human-style mobile test cases (CMP, INT, E2E, UI, MOB) as MD (and XLSX with --xlsx), one file per platform. Re-runs stop without the device when docs, plan and app build are unchanged.
---

# build-mobile-test-cases

`SKILL` below means this skill's base directory (shown as "Base directory for this skill" when it loads; inside the plugin it is `${CLAUDE_PLUGIN_ROOT}/skills/build-mobile-test-cases`). Run scripts with `python "SKILL/scripts/<name>.py"` from the user's project root (the current working directory). Paths may contain spaces – always quote them.

Same structure, output formats and rules as the web `build-test-cases`; this file states the whole mobile flow. Decisions already made (do not ask): Flutter apps, Appium; **real devices only** (no emulators or simulators); Android first, iOS only on a Mac with Xcode; **one platform per file** (a plan naming both gives two suites and two files); one device at a time (flows explored one after another); levels CMP, INT, E2E, UI and MOB only – **no API, security or accessibility cases for now**; one combined MD per platform per run with one H2 section per flow; explore only the plan's flows; exploration in `Exploration/`, never in `Test Cases/`.

## 1. Usage and argument rules

```
/build-mobile-test-cases --project-dir <dir> --test-plan <file> [--xlsx] [--force-full]
```

| Argument | Required | Meaning |
|---|---|---|
| `--project-dir <dir>` | Yes | Folder with project-level docs: PRD, BRD, overviews, specs |
| `--test-plan <file>` | Yes | Platform(s), app file or id, real device, Appium address, credentials and roles, flows, allowed actions, permissions the tester may grant, test data, out-of-scope |
| `--xlsx` | No | Also generate an Excel file per platform. Without it, only MD |
| `--force-full` | No | Ignore previous exploration and explore everything again |

The platform, device, OS and app build come from the **test plan** (and the device), never from arguments. Missing `--project-dir` / `--test-plan`, unknown arguments, a missing/empty folder or a missing plan file: print the error and the usage line, and **stop**.

## 2. Run modes (per platform)

| Mode | When | What happens |
|---|---|---|
| `first` | No exploration for this platform in `Exploration/<plan-key>/manifest.json` | Full analysis, exploration of every flow on the device, V1.0 |
| `rerun` | The platform has an exploration | Stop at once (no device) when docs, plan and app hash are unchanged; light check when only the build changed; explore only what changed |
| `force-full` | `--force-full` | Archive old exploration to `history/`, explore everything; IDs from the previous output are kept and the version is bumped |

`plan-key` = slug of the test plan file name.

## 3. Phases

### Phase 0 – Validate, check prerequisites, detect run mode
1. `python "SKILL/scripts/parse_args.py" '<the raw arguments text>'` → JSON (pass the arguments unchanged as **one single-quoted string**; `''` when empty). Exit 2: print its usage line and stop. Keep `plan_key`, `plan_exploration_dir`, `project_docs`.
2. `python "SKILL/scripts/snapshot_diff.py" plan --test-plan "<plan>"` → plan name, flows and `environment` hints. Read the plan's common part yourself and settle, per platform: **platform(s)**, **app** (APK/IPA path, or package name / bundle id of an installed app), **device** (name and OS), Appium address (default `http://127.0.0.1:4723`), roles, permissions the tester may grant.
   - **No app file and no app identifier → stop:** `The test plan names no app (APK/IPA file or package name / bundle id). Nothing can be explored without the app. Add it to the test plan and run again.`
   - iOS requested on a machine that is not macOS → build only the Android suite if Android is also named, otherwise stop with the message from step 3.
   - No flows, or a split that does not match the plan's intent → ask the user how the flows are named.
3. **Detect the run mode first, without the device.** Per platform: `python "SKILL/scripts/snapshot_diff.py" compare --project-dir "<dir>" --test-plan "<plan>" --plan-dir "<plan_exploration_dir>" --platform <p> --app "<app>" [--force-full]` → `decision`, `needs_device`, the app build fingerprint (`app.hash`, version, build) and per-flow `actions`. An APK/IPA file is hashed on disk; an app given only by package name / bundle id has no fingerprint yet (the device is needed for it), so such a plan never stops here.
   - `stop` (`needs_device: false`): print exactly `No changes detected, existing test cases are still valid.` plus the last output path of that platform, and **end that platform's run** – no files, no device, no prerequisite check.
   - Anything else: go on with step 4.
4. **Prerequisites** (only for platforms that need the device). `python "SKILL/scripts/check_prerequisites.py" --platform <p> --app "<app>" --device "<device from plan>" --appium-url <url> --install --start-server --server-log "<scratchpad>/appium.log"`.
   It checks Node 22+, npm, Java 8+, Android SDK/adb or Xcode, Appium, the drivers (`uiautomator2`/`xcuitest`, `appium-flutter-integration-driver`), the server, a **real** device (emulators/simulators ignored), the app (exists / installed, version, build, hash, Flutter test server inside). `--install` installs only Appium and its drivers; it never installs the Android SDK or Xcode.
   - Exit 1 → print every entry of `missing` exactly (each says what to install or start) and **stop**. Only an emulator/simulator connected → the message is `A real device is required for now. Please connect one.`
   - Show `device_note` (which device is used and why). Remind the user: **keep the phone unlocked and awake during the run** (settings are never changed).
   - `app.test_server` false → say what is missing (the `appium_flutter_server` test build: Android debug test build, iPhone release test build; the message in `checks`) and that exploration continues through the native fallback with limited coverage. Unknown → continue; the explorer checks the Flutter layer.
   - Load the Appium MCP tools now (ToolSearch, query `appium`). None found → stop: `The Appium MCP server is not available. Add it with: claude mcp add appium-mcp -- npx -y appium-mcp@latest (on Windows: claude mcp add appium-mcp -- cmd /c npx -y appium-mcp@latest), restart Claude Code and run again.`
   - Keep per platform: `serial`, device model, OS, app path/id, package, version, build.
   - App given by package name / bundle id: run `compare` again with `--serial <serial>` now (the installed build is fingerprinted on the device); a `stop` then ends the platform as above.
5. Act on the decision:
   - `full` + `--force-full` with an existing folder: `python "SKILL/scripts/snapshot_diff.py" archive --plan-dir "<plan_exploration_dir>" --platform <p>` (flows of that platform + `project-understanding.md` to `history/<ts>/`; manifest copied; nothing deleted).
   - `check-drift` (new app build, nothing else changed): run the **light check** (Phase 3, `light-check`) for the listed flows, then `compare … --serial <serial> --drift -` with the merged light-check JSON on stdin. Result `stop` + `update_app_only` → `snapshot_diff.py update-app --plan-dir … --platform <p> --app "<app>" --serial <serial> --device "<model>" --drift -` (same JSON on stdin), print `No changes detected, existing test cases are still valid.` and `The new app build <version> (build <n>) was checked; no screen changed.`, end. Result `partial` → continue with the final `actions`.
   - `partial`: run the light check for flows whose action is `light-check`, call `compare --drift -` again, use the final `actions`.
6. One run timestamp now: `python "SKILL/scripts/ist_timestamp.py"` → `file`, `cell`, `date`. Reuse it for the whole run (all platforms).

### Phase 1 – Understand the project (main skill)
- First run / force-full / any document changed, added or removed: read **every** document in `--project-dir` in full (PDF in chunks of up to 20 pages; images described; unreadable files listed) and write `Exploration/<plan-key>/project-understanding.md` (purpose, roles, features, business rules with exact messages and limits, integrations, non-functional notes incl. devices/OS/permissions, data and validation rules, gaps and contradictions, unreadable documents; no credentials). On a re-run with changed docs, move the old summary to `Exploration/<plan-key>/history/<ts>/` first and re-read only what changed.
- No document changed: reuse `project-understanding.md`. One summary serves all platforms.

### Phase 2 – Read the test plan
Read the plan yourself. Extract: scope, flows, platforms, app file/id, device, credentials and roles, allowed actions, permissions the tester may grant, supporting data, out-of-scope items, and the **user story / ticket reference and title of each flow** when the plan names one (never invent one). Cross-check against `project-understanding.md`; note contradictions as observations. Keep credentials in memory only.

### Phase 3 – Explore on the device (delegate to `em-qa-mobile:qa-mobile-explorer`, one flow at a time)
Scope: **only the flows named in the plan**. **One explorer at a time** – the device runs one session. Platforms one after another.

| `action` from compare | Explorer mode | Notes |
|---|---|---|
| `full-explore` | `full` | Flow new, edited, first run or force-full |
| `recapture-screens` | `recapture-screens` | Pass only the changed screens (+ `reached_by`) |
| `light-check` | `light-check` | Writes nothing; returns light-check JSON |
| `archive` | — | Flow removed from the plan: no exploration; files stay; manifest marks it `archived` |
| `none` | — | Nothing to do |

Give each explorer: mode, platform, `device_serial`, `appium_url`, app (path or id) and package, flow key/name, the flow's plan text and the plan's common part, `flow_dir` (`Exploration/<plan-key>/<platform>/<flow-key>/`), the credentials, screens (when relevant), `skill_dir`, the `project-understanding.md` path and what Phase 0 found about the test build. Rules for capture, scrubbing and layout: `references/exploration-guide.md`. Re-run rules: `references/incremental-mode.md`. After the last explorer, make sure no Appium MCP session is left open (`appium_session_management` `action=list` / `delete`). Do not write test cases from documents alone unless the user explicitly asks; if they do, say so in Observations and the summary.

### Phase 4 – Design test cases (main skill), then `em-qa-mobile:qa-reviewer`
Per platform:
1. Previous output: `platforms.<p>.last_output_file` in the manifest. Next free number: `python "SKILL/scripts/lint_testcases.py" "<previous.md>" --stats` → `max_number + 1`.
2. Per flow: unchanged flow, no changed screen, docs/common part unchanged → **carry over** its section verbatim (clear old `[NEW]`/`[UPDATED]`). New flow → write it. Changed flow, changed screens, or docs/common part changed in a way that touches the flow → update it (keep valid cases exactly; `[UPDATED]` / `[NEW]` / `[OBSOLETE]` rules in `references/incremental-mode.md`). Archived flow → keep its section, every case `[OBSOLETE]`.
3. Write each new/changed flow section yourself, following `references/writing-style.md`, `test-case-schema.md`, `coverage-matrix.md` and `mobile-conditions.md`, from `project-understanding.md`, the plan and everything in the flow's exploration folder (`observations.md`, `screens/*.json`, `testability.md`, screenshots):
   - levels **CMP, INT, E2E, UI, MOB** only; in each, positive, negative, edge, boundary, validation and error scenarios that are real for the flow (no padding);
   - consider every mobile condition group for the flow (`mobile-conditions.md`); conditions the script cannot create on a real device are still written (they become manual checks at execution);
   - each case's Preconditions state the app state (`App freshly installed.` / `Signed out.` / `Signed in as <role>.`) and, for MOB, the device condition;
   - expected results from what was observed (exact text) or what the docs state; when they disagree, write to the documented behaviour and add the mismatch to Observations;
   - one running number across the file; never renumber or reuse;
   - keep a list of empty matrix cells and not-applicable conditions with a specific reason each, for the reviewer.
   Platforms may share wording, but each file is complete on its own (its own IDs from V1.0).
4. Assemble the MD at its final path (format in §4), in plan order (archived flows last).
5. Launch `em-qa-mobile:qa-reviewer` with the MD path, `skill_dir` = SKILL, the empty-cell and condition reasons, and (re-runs) the IDs that must not change. It runs `lint_testcases.py --write-matrix`, fills the reasons and condition rows, fixes style and re-lints to **0 errors**.
6. Confirm yourself: `python "SKILL/scripts/lint_testcases.py" "<output.md>"` exits 0. Never deliver a file that fails lint.

### Phase 5 – Output (per platform)
1. MD: `Test Cases/<Test plan name>_<Platform>_<YYYY-MM-DD>_<HH-MM-SS>-IST.md` (`Android` or `iOS`; timestamp from Phase 0). Replace `<>:"/\|?*` in the plan name with `-`. If the name exists, wait a second and take a new timestamp – never overwrite.
2. With `--xlsx`: `python "SKILL/scripts/md_to_xlsx.py" "<output.md>"` → same name `.xlsx` (Description cell: `Test cases for <plan>, Android, Pixel 7, Android 14, app 2.4.1 (build 123)`). Without `--xlsx`: MD only.
3. Write `Exploration/<plan-key>/runs/<ts>/changes.md` with one `## <Platform>` section per platform: run mode; docs changed/added/removed; app build old → new; flows new/changed/removed; screens re-captured; cases added/updated/obsoleted (IDs); version old → new; mismatches; whether the Flutter layer was reachable.
4. `python "SKILL/scripts/snapshot_diff.py" update-manifest --project-dir "<dir>" --test-plan "<plan>" --plan-dir "<plan_exploration_dir>" --platform <p> --app "<app>" --serial <serial> --device "<model>" --os-version "<OS>" --flutter-layer true|false --output-file "<output.md>" [--extra-output "<output.xlsx>"] [--story "<flow-key>=<ref>|<title>" …] --version <V> --mode first|partial|force-full --summary "<one line>"`.
5. Print the final summary (§8).

## 4. Output rules

### MD structure (exact layout in `references/test-case-schema.md`)
1. YAML front-matter with the keys in `references/properties.md` (`project_id`, `document_id`, `approved_date` empty; `privacy: Confidential`; tags `test-cases`, `qa`, `mobile`, `android` or `ios`, `flutter`; `version` V1.0 or bumped).
2. `# <Test plan name> – Test Cases` and the Field/Value header: Plan name, **Plan key**, Project, Source documents, **Platform** (`Android`/`iOS`), **Device** (`<model> (real device)`), **OS version**, **App version and build** (`2.4.1 (build 123)`), Run mode, Generated at (IST cell format). Then the line **`Out of scope for now: API, security and accessibility`**.
3. `## Version History` (Version No, Created On, Revised By, Approved By, Comments) – previous rows + one new row.
4. `## Legend` – Execution Status values `PASS, FAIL, IN PROGRESS, PENDING, BLOCKED` (default `PENDING`) and the Comments tags.
5. One `## <Flow name>` per flow, then `<!-- flow-key: <key> -->`, then (only when the plan names one) `User story: <ref> - <title>`, the 15-column table, `### Coverage Matrix – <Flow name>` (5 levels × 6 types; empty cells `N/A – <reason>`), and `### Mobile Conditions – <Flow name>` (7 condition rows: case IDs or `N/A – <reason>`).
6. `## Observations and Assumptions` – mismatches between docs, plan and app (both sides), assumptions, blockers, things not explored and why, whether the Flutter layer was reachable, **testability findings** (controls without a label or key, from `testability.md` – a note for the team, not an accessibility check), conditions written for a manual check.

### Columns, IDs, values
15 columns in the schema order. ID `TC-<LEVEL>-<TYPE>-<NNN>` with LEVEL in CMP, INT, E2E, UI, MOB (API, SEC, ACC reserved, never used now); one running number across the file, never changed on re-runs. Execution Status default `PENDING`. Created By, Reviewed By, Executed By empty. Executed On empty, `dd-mm-yyyy hh:mm:ss IST` when filled.

### Re-run with changes
New timestamped file with **all** flow sections of that platform. Unchanged cases keep IDs and execution columns. Changed `[UPDATED]`, new `[NEW]`, invalid `[OBSOLETE]`. Version bumped with a Version History row.

### XLSX (`--xlsx`)
Built only by `md_to_xlsx.py` from the template: 3 sheets (Test Suite removed), Document Control with Title / Description (`Test cases for <plan>, <Platform>, <device>, <OS>, app <version> (build <n>)`) / Privacy Classification only, Version History rows from the MD, Testcases with blue flow bands, Actual Result after Expected Result, Execution Status dropdown and colours, frozen header. Property keys never go into the XLSX. `xlsx_layout.py` runs last on every workbook (keep the copies in both skills identical).

## 5. Writing rules (summary – full rules in `references/writing-style.md`)
Human QA wording for a manual tester holding the phone: tap, swipe, scroll, long press, rotate the device, minimise / reopen the app, allow or deny the permission, turn on airplane mode. Title `<Feature> - <what is verified>`; description "Verify that…"; 3–6 numbered steps; exact message text; `Label: value` test data with masked secrets. **Never**: Appium, WebdriverIO, driver, capabilities, session, XPath, resource id, content description, accessibility id, UiSelector, widget tree, context, `NATIVE_APP`, `FLUTTER`, or the web tool terms (quoted app text is exempt).

## 6. Guardrails
- Real devices only. Never start or use an emulator or simulator. Never change device settings unless the plan allows it; put back anything changed.
- Use the plan's credentials **only to sign in**. Mask them everywhere, including the manifest, exploration files, logs and test data: `User: <admin>`, `Email: <admin email from test plan>`, `Password: ********`.
- Device logs contain tokens: always run `snapshot_diff.py scrub` (with the credentials as `--secret`) right after saving an excerpt. No network capture (no HAR on mobile).
- Stay inside the plan's flows and the app. No destructive actions unless the plan explicitly allows them.
- If the app behaves differently from the docs, record both and flag the mismatch. Do not guess.
- Never overwrite earlier outputs. Archive replaced exploration files to `history/` – never delete them.
- Do not mention Appium, scripts, recordings, logs or exploration files inside test cases.
- An unchanged re-run creates **no** files and does not open the device.
- Ask the user only when something is genuinely ambiguous (flows cannot be identified, credentials missing for a required role, a flow needs a destructive step the plan does not clearly allow, the plan's device is not connected but another real one is and the plan insists on that model).

## 7. References, scripts and agents

| Kind | Path | Use |
|---|---|---|
| Reference | `references/test-case-schema.md` | Columns, IDs, levels, MD layout (matrix + conditions table) |
| Reference | `references/writing-style.md` | How cases read on mobile (lint enforces the "Do not" list) |
| Reference | `references/coverage-matrix.md` | What each level × type cell covers; conditions table |
| Reference | `references/mobile-conditions.md` | MOB condition groups, what a real device allows |
| Reference | `references/exploration-guide.md` | Appium MCP / adb recipes, what to capture, screen JSON, testability, scrubbing, manifest |
| Reference | `references/incremental-mode.md` | Hashes incl. app build, decision table, light check, ID carry-over, versioning |
| Reference | `references/properties.md` | MD front-matter keys and version bump rules |
| Script | `scripts/parse_args.py` | Validate arguments, create output folders, plan key |
| Script | `scripts/check_prerequisites.py` | Tools, drivers, server (start), real device, app inspection (version, build, hash, test server) |
| Script | `scripts/ist_timestamp.py` | `--file` / `--cell` / `--date` IST timestamps |
| Script | `scripts/snapshot_diff.py` | `plan`, `compare`, `fingerprint`, `archive`, `scrub`, `update-manifest`, `update-app` |
| Script | `scripts/lint_testcases.py` | Lint (exit 1 on errors), `--write-matrix` (matrix + conditions skeleton), `--stats` |
| Script | `scripts/md_to_xlsx.py` | MD → XLSX on `assets/Testcases_Template.xlsx` |
| Script | `scripts/xlsx_layout.py` | Wrapping, alignment, widths, row heights for every XLSX |
| Asset | `assets/Testcases_Template.xlsx` | The user's template |
| Agent | `em-qa-mobile:qa-mobile-explorer` | Phase 3, one flow at a time on the device (full / recapture-screens / light-check) |
| Agent | `em-qa-mobile:qa-reviewer` | Phase 4, once per platform file |

Orchestration: arguments → compare per platform (stop here, without the device, when nothing changed) → prerequisites → project understanding → plan → explorers one by one → design per platform → reviewer → output scripts → manifest.

## 8. Final summary format (printed to the user)

```
build-mobile-test-cases – <Test plan name>
Platform: Android – Pixel 7 (real device), Android 14 – app 2.4.1 (build 123) – Flutter layer: reachable | not reachable (native fallback)
Run mode: First run | Re-run (partial) | Force full | Re-run (no changes – stopped) | New build checked (no changes – stopped)
Files created:
  - Test Cases/<name>_Android_<ts>.md
  - Test Cases/<name>_Android_<ts>.xlsx           (only with --xlsx)
  - Exploration/<plan-key>/runs/<ts>/changes.md
Version: V1.0 (or V1.0 → V1.1)
Out of scope for now: API, security and accessibility

Cases per flow:
| Flow | Total | CMP | INT | E2E | UI | MOB | New | Updated | Obsolete |

Testability findings: <n> controls without a label or key (see Observations)
What changed (re-runs): docs …; app build …; flows …; screens re-captured …
Open questions / mismatches:
  1. …
```

Repeat the block per platform when the plan has two. Take counts from `lint_testcases.py "<output.md>" --stats`. On a stopped re-run print only the run mode line, `No changes detected, existing test cases are still valid.` and the last output path.
