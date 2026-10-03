# Test case schema (mobile)

Same columns, cell encoding and ID rules as the web skill. One file holds **one platform** of one app. Every test case is one row of a Markdown table inside its flow section. Columns appear **in this exact order** with these exact header names (`execute-mobile-test-cases` finds them by name).

| # | Column | Rule |
|---|---|---|
| 1 | Test Case ID | `TC-<LEVEL>-<TYPE>-<NNN>` (see below). Required |
| 2 | Test Case Title | `<Feature> - <what is verified>`. Plain, no tags. Required |
| 3 | Test Description | One sentence starting "Verify that…". Required |
| 4 | Preconditions | The app state the case starts from (`App freshly installed.`, `Signed out.`, `Signed in as <role>.`) and, for MOB cases, what the device condition needs (`Location permission not yet granted.`, `Device in airplane mode.`) |
| 5 | Test Steps | Numbered, short, 3 to 6 steps. Required |
| 6 | Test Data | `Label: value` lines. Mask secrets |
| 7 | Expected Result | What the user sees or what the app does. Required |
| 8 | Actual Result | Empty on generation |
| 9 | Execution Status | One of `PASS, FAIL, IN PROGRESS, PENDING, BLOCKED`; default `PENDING`. Required |
| 10 | Comments | Empty, or `[NEW]` / `[UPDATED]` / `[OBSOLETE]` on re-runs (a short note may follow the tag) |
| 11 | Created By | **Leave empty** |
| 12 | Reviewed By | **Leave empty** |
| 13 | Executed By | **Leave empty** |
| 14 | Executed On | Empty until executed. Format `dd-mm-yyyy hh:mm:ss IST` |
| 15 | Execution Defects | Empty |

## ID format

`TC-<LEVEL>-<TYPE>-<NNN>`, e.g. `TC-MOB-NEG-014`.

| LEVEL | Meaning (mobile) | TYPE | Meaning |
|---|---|---|---|
| `CMP` | Component: a screen or control on its own (field, button, list item) | `POS` | Positive |
| `INT` | Integration: screens and services working together | `NEG` | Negative |
| `E2E` | End to end: a full user journey | `EDG` | Edge |
| `UI` | Basic UI/UX: layout on the connected device, orientation, dark mode, keyboard covering fields, messages | `BND` | Boundary |
| `MOB` | Mobile conditions: how the app behaves on the device (see `mobile-conditions.md`) | `VAL` | Validation |
| | | `ERR` | Error |

**Out of scope for now:** `API`, `SEC` (security) and `ACC` (accessibility). Their codes stay reserved so they can be added later without changing the ID format. No such case is written; `lint_testcases.py` flags any case that uses them.

- `NNN` is **one running number across the whole file** (not per flow, not per level), zero-padded to 3 digits (4+ digits allowed past 999).
- IDs are unique and **never change** on re-runs. New cases continue from the highest number ever used (including `[OBSOLETE]` ones). Never reuse a number.
- Next number: `python scripts/lint_testcases.py <previous.md> --stats` → `max_number` + 1.

## Markdown cell encoding

- A Markdown table cell cannot hold a newline. Write line breaks as `<br>`: `1. Open the app.<br>2. Tap Sign in.<br>3. Enter the email.`
- Escape a literal pipe as `\|`.
- Do not use other HTML.

## Execution Status values (dropdown in XLSX, legend in MD)

`PASS`, `FAIL`, `IN PROGRESS`, `PENDING`, `BLOCKED`. Default `PENDING`. Cases the device cannot be put in by the test run stay `PENDING` with `Needs manual check: <reason>` in Comments at execution time.

## MD document layout

```
---                                   <- front-matter, see properties.md (tags: test-cases, qa, mobile, android|ios, flutter)
...
---

# <Test plan name> – Test Cases

| Field | Value |
|---|---|
| Plan name | <Test plan name> |
| Plan key | <plan-key> |
| Project | <Project name> |
| Source documents | a.pdf, b.docx, <plan file> |
| Platform | Android |                          <- Android or iOS: one platform per file
| Device | Pixel 7 (real device) |
| OS version | Android 14 |
| App version and build | 2.4.1 (build 123) |
| Run mode | First run / Re-run (partial) / Force full |
| Generated at | dd-mm-yyyy hh:mm:ss IST |

Out of scope for now: API, security and accessibility

## Version History
| Version No | Created On | Revised By | Approved By | Comments |
|---|---|---|---|---|
| V1.0 | 03-10-2026 | | | Initial generation |

## Legend
Execution Status allowed values: `PASS`, `FAIL`, `IN PROGRESS`, `PENDING`, `BLOCKED` (default `PENDING`).
Comments tags: `[NEW]`, `[UPDATED]`, `[OBSOLETE]`.

## <Flow name>
<!-- flow-key: <flow-key> -->
User story: #234 - Login page update      <- only when the plan names a story/ticket for the flow

| Test Case ID | Test Case Title | ... 15 columns ... |
|---|---|---|
| TC-E2E-POS-001 | ... |

### Coverage Matrix – <Flow name>
| Level | POS | NEG | EDG | BND | VAL | ERR |
|---|---|---|---|---|---|---|
| Component (CMP) | TC-CMP-POS-002 | ... | N/A – <reason> | ... |
...  (one row per level: CMP, INT, E2E, UI, MOB)

### Mobile Conditions – <Flow name>
| Condition | Covered by | Notes |
|---|---|---|
| App lifecycle | TC-MOB-EDG-007 | |
| Permissions | N/A – the flow asks for no permission | |
| Interruptions | TC-MOB-NEG-009 | Needs a person: calls cannot be triggered on a real device |
| Network | TC-MOB-ERR-010 | |
| Orientation | N/A – the app supports portrait only | |
| Device settings | TC-UI-EDG-011 | Dark mode |
| Navigation | TC-MOB-POS-012 | System back gesture |

## <next flow> ...

## Observations and Assumptions
- ...
- Testability: <screen> – <control> has no label or key.   <- from testability.md, a note for the team
```

- Column headers must stay exactly as listed above.
- Masked credentials name the role: `User: <admin>`, `Password: ********` (the executor maps them to `.env` variables).
- A flow section is an H2 immediately followed by the `<!-- flow-key: ... -->` marker. H2s without the marker are document sections.
- The coverage matrix comes before the conditions table. `lint_testcases.py --write-matrix` builds the matrix and adds a conditions skeleton (`N/A – TODO` rows) where it is missing; the TODOs must be replaced with case IDs or a reason.
- Version History rows accumulate across runs (copy previous rows, append the new one).
