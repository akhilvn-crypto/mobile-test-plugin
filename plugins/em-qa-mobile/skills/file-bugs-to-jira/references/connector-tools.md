# Jira connector tools

The skill talks to Jira through the user's **Atlassian connector** (Atlassian's remote MCP server, "Atlassian Rovo"). On the machine where this skill was built the tools are exposed as `mcp__claude_ai_Atlassian_Rovo__<tool>`; on another setup the prefix can differ (for example `mcp__atlassian__<tool>`). Look the tools up by their **last part** (the names below). They are often *deferred*: load their schemas first with ToolSearch (`select:<full name>,<full name>,…`) before the first call.

Every call except `atlassianUserInfo` and `getAccessibleAtlassianResources` needs `cloudId` (UUID, or the site host such as `yourcompany.atlassian.net`).

| Tool | Used in | Notes |
|---|---|---|
| `atlassianUserInfo` | Phase 1 | Connector check. Fails or is missing → not connected. Gives the current user (for "Me") |
| `getAccessibleAtlassianResources` | Phase 1 | Sites and their `cloudId`. More than one site → ask which one |
| `getVisibleJiraProjects` | Phase 2 | `action: "create"` lists only projects where the user can create issues. `searchString` narrows; pages of 50 (`startAt`) |
| `getJiraProjectIssueTypesMetadata` | Phase 3 | Issue types of the project (`Bug`, `Defect`, …) with their ids |
| `getJiraIssueTypeMetaWithFields` | Phase 3 | `requiredFieldsOnly: false` → every field on the create screen: `priority` (allowedValues), `environment`, a Severity custom field (name contains "Severity"), required fields |
| `getIssueLinkTypes` | Phase 3 | Must contain `Relates` |
| `getJiraIssue` | Phase 3, 6, Part B | Story check; read-back with `fields: ["*all"]`; closing: status, statusCategory, resolution. Include `"comment"` in `fields` to see comments |
| `lookupJiraAccountId` | Phase 4 | Resolve a typed name to an account id; show the match back before using it |
| `searchJiraIssuesUsingJql` | Phase 4, 5, 6 | Recent people in the project; duplicate check; label guard (`labels = "BUG-003"`). `maxResults` 50–100 |
| `createJiraIssue` | Phase 6 | `projectKey`, `issueTypeName`, `summary`, `description`, `contentFormat: "markdown"`, `assignee_account_id`, and **everything else in `additional_fields`** (priority, labels, environment, severity, extra required fields) |
| `editJiraIssue` | Phase 6 | Corrections right after creation only (`fields: {...}`) |
| `createIssueLink` | Phase 6 | `type: "Relates"`, `inwardIssue: <bug key>`, `outwardIssue: <story key>` (Relates has no direction) |
| `addCommentToJiraIssue` | Part B | `commentBody` (markdown), `contentFormat: "markdown"` |
| `getTransitionsForJiraIssue` | Part B | Transitions with their target status and status category; check `fields` the transition screen requires |
| `transitionJiraIssue` | Part B | `transition: {id}`; resolution in `fields: {"resolution": {"name": "Done"}}` when the screen needs it |

## What the connector cannot do

- **No attachment upload tool.** Web bugs: the user attaches screenshots and recordings by hand. Mobile bugs: uploaded through the Jira REST settings (`jira_rest.py attach`, settings `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` in `.env` or `mobile-automation/.env`); without them, listed for the user to attach.
- **No assignable-user search**: the person list is built from recent issues, or from `jira_rest.py assignable` when the REST settings exist.

## Field formats seen through the connector

- `description` and comments: markdown string with `contentFormat: "markdown"`.
- `environment` (Jira Cloud REST v3 rich text): an ADF document. `bug_to_jira.py` builds it (`{"type": "doc", "version": 1, "content": [bulletList …]}`). If Jira rejects it, move the Environment lines into the description (re-run `bug_to_jira.py` with `"environmentField": false` in the meta file) and report that.
- `priority`: `{"name": "High"}`; `labels`: list of strings without spaces; select custom fields: `{"value": "Major"}`.
- The read-back shows rich text as markdown when `responseContentFormat: "markdown"` is passed.

## Errors

Report the exact failure in plain words: permission (403 / "You do not have permission"), invalid field (400 with the field name), not found (404), connection or authentication (401, connector error). Retry a failed call **once** at most. Never present a key or link that Jira did not return.
