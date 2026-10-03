---
description: File the bugs from bugs/ into Jira (fields, attachments, story link), verify them and write the Jira links back to the test cases and test report
argument-hint: [--bug-id <BUG-ID>] [--link-story <STORY-KEY>]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion, ToolSearch, mcp__claude_ai_Atlassian_Rovo
---

Arguments: `$ARGUMENTS`

If the arguments contain anything other than `--bug-id <value>` and/or `--link-story <value>` (each at most once, each with a value), print exactly this line and stop:

```
Usage: /file-bugs-to-jira [--bug-id <BUG-ID>] [--link-story <STORY-KEY>]
```

Otherwise use the `file-bugs-to-jira` skill (`em-qa-mobile:file-bugs-to-jira`, at `${CLAUDE_PLUGIN_ROOT}/skills/file-bugs-to-jira/SKILL.md`) and follow Part A from Phase 0 to the final summary. Start with `scripts/list_bugs.py`, passing `--bug-id` and `--link-story` exactly as given. Make no Jira call before Phase 0 is done, and create nothing in Jira before the user confirms the table in Phase 5.
