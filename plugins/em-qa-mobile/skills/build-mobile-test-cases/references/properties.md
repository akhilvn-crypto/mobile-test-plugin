# MD front-matter properties (mobile)

The property keys appear **only in the MD** (never in the XLSX Document Control sheet). Same keys as web.

```yaml
---
title: "<Project Name> – <Test plan name> Test Cases"
document_type: Test Cases
project_id:
document_id:
version: V1.0
approved_date:
privacy: Confidential
tags:
  - test-cases
  - qa
  - mobile
  - android
  - flutter
---
```

| Key | Filled by | Value |
|---|---|---|
| `title` | Claude | `<Project Name> – <Test plan name> Test Cases` (en dash). Project name from `project-understanding.md`; if unknown, `<Test plan name> Test Cases` |
| `document_type` | Claude | `Test Cases` |
| `project_id` | **Leave empty** | |
| `document_id` | **Leave empty** | |
| `version` | Claude | `V1.0` on a first run of this platform |
| `approved_date` | **Leave empty** | |
| `privacy` | Claude | `Confidential` |
| `tags` | Claude | `test-cases`, `qa`, `mobile`, `android` **or** `ios` (the file's platform), `flutter` |

Empty keys stay empty (`project_id:` with nothing after it).

## Version bump rules (per platform file)

| Situation | Version |
|---|---|
| First run for this platform | `V1.0` |
| Re-run with changes | previous minor + 1: `V1.0` → `V1.1` → `V1.2` … (`V1.9` → `V1.10`) |
| `--force-full` with a previous output | bump like a changing re-run |
| Unchanged re-run, or new build without changed screens | nothing is written, version unchanged |

The previous version is `manifest.json` → `platforms.<platform>.version` (falls back to the `version` key of that platform's `last_output_file`).

Each new version adds one Version History row: `| <version> | <dd-mm-yyyy> | | | <comment> |`. Comment is `Initial generation` on a first run, otherwise a one-line change summary, e.g. `Re-run: app 2.4.2 (build 124), Login updated (2 new, 1 updated), Profile added`. Revised By and Approved By stay empty.
