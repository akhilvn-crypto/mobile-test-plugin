---
description: Build mobile test cases (MD, optional XLSX, one file per platform) for a Flutter app from project docs, a test plan and exploration on a real device with Appium
argument-hint: --project-dir <dir> --test-plan <file> [--xlsx] [--force-full]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, ToolSearch
---

Arguments: `$ARGUMENTS`

If `--project-dir` or `--test-plan` is missing from the arguments above, print exactly this line and stop:

```
Usage: /build-mobile-test-cases --project-dir <dir> --test-plan <file> [--xlsx] [--force-full]
```

Otherwise use the `build-mobile-test-cases` skill (`em-qa-mobile:build-mobile-test-cases`, at `${CLAUDE_PLUGIN_ROOT}/skills/build-mobile-test-cases/SKILL.md`) with these arguments and follow it from Phase 0 to the final summary. Start with `scripts/parse_args.py`, passing the arguments text unchanged as one single-quoted string. The platform, device, operating system and app build come from the test plan, not from arguments. When nothing changed since the last run, stop without opening the device.
