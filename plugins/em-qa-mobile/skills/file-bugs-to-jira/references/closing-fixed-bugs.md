# Part B: closing fixed bugs

Runs from `/execute-mobile-test-cases` or `/execute-test-cases` (Phase 5a), after the retest results are known and **before** the test cases and the report are updated. Also runs at the start of `/file-bugs-to-jira` for bugs left `close_pending`. Closing is automatic — no question to the user — but it only ever touches issues recorded in `bugs/jira-sync.json`.

`SKILL` = the file-bugs-to-jira skill folder (`${CLAUDE_PLUGIN_ROOT}/skills/file-bugs-to-jira`); `EXEC` = its sibling `SKILL/../execute-mobile-test-cases`.

## 1. Candidates (local)

`python "EXEC/scripts/retest_evidence.py" collect --results "<results_dir>/results.json" --since <ISO start of this run>`

A bug is a candidate only when **all** hold (the script checks 1–3 and copies the evidence to `bugs/<bug>/retest/`):
1. In `jira-sync.json` with status `filed` or `close_pending`.
2. **Every** test case linked to the bug passed in this run. Skipped, blocked, manual, still failing or not run → stays open.
3. Passed on the first attempt (not flaky, not on the automatic retry) and kept a retest screenshot (and recording) locally, for the user to attach by hand if they want.
4. In Jira the issue is not done (checked in step 2 below).

`stay_open` bugs keep their state; say why in the run summary. For `close_pending` bugs started from `/file-bugs-to-jira`, the candidate data comes from the earlier run: retest files already in `bugs/<bug>/retest/`, cases already PASS in the test case file.

## 2. Per candidate, in this order

1. **Connector check** (`atlassianUserInfo`). Not connected → do not fail the test run: `sync_state.py set --id <ID> --status close_pending --note "Jira connector was not connected"`, tell the user, and leave everything else for the next `/file-bugs-to-jira` or test run.
2. **Read** `getJiraIssue` (`fields: ["status", "resolution", "assignee", "comment"]`). Status category Done (closed, done, resolved, "Won't Do", "Duplicate" …) → **do not touch Jira**. Only update the local state: `writeback.py closed --bug <ID> [--bug-only]` and note "PROJ-45 was already closed in Jira (Done)".
3. **Comment** (`addCommentToJiraIssue`, `contentFormat: "markdown"`), from `assets/retest-comment-template.md`, checked first with `lint_human_text.py --text-file`:

   > Retested on 05-10-2026 at 14:22 IST in the development environment (web-app-dev).
   > Steps followed: 1. Open the subscription page. 2. Enter "abc.co" in the email field. 3. Click Subscribe.
   > Result: The message "Enter a valid email address." is now displayed and the email is not subscribed.
   > The issue is fixed. Related test case TC-UI-NEG-014 passed. Closing this bug.

   Mobile bug – the comment names the device, OS and build of the retest (from the run's `device_info.py`):

   > Retested on 05-10-2026 at 14:22 IST on a Google Pixel 7 (real device), Android 14, app 2.4.2 (build 124).
   > Steps followed: 1. Open the app and sign in as user. 2. Tap New note. 3. Enter "Shopping list" in the Title field. 4. Tap Save.
   > Result: The note "Shopping list" is shown at the top of the Notes list and the app stays open.
   > The issue is fixed. Related test case TC-E2E-POS-004 passed. Closing this bug.

   Do not add a second comment when a retest comment from the same day is already on the issue (an interrupted earlier attempt).
4. **Close**: `getTransitionsForJiraIssue`. Keep transitions whose target status category is Done; prefer the name `Closed`, then `Done`, then `Resolved`, then any other Done transition. When the transition screen needs a resolution, pass `fields: {"resolution": {"name": "<Done or Fixed, whichever is offered>"}}`. `transitionJiraIssue`.
   - **No direct transition to Done**, or it needs fields that cannot be filled → do not force it (no chain of transitions, no field guessing). The comment stays. `sync_state.py set --id <ID> --status close_pending --note "<what is needed, e.g. the workflow has no direct transition from In Progress to Done>"` and tell the user exactly that.
   - Transition error → retry once, then the same as above with Jira's message as the note.
5. **Verify**: `getJiraIssue` again — status category Done and the comment present. Report any part that is missing. Retest evidence (the passing-run screenshot and screen recording in `bugs/<bug>/retest/`): for a mobile bug with the REST settings, `prepare_attachments.py --bug <ID> --retest --limit <bytes>` then `jira_rest.py attach` (record with `sync_state.py set --attached`); otherwise name that folder in the run summary so the user can attach them by hand.
6. **Local files**: `python "SKILL/scripts/writeback.py" closed --bug <ID> --closed-on "<cell time>" --bug-only` from `/execute-mobile-test-cases` / `/execute-test-cases` (its results update writes `Retest passed. PROJ-45 closed.` and the new report shows the closed state); without `--bug-only` when finishing a `close_pending` bug from `/file-bugs-to-jira` (the test cases and the latest report are updated in place).

## Not in v1

Reopening: when a closed bug's case fails again, `execute-mobile-test-cases` (or `execute-test-cases`) files a **new** bug whose Description mentions the old key ("This looks like PROJ-45, which was closed on 05-10-2026."). Nothing is reopened automatically.
