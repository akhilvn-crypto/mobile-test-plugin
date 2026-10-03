---
description: Execute written mobile test cases on a real device (Appium + WebdriverIO + TypeScript), record results, file genuine bugs and produce a test report (MD, optional XLSX)
argument-hint: --testcase "<file name>" [--test-report xlsx]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill, ToolSearch, mcp__claude_ai_Atlassian_Rovo
---

Arguments: `$ARGUMENTS`

If `--testcase` is missing from the arguments above, or `--test-report` is given with any value other than `xlsx` (or with no value), print exactly this line and stop:

```
Usage: /execute-mobile-test-cases --testcase "<file name>" [--test-report xlsx]
```

Otherwise use the `execute-mobile-test-cases` skill (`em-qa-mobile:execute-mobile-test-cases`, at `${CLAUDE_PLUGIN_ROOT}/skills/execute-mobile-test-cases/SKILL.md`) with these arguments and follow it from Phase 0 to the final summary. Start with `scripts/find_testcase.py`, passing the arguments text unchanged as one single-quoted string. Only real devices are used; only one run drives the device at a time.
