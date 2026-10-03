# Filing flow (Part A): exact steps, questions and messages

`SKILL` = the file-bugs-to-jira skill folder (`${CLAUDE_PLUGIN_ROOT}/skills/file-bugs-to-jira`). Scripts run from the project root: `python "SKILL/scripts/<name>.py"`. Keep working files (bugs.json, meta.json, payloads) in the scratchpad. Ask questions with the interactive question tool (AskUserQuestion) when it is available; otherwise ask in plain text and wait.

## Phase 0 – Arguments and bugs (no Jira call yet)

```
python "SKILL/scripts/list_bugs.py" [--bug-id <id>] [--link-story <KEY>] --out "<scratchpad>/bugs.json"
```

| Result | What to do |
|---|---|
| exit 2, `--bug-id` unknown | Stop: "Bug `<id>` does not exist. The bugs in bugs/ are:" + the `available` list |
| exit 2, `--link-story` malformed | Ask: "`<value>` does not look like a Jira story key (for example PROJ-123). Which story should the bugs be linked to?" Use the answer only if it matches `^[A-Z][A-Z0-9]+-\d+$`; never guess |
| `close_pending` not empty | These closings were left unfinished by an earlier test run. After Phase 1 (connector) finish them first with `closing-fixed-bugs.md`, then continue |
| `to_file` and `story_link_only` empty | Stop with the `message` ("Nothing to file: every open bug is already in Jira." / "BUG-003 is already in Jira (PROJ-45)." / the skip reason) and list `already_filed` with keys |
| `problems` | Show them in the confirmation table's Notes (for example: test case file not found → links cannot be written back) |
| `cross_platform` not empty | Show each candidate in Notes as `Possible duplicate: PROJ-45 (iOS)` (or `BUG-012 (iOS, not in Jira yet)`); Phase 5 asks per bug |

`already_filed` bugs are listed as "already in Jira" with their key and skipped. `story_link_only` bugs get only the missing story link in Phase 6 (no new issue).

## Phase 1 – Connector

1. Find the Atlassian tools (`connector-tools.md`). Load `atlassianUserInfo` and `getAccessibleAtlassianResources` with ToolSearch.
2. Call `atlassianUserInfo`. If the tools are missing, or the call fails with an authentication or connection error, stop with exactly:

   > The Jira connector isn't connected. Please connect the Atlassian connector first (in Claude Code, open `/mcp` and sign in to Atlassian, or add Atlassian's remote MCP server), then run the command again.

   Never ask for a token, password or API key in the chat.
3. `getAccessibleAtlassianResources` → sites with `cloudId`. Keep only sites that have Jira scopes. One site → use it. Several → ask "Which Jira site should the bugs be filed in?" listing `name – url`; mark the site saved in `jira-sync.json` as "(used before)".

## Phase 2 – Project

`getVisibleJiraProjects` with `cloudId`, `action: "create"`, `maxResults: 50` (page with `startAt` while 50 come back).

| Projects | Message |
|---|---|
| 0 | "Your Jira account has no projects where you can create issues." Stop |
| 1 | "The only project available is `KEY - Name`. Is this the project the bugs should be filed in?" Options: Yes / No. No → stop without filing |
| several | "Which Jira project should the bugs be filed in?" Options `KEY - Name`. Mark "(story's project)" for the project of the `--link-story` key and "(used before)" for `projectKey` in `jira-sync.json`. With more than 4 projects, put the marked ones first in the question and offer "Other – type the key"; validate a typed key against the list |

Then: `python "SKILL/scripts/sync_state.py" init --site <url> --cloud-id <id> --project <KEY>` (site and project are saved; no credentials).

## Phase 3 – What the project needs

1. **Issue type**: `getJiraProjectIssueTypesMetadata`. Use `Bug`. If missing: offer the closest (`Defect`, `Problem`, `Incident`) — "This project has no Bug issue type. Use `<closest>` instead?" Nothing fits → ask which type to use (list the non-sub-task types). Never a sub-task type.
2. **Fields**: `getJiraIssueTypeMetaWithFields` with the issue type id and `requiredFieldsOnly: false`. Read:
   - `priority.allowedValues` names, in Jira's order (highest first);
   - whether `environment` is on the screen;
   - a field whose name contains "Severity" → its key and allowed values;
   - **required fields without a default** other than project, issuetype, summary, reporter (and description/priority/assignee/labels, which are filled). If any: ask once — "The project requires `<Field>` when creating a bug. What should it be?" (offer the allowed values) — and save the answers with `sync_state.py project-fields --project <KEY> --set '<json>'`. On later runs reuse the saved values (show them in the confirmation table). A required field that cannot be filled → stop: "The project requires the field `<Field>`, which cannot be filled from here."
