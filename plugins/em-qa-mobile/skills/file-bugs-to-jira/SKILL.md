---
name: file-bugs-to-jira
description: Use when the user runs file-bugs-to-jira (optionally with --bug-id and --link-story), or when execute-mobile-test-cases (or execute-test-cases) needs to close a fixed bug that was filed in Jira. Files the web and mobile bugs from the bugs folder into Jira with the right fields, labels and links, attaches mobile evidence (screenshots, MP4 recordings, device logs) when the Jira REST settings exist, flags the same problem already filed for the other platform, writes the Jira links back to the test cases and test report, and closes verified fixes with a retest comment naming the device, OS and build.
---

# file-bugs-to-jira

`SKILL` below means this skill's base directory (shown as "Base directory for this skill" when it loads; inside the plugin it is `${CLAUDE_PLUGIN_ROOT}/skills/file-bugs-to-jira`); `EXEC` means the sibling `execute-mobile-test-cases` skill folder (`SKILL/../execute-mobile-test-cases`). Run scripts with `python "SKILL/scripts/<name>.py"` from the project root. Paths contain spaces and en dashes — always quote them. Keep working files (bugs.json, meta.json, payloads, comment drafts) in the scratchpad. This skill consumes what `execute-mobile-test-cases` (and the web `execute-test-cases`, same formats) produced: `bugs/` (shared, one running `BUG-nnn`), `Test Cases/` and `Test Reports/`. A bug with a `Platform` row of `Android` or `iOS` is a **mobile bug** and gets the mobile handling below; any other bug is handled exactly as on web. Its scripts reuse EXEC's helpers (`_common.py`, `bug_index.py`, `jira_refs.py`, `xlsx_layout.py`), so the two skills stay in step.

## 1. Usage

```
/file-bugs-to-jira [--bug-id <BUG-ID>] [--link-story <STORY-KEY>]
```

| Argument | Required | Meaning |
|---|---|---|
| `--bug-id <BUG-ID>` | No | File only this bug (`BUG-003`, or `3`). Without it, every bug in `bugs/` that is not in Jira yet |
| `--link-story <STORY-KEY>` | No | Link every bug filed in this run to this story with a `Relates` link. Without it, no link is created |

Two parts: **Part A** files bugs (this command, §2). **Part B** closes fixed bugs; it runs from the next `/execute-mobile-test-cases` (or `/execute-test-cases`) run (§3).

Decisions already made (do not ask): check the connector first and never ask for credentials; project — none → stop, one → confirm, several → pick; always ask for the assignee from a list; each bug part goes to its exact Jira place and is verified after creation; web bugs: no attachments are uploaded (the user attaches them by hand); mobile bugs: screenshots, MP4 recordings and `logs/` files are uploaded through the Jira REST settings when they exist (size limit checked, oversized recordings shrunk with ffmpeg or reported with their local path, never dropped silently), otherwise listed for the user to attach; write the Jira link back to the bug files, test cases and test report (MD and XLSX); close verified fixes on the next test run with a retest comment; human QA wording only; confirm before creating, `Relates` links (never sub-tasks), report the exact failure, retry at most once, never invent a key or link.

## 2. Part A phases

Exact questions, messages and tool parameters: `references/filing-flow.md`.

### Phase 0 – Arguments and bugs (local, no Jira call)
`list_bugs.py [--bug-id …] [--link-story …] --out "<scratchpad>/bugs.json"`. Each bug carries `platform` (`android`/`ios`, empty for web) and, for mobile bugs, `cross_platform` candidates (the same problem already in `bugs/` for the other platform). Unknown bug ID → stop and list the bugs that exist. Malformed story key → ask for the right key, do not guess. Filed only: Status `Open` and not in `jira-sync.json`. Already filed → listed with their key and skipped; with `--link-story` they get only the missing story link. `Fixed - verified` / `Closed` / `Closed in Jira` → skipped. Nothing to do → say so and stop. `close_pending` bugs are finished first (Part B) once the connector is confirmed.

### Phase 1 – Jira connector (first Jira step)
Load the Atlassian tools (`references/connector-tools.md`), call `atlassianUserInfo`. Missing or failing → stop with the connect message from `filing-flow.md`. `getAccessibleAtlassianResources` → site and `cloudId`; several sites → ask which.

