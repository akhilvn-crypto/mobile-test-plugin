# Jira field mapping

`scripts/bug_to_jira.py` applies this table; the description layout is `assets/jira-description-template.md`. Pass the payload parts to `createJiraIssue` unchanged.

| Bug report part | Jira place | Notes |
|---|---|---|
| Title (H1 without `BUG-003:`) | **Summary** | Exactly as written (max 255 characters) |
| Summary + Description | **Description**, first paragraphs | Plain paragraphs, no heading |
| Steps to Reproduce | Description, `## Steps to Reproduce` | Numbered list, same order |
| Expected Result | Description, `## Expected Result` | |
| Actual Result | Description, `## Actual Result` | Lists inside it are kept |
| Environment | **Environment** field when the create screen has it (ADF bullet list), otherwise Description `## Environment` | Role only, never a password or e-mail. Mobile bugs: the lines `App: <name> <version> (build <n>)`, `Device: <model> (real device)`, `Operating system: …`, `Network: …`, `Screen: …`, `User/role: …` |
| Insights for Developers | Description, `## Notes for Developers` | Requests, status codes and console text quoted as the app produced them |
| Test case(s) + test case file | Description footer "Found in test case(s): … (test case file: …)" | Also the plan key label |
| Severity | **Severity** field when the project has one with a matching value (`{"value": "Major"}`), otherwise label `sev-<severity>` and the line "Severity: Major" in the description | The label is always added |
| Priority | **Priority** `{"name": …}` | High → High, Medium → Medium, Low → Low (also accepts "Major/Normal/Minor" style schemes). Severity Critical → the highest allowed value. No match → field left out, Jira's default applies, said in the summary |
| Assignee | `assignee_account_id` | The user's choice; left out for Unassigned |
| Labels | **Labels** | `qa-found`, `<BUG-ID>`, `sev-<severity>`, `<plan-key>` (spaces become hyphens); mobile bugs also `mobile` and `android` or `ios` |
| Platform | Labels + Environment | From the bug's `Platform` row |
| Issue type | `issueTypeName` | `Bug`, or the type the user accepted in Phase 3 |
| Story key | Issue link `Relates` | One link per bug, never a sub-task |
| Same problem on the other platform | Issue link `Relates` to that issue | Only when the user chose "file anyway" for a possible cross-platform duplicate |
| Screenshots, recordings | Web: — (attached by the user, by hand). Mobile: uploaded with `jira_rest.py attach` when the REST settings exist | Named in the description's `## Attachments` section. Mobile files: `screenshots/` (PNG), `recordings/` (MP4), `logs/` (device log excerpt). The site's limit comes from `jira_rest.py limit`; `prepare_attachments.py` shrinks a too-large MP4 with ffmpeg, or leaves it out and adds the sentence with its local path to the description (`meta.json` → `attachmentNote`) |
| Reporter | — | Jira sets the connected user |
| Extra required fields | `additional_fields` | Values the user gave in Phase 3, saved per project in `jira-sync.json` |

The description names the evidence files: "Screenshots, recordings and logs: BUG-007_home-screen.png, BUG-007_save-crash.mp4, BUG-007_device-log.txt." Without files: "No screenshots or recordings." A recording that could not be attached adds: "The screen recording BUG-007_save-crash.mp4 (180.4 MB) is too large to attach; it is kept at bugs/BUG-007_…/recordings/BUG-007_save-crash.mp4."

## Priority and severity rules

1. Allowed priorities are read in Phase 3 (`priority.allowedValues`, highest first).
2. Critical severity overrides the bug's Priority with the first (highest) value.
3. Matching is case-insensitive.
4. A Severity custom field is used only when its allowed values contain the bug's severity; otherwise the label and description line carry it.

## Required fields

`getJiraIssueTypeMetaWithFields` (`requiredFieldsOnly: false`) lists `required: true` fields. Ignore those that are filled anyway (project, issuetype, summary, reporter, description, priority, assignee, labels) or have a `defaultValue`. For the rest ask once, with the allowed values when there are any; store with `sync_state.py project-fields --project <KEY> --set '{"<field key>": <value>}'` and put them in `meta.json` → `extraFields`. Value shapes: select → `{"value": "X"}`, multi-select / components / versions → `[{"name": "X"}]`, user → `{"accountId": "…"}`, text → `"X"`, number → `5`.

## Wording

Everything sent to Jira is the QA engineer's wording from the bug file: no testing-tool or machine terms, no credentials. `bug_to_jira.py` runs `lint_human_text.py` on summary, description and environment and exits 1 on any finding; nothing is sent until it passes.