3. **Story** (only with `--link-story`): `getJiraIssue`. Not found / no permission → stop: "The story `<KEY>` was not found or cannot be opened with your account." Not a Story (Epic, Task, …) → ask "`<KEY>` is a `<type>`, not a Story. Link the bugs to it anyway?" A story in another project is fine.
4. **Link type**: `getIssueLinkTypes` → must contain `Relates`. Missing → stop and list the available link types.
5. Write `<scratchpad>/meta.json` for `bug_to_jira.py`:
   ```json
   {"projectKey": "PROJ", "issueType": "Bug", "priorities": ["Highest", "High", "Medium", "Low", "Lowest"],
    "environmentField": true, "severityField": null, "extraFields": {}}
   ```

## Phase 4 – Assignee

Build the list:
1. REST configured (`python "SKILL/scripts/jira_rest.py" check` → `auth_ok` and `site_matches`) → `jira_rest.py assignable --project <KEY>` (most accurate).
2. Otherwise `searchJiraIssuesUsingJql` `project = <KEY> AND assignee IS NOT EMPTY ORDER BY updated DESC`, `maxResults: 50`, `fields: ["assignee"]` → distinct people (repeat with `reporter` if the list is short). Keep the field list that small: on the RD project a 100-issue query with more fields returned ~240,000 characters and could not be read.
3. Always add `Me (<current user>)`, `Unassigned` and `Other…`.

Ask: "Who should the bugs be assigned to?" (the question tool shows at most 4 options: put `Me`, `Unassigned` and the two most active people first, and say in the question text that "Other" accepts any name; list the remaining people in the question text). With several bugs add "Choose per bug" (then ask once per bug, same list). `Other…` / a typed name → `lookupJiraAccountId`; show "Found: `<display name>` (`<email if shown>`). Assign to this person?" Several matches → let the user pick. No match → ask again. The choice applies to every bug of the run unless "Choose per bug".

## Phase 5 – Confirm before creating