### Phase 2 – Project
`getVisibleJiraProjects` (`action: "create"`). None → tell the user and stop. One → ask to confirm; no → stop. Several → list (key, name), marking the story's project and the earlier choice; the user picks. `sync_state.py init`.

### Phase 3 – What the project needs
Issue type `Bug` (or the closest the user accepts); fields via `getJiraIssueTypeMetaWithFields` (`requiredFieldsOnly: false`): allowed priorities, Environment and Severity fields, extra required fields (ask once, save per project; unfillable → stop with the field name). `--link-story`: the story must exist (non-Story types need the user's OK). Link type `Relates` must exist. Write `meta.json`.

### Phase 4 – Assignee
People from `jira_rest.py assignable` (REST configured) or from recent project issues, plus `Me`, `Unassigned` and `Other…` (resolved with `lookupJiraAccountId`, shown back). The choice applies to all bugs; offer "Choose per bug" when several.

### Phase 5 – Confirm before creating
Mobile bugs first: `jira_rest.py check`; when configured, `jira_rest.py limit` → `prepare_attachments.py --bug <ID> --limit <bytes> --out-dir "<scratchpad>/att"` (puts its `note` into `meta.json` → `attachmentNote` for that bug). Then `bug_to_jira.py` per bug (exit 1 = wording/secret problem; fix before going on). Duplicate search per bug, plus the **cross-platform check**: a `cross_platform` candidate (or a Jira search hit with the other platform's label) is shown in Notes as `Possible duplicate: PROJ-45 (iOS)`, and the user chooses per bug: file it anyway (a `Relates` link to the other bug is added) or skip it. One table — Bug, Platform, Title, Severity → Priority, Project, Assignee, Story link, Notes — and a go-ahead. Nothing is created before the user says yes.

### Phase 6 – File each bug, one by one
Label guard (`labels = "<BUG-ID>"`, reuse a found issue) → `createJiraIssue` with the payload → `sync_state.py set --platform <web|android|ios>` **immediately** → `createIssueLink` `Relates` (with `--link-story`; and to the other platform's issue when the user chose "file anyway", recorded with `--related`) → mobile with REST: `jira_rest.py attach --key <KEY> --file …` (the `upload` list), each uploaded file recorded with `sync_state.py set --attached`; tell the user about every file in `not_uploaded` → read back with `getJiraIssue` `*all` and check every item (attachments too, when uploaded); fix with `editJiraIssue`, report what still differs → `writeback.py filed --bug <ID>`. A failing bug is reported with the exact reason and the run continues.

### Phase 7 – Summary
§6 format.

## 3. Part B pointer — closing fixed bugs

`/execute-mobile-test-cases` (and the web `/execute-test-cases`) runs it in its Phase 5a (before the results update) for bugs whose linked cases all passed a fresh retest, using `EXEC/scripts/retest_evidence.py collect` for the local conditions. For a mobile bug the retest comment names the device, OS and build of the retest, and the evidence is the passing-run recording and screenshot in `bugs/<bug>/retest/` (uploaded when the REST settings exist). Steps, the retest comment and the `close_pending` rule: `references/closing-fixed-bugs.md`. It closes automatically, without a question, but only issues recorded in `jira-sync.json` and only when every linked case passed.

## 4. Rules
- One state file, `bugs/jira-sync.json` (`scripts/sync_state.py`): written right after each create and after each later step, so an interruption never creates a duplicate. Together with the `BUG-NNN` label check it is the duplicate guard. Each entry also stores `platform` (`web`, `android`, `ios`), and for mobile `attached` / `related`.
- Field mapping: `references/jira-field-mapping.md` — summary, description sections, Environment (mobile: App, Device (real device), Operating system, Network, Screen, User/role), Severity, Priority, labels (`qa-found`, `<BUG-ID>`, `sev-<severity>`, `<plan-key>`, plus `mobile` and `android`/`ios` for mobile bugs), assignee, `Relates` link.
- Verify after creating; never claim a field or link that the read-back did not show.
- Web bugs: no attachment uploads and no attachment state; the user attaches the files by hand. Mobile bugs: upload through `jira_rest.py attach` only when the REST settings exist; otherwise list the files (`screenshots/`, `recordings/`, `logs/`, and `retest/` when closing) for the user to attach. Never say a file is attached unless the upload and the read-back confirmed it. An oversized recording is shrunk or reported, never silently dropped.
- Write-back: `references/writeback.md` — only the Jira row/column, Execution Defects and report Comments change; earlier versions go to `.history/`. The bug's `Test case file` row picks the right file and test report (it also separates Android and iOS files).
- Retry any failing Jira call at most once. Report Jira's own error text in plain words.
- Ask with the interactive question tool when available, plain text otherwise.

## 5. Guardrails
- Only bugs in `bugs/` are filed, only to the project and assignee the user chose.
- Only issues recorded in `jira-sync.json` (filed by this skill) are ever changed, commented on or closed. Never touch an issue someone else created; a duplicate found in Phase 5 is only mentioned.
- No credentials in Jira text, the state file or the chat. Environment lines show the role, never a password. The REST token lives only in `.env`; never ask for it, print it or copy it.
- Never edit or delete existing Jira content, except corrections made right after creation.
- Run `lint_human_text.py` (or `bug_to_jira.py`, which runs it) on all text before it goes to Jira: no Playwright, Appium, driver, session, script, locator, selector, timeout, trace or similar words (shared web + mobile list).

## 6. References, scripts and assets

| Kind | Path | Use |
|---|---|---|
| Reference | `references/filing-flow.md` | Phases 0–7: exact questions, messages, tool parameters |
| Reference | `references/jira-field-mapping.md` | Bug part → Jira place, priority/severity, labels, required fields |
| Reference | `references/writeback.md` | What changes in which file after filing and closing |
| Reference | `references/closing-fixed-bugs.md` | Part B conditions, order, retest comment, `close_pending` |
| Reference | `references/connector-tools.md` | Atlassian tool names and formats; what the connector cannot do |
| Script | `scripts/list_bugs.py` | Phase 0: parse bugs, compare with the state file, what to file / skip |
| Script | `scripts/bug_to_jira.py` | One bug → Jira payload (summary, markdown description, fields, evidence file list, read-back checks) + lint |
| Script | `scripts/sync_state.py` | `jira-sync.json`: init, set, project fields (atomic) |
| Script | `scripts/jira_rest.py` | REST fallback: check, assignable users, attachment limit, attach (mobile) |
| Script | `scripts/prepare_attachments.py` | Mobile evidence ready for upload: size limit, ffmpeg shrink, not-uploaded note |
| Script | `scripts/writeback.py` | `filed` / `closed`: bug file, index, test case MD/XLSX, report MD/XLSX |
| Script | `scripts/lint_human_text.py` | Wording/secret check for text going to Jira (EXEC's shared banned-terms list) |
| Asset | `assets/jira-description-template.md` | Description layout |
| Asset | `assets/retest-comment-template.md` | Closing comment, with filling notes |
| EXEC script | `retest_evidence.py` | Retest case IDs; closing candidates and local `bugs/<bug>/retest/` evidence |

## 7. Final summary format (printed to the user)

```
file-bugs-to-jira – <KEY - Project name> (<site>)

| Bug | Platform | Jira | Assignee | Story link | Attachments | Problems |
|---|---|---|---|---|---|---|
| BUG-007 | Android | [PROJ-45](https://…/browse/PROJ-45) | <name> | PROJ-10 | 3 uploaded | – |
| BUG-003 | web | [PROJ-46](https://…/browse/PROJ-46) | <name> | PROJ-10 | by hand | – |

Already in Jira (skipped): BUG-001 → PROJ-40
Linked to the other platform's bug: BUG-007 ↔ PROJ-44 (iOS)
Story link added to existing issues: BUG-002 → PROJ-41
Closings finished first: BUG-005 → PROJ-38 closed
Files updated: bugs/…, bugs/bug-index.md, bugs/jira-sync.json, Test Cases/<name>.md (+ .xlsx),
               Test Reports/<report>.md (+ .xlsx)
Not uploaded (too large): BUG-007 → bugs/BUG-007_…/recordings/BUG-007_save-crash.mp4 (kept locally; named in the description)
Evidence to attach by hand: BUG-003 → bugs/BUG-003_…/screenshots/, recordings/
```

Show a link only for keys Jira returned and the read-back confirmed. When nothing was filed, say why in one line.
