# Bug writing guide (mobile)

Bugs are written by a QA engineer for a developer. They describe what a user does and sees on the phone, never how the testing tool works. The `bugs/` folder, `bug-index.md` and the running `BUG-nnn` numbering are **shared with web**.

## Files

```
bugs/
├── bug-index.md                                   # one row per bug (scripts/bug_index.py), web and mobile
└── BUG-007_app-closes-after-tapping-save/
    ├── BUG-007_app-closes-after-tapping-save.md   # the report (template: assets/bug-template.md)
    ├── screenshots/BUG-007_home-screen-after-crash.png
    ├── recordings/BUG-007_save-crash.mp4          # screen recording of the failing steps (required)
    ├── logs/BUG-007_device-log.txt                # optional device log excerpt, secrets removed
    └── retest/                                    # later: passing-run recording and screenshot (Jira closing)
```

- ID: `python "SKILL/scripts/bug_index.py" next` → `BUG-<NNN>`, running across the project (web and mobile), never reused.
- Slug: `python "SKILL/scripts/bug_index.py" slug "<title>"`.
- Register: `bug_index.py add --id … --title "<Feature> - <what is wrong>" --severity … --priority … --test-cases "TC-…" --folder "BUG-<NNN>_<slug>"`.
- Duplicates: `bug_index.py list` and compare (same screen + same wrong behaviour = same bug, even from a different case; a bug filed for the other platform is **not** a duplicate here – `file-bugs-to-jira` links the two). For a duplicate: `bug_index.py also-seen --id BUG-007 --test-case TC-… --note "<where>"`. No new folder.
- Retest passed: `bug_index.py set-status --id BUG-007 --status "Fixed - verified"` (a bug filed in Jira is closed by `file-bugs-to-jira` instead).

## Template (assets/bug-template.md)

```markdown
# BUG-007: Notes - App closes after tapping Save

| Field | Value |
|---|---|
| Severity | Critical |
| Priority | High |
| Status | Open |
| Platform | Android |
| Test case(s) | TC-E2E-POS-004 |
| Test case file | Demo App Plan_Android_2026-10-03_10-44-55-IST.md |
| Reported on | 03-10-2026 14:35:10 IST |
| Jira | Not filed |

## Summary
The app closes by itself when a new note is saved.

## Description
A signed-in user writes a note and taps Save. The app closes by itself and the note is lost. It happens every time, on the one device tried.

## Steps to Reproduce
1. Open the app and sign in as <user>.
2. Tap New note.
3. Enter "Shopping list" in the Title field.
4. Tap Save.

## Expected Result
The note "Shopping list" is shown at the top of the Notes list.

## Actual Result
The app closes by itself after tapping Save and returns to the home screen. The entry is not saved.

## Environment
- App: Demo Notes 2.4.1 (build 123)
- Device: Google Pixel 7 (real device)
- Operating system: Android 14
- Network: Wi-Fi
- Screen: portrait, language en-IN, dark mode off
- User/role: user

## Insights for Developers
- The device log shows: "E/flutter: [ERROR:flutter/runtime/dart_vm_initializer.cc] Unhandled Exception: Null check operator used on a null value".
- It happens every time from a fresh app state.
- Possible cause: the note's date is read before it is set.

## Attachments
- screenshots/BUG-007_home-screen-after-crash.png
- recordings/BUG-007_save-crash.mp4
- logs/BUG-007_device-log.txt
```

- `Platform`: `Android` or `iOS`. `Test case file`: the exact test case file name (with `.md`); it also tells `file-bugs-to-jira` which platform's files to update. `Jira`: always `Not filed` when written; `file-bugs-to-jira` replaces it.
- `Reported on`: `python "SKILL/scripts/ist_timestamp.py" --cell`.
- Environment lines come from `device_info.py` → `environment_lines` (App, Device, Operating system, Network, Screen) plus `User/role:` – the role, never a password or e-mail. Always `(real device)` after the model.
- When `qa-mobile-bug-reviewer` tried a second real device, say in the Description whether it happened on one device or on both, and name the second device under Insights.

## Wording rules

- Steps are things the user does: Open the app, Tap, Long press, Swipe, Scroll, Enter, Minimise the app, Reopen the app, Rotate the device, Allow / Deny the permission, Turn on airplane mode, Go back. One action per step, numbered, starting from a state anyone can reach ("Open the app from a fresh install", "Open the app and sign in as <role>").
- State what the user sees. Quote the exact message text in double quotes.
- Insights for developers may quote device log lines **as the app printed them** (in double quotes) and say when it happens (every time, only after minimising, only on one device), plus a short possible cause marked as a possibility.
- **Never use** (`lint_human_text.py` flags these, list in `assets/banned-terms.txt`): Appium, WebdriverIO, driver, capabilities, session, XPath, resource id, content description, accessibility id, UiSelector, widget tree, context, `NATIVE_APP`, `FLUTTER`, adb, logcat, and the web terms (Playwright, script, locator, selector, assertion, timeout, element not found, retry, automation …).
- Translate runner messages into human language:

| Runner says (never copy) | Bug says |
|---|---|
| `Control not found within 15000 ms: Save button` | The Save button never appeared on the Edit note screen. |
| `Expected "3 notes", received "2 notes"` | The Notes list shows "2 notes" instead of 3 after saving. |
| `appState: not running` + `FATAL EXCEPTION` | The app closes by itself after tapping Save and returns to the home screen. |
| `An unknown server-side error occurred … ANR` | The app stops responding for more than 10 seconds after tapping Save; Android offers to close it. |

## Attachments

- A screenshot that **shows the problem** (copy from `mobile-automation/test-results/<suite>/evidence/<TC-ID>/attemptN_screenshot.png`, rename meaningfully).
- A **screen recording (MP4)** of the failing steps (`attemptN_recording.mp4` → `recordings/BUG-007_<what>.mp4`). Required for every mobile bug.
- Optionally a **device log excerpt** (`attemptN_device-log.txt` → `logs/BUG-007_device-log.txt`): only the lines around the problem, scrubbed (`python "<build skill>/scripts/snapshot_diff.py" scrub "<file>" --secret …`), never the whole log.
- Hide anything sensitive: if a screenshot or recording shows a password, token or personal data, record it again after clearing the field – never attach it unmasked.

## Severity guide

| Severity | Meaning |
|---|---|
| Critical | App crash or freeze on a main path, core flow blocked, data loss or a security problem |
| Major | A feature does not work or works wrongly, with no reasonable workaround |
| Minor | Works with a workaround, or a visible but low-impact defect |
| Trivial | Cosmetic or wording only |

Priority (High / Medium / Low) is a suggestion based on user impact.

## Bug status values

`Open`, `In Progress`, `Fixed - verified`, `Closed`, `Closed in Jira`, `Reopened`, `Rejected`. This skill sets `Open` on filing and `Fixed - verified` after a passing retest of a bug not filed in Jira.