For each bug: `python "SKILL/scripts/bug_to_jira.py" --bugs-json "<scratchpad>/bugs.json" --id <ID> --meta "<scratchpad>/meta.json" --out "<scratchpad>/<ID>.payload.json"`.
Exit 1 = the lint found machine terms or a secret in text going to Jira → fix the bug file (with the user's knowledge if it changes meaning), run `list_bugs.py` again, rebuild.

Duplicate check per bug: `searchJiraIssuesUsingJql` `project = <KEY> AND statusCategory != Done AND summary ~ "<3–5 key words of the title>"`. Best match → Notes: "Possible duplicate: PROJ-12 – <summary>".

**Cross-platform check (mobile bugs):** the `cross_platform` candidates from `list_bugs.py`, plus `searchJiraIssuesUsingJql` `project = <KEY> AND labels = "<other platform>" AND labels = "mobile" AND summary ~ "<key words>"`. Show the best match as `Possible duplicate: PROJ-45 (iOS)`. Ask per bug: "BUG-007 (Android) looks like PROJ-45 (iOS). File it anyway and link the two, or skip it?" (File anyway and link / Skip). File anyway → in Phase 6 add `createIssueLink` `type: "Relates"` between the new issue and PROJ-45 and record `sync_state.py set --id BUG-007 --related PROJ-45`.

**Attachments (mobile bugs):** `python "SKILL/scripts/jira_rest.py" check`. Configured → `jira_rest.py limit` → `upload_limit_bytes`; per mobile bug `python "SKILL/scripts/prepare_attachments.py" --bug <ID> --limit <bytes> --out-dir "<scratchpad>/att"`. Put its `note` (when not empty) into `meta.json` as `attachmentNote` before building that bug's payload, and show `not_uploaded` in Notes ("Recording too large: kept locally"). Not configured → Notes: "Attach by hand: screenshots, recording, log".

Show one table and ask "File these bugs in Jira?" (Yes – file all / Choose bugs to skip / No – cancel):

| Bug | Platform | Title | Severity → Priority | Project | Assignee | Story link | Notes |
|---|---|---|---|---|---|---|---|
| BUG-007 | Android | Notes - App closes after tapping Save | Critical → Highest | PROJ | Asha K | PROJ-10 | Possible duplicate: PROJ-45 (iOS); 3 files to upload |
| BUG-003 | web | Advanced Search - Result message says "1 item were found" | Trivial → Low | PROJ | Asha K | PROJ-10 | Possible duplicate: PROJ-12 |
| BUG-001 | web | … (already in Jira as PROJ-40) | | | | PROJ-10 | Story link only |

Bugs with a possible duplicate: ask per bug "File anyway or skip?". Nothing is created before the answer. "No" → stop: "Nothing was filed."

## Phase 6 – File each bug, one by one

1. **Label guard**: `searchJiraIssuesUsingJql` `project = <KEY> AND labels = "<BUG-ID>"`. Found → reuse it: record it (`sync_state.py set --id <ID> --key <KEY-n> --status filed --filed-on now`), skip creating, continue at step 4 (story link), say "BUG-003 was already in Jira as PROJ-45 (found by its label); it was not filed again."
2. **Create**: `createJiraIssue` with `cloudId`, `projectKey`, `issueTypeName`, `summary`, `description`, `contentFormat: "markdown"`, `assignee_account_id` (omit for Unassigned), `additional_fields` — all copied **unchanged** from the payload file.
   - Error → read the message. An invalid optional field (environment, severity) → drop it, move its content into the description as the payload notes say, retry **once**. Permission/connection → report and go to the next bug.
3. **Save state immediately**: `sync_state.py set --id <ID> --key <returned key> --url <site>/browse/<key> --status filed --filed-on now --platform <web|android|ios> [--story <STORY>]`.
   **Attachments (mobile, REST configured):** `python "SKILL/scripts/jira_rest.py" attach --key <key> --file "<each path in upload>"`; record each uploaded file with `sync_state.py set --id <ID> --attached "<file name>"`. A failed upload is reported with Jira's message; the files stay listed for the user.
   **Other platform (file anyway):** `createIssueLink` `type: "Relates"`, `inwardIssue: <new key>`, `outwardIssue: <other platform's key>`, then `sync_state.py set --id <ID> --related <other key>`.
4. **Story link** (with `--link-story`): `createIssueLink` `type: "Relates"`, `inwardIssue: <bug key>`, `outwardIssue: <story>`. Then `sync_state.py set --id <ID> --story <STORY>`. For `story_link_only` bugs this is the only step (then 5 and 6).
5. **Verify**: `getJiraIssue` `fields: ["*all"]`, `responseContentFormat: "markdown"`. Compare with the payload `checks`:
   summary equal; description contains every section heading in `checks.description_sections`; priority name; assignee account id; every label (incl. `mobile` and the platform); environment present when `environment_field`; severity field value; the story (and the other platform's issue, when linked) among `issuelinks` (type Relates); uploaded attachments present by file name (mobile with REST). Files added by hand are not checked.
   Mismatch → `editJiraIssue` with the right value, read again. Still wrong → report it plainly in the summary ("Priority stayed Medium; the project did not accept High"). Never report success for an unchecked item.
6. **Write back**: `python "SKILL/scripts/writeback.py" filed --bug <ID>` (`writeback.md`). Report its `problems`.

One bug failing never stops the run: report the exact reason and continue with the next bug.

## Phase 7 – Summary

```
file-bugs-to-jira – <project KEY - name> (<site>)

| Bug | Jira | Assignee | Story link | Problems |
|---|---|---|---|---|
| BUG-003 | [PROJ-45](https://…/browse/PROJ-45) | Asha K | PROJ-10 | – |
| BUG-007 | not filed | – | – | Permission denied: you cannot create issues in PROJ |

Already in Jira (skipped): BUG-001 → PROJ-40
Files updated: bugs/BUG-003_…/BUG-003_….md, bugs/bug-index.md, bugs/jira-sync.json,
               Test Cases/<name>.md (+ .xlsx), Test Reports/<report>.md (+ .xlsx)
Evidence to attach by hand: BUG-003 → bugs/BUG-003_…/screenshots/, recordings/   (from the payload's evidence_files)
```

Links shown only for keys Jira returned and the read-back confirmed.
