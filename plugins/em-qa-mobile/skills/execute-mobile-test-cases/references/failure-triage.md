# Failure triage (mobile)

Every failed case in `results.json` is classified **before** anything is recorded. Read the raw error, the failure screenshot and, when it is unclear, the screen recording and the device log excerpt (`evidenceFiles`), plus `appCrashed` / `crashLines` / `appState`. These are for you only; never mention them in human-facing text.

## Cause table

| Cause | How to recognise it | Action |
|---|---|---|
| **Script problem** | Control not found / wrong locator, scroll or keyboard problems (field hidden behind the keyboard, list not scrolled), gesture missed, wrong wait (action before the screen settled), wrong test data, a system pop-up the script did not answer | Fix the script (or the screen object) and run that case again. Maximum **3 attempts** per case |
| **Environment problem** | Device disconnected or locked (`adb devices` shows nothing / `unauthorized`), Appium server error or unreachable, device frozen, app file cannot be installed, no network on the device, Flutter server not reachable after a relaunch | Status `BLOCKED`, Comment with the reason in plain words. Not a bug |
| **Test case problem** | The case's steps or expected result conflict with the PRD/BRD, `project-understanding.md` or clearly intended behaviour | Correct the case wording (`corrections`), Comment `Test case corrected: <what and why>`, run again |
| **App crash or freeze** | The app closes by itself (`appState` "not running" / "running in background" after the failure, the recording shows the home screen), or stops responding; the device log shows `FATAL EXCEPTION`, `ANR in`, `E/flutter`, `Unhandled Exception` (`crashLines`) | **Candidate bug.** Reproduce again from a fresh app state (Phase 5) before filing |
| **Genuine bug** | The app behaves differently from the expected result, and the expected result is backed by the case **and** the PRD/BRD (where available) | Candidate bug → Phase 5 (`qa-mobile-bug-reviewer`) |
| **Cannot be automated after 3 attempts** | Still unclear what goes wrong, or the screen cannot be driven reliably (no label, no key, no text) | Status `BLOCKED`, Comment `Could not be automated: <reason>`. Not a bug |

## Telling a script problem from a real bug

Ask in this order:

1. **Did the screen look right in the screenshot?** If it shows the expected state (the message is there, the right screen is open), the script is wrong.
2. **Was the control missing, or the script looking in the wrong place?** Compare the `Loc` with the stored `screens/*.json`. A label that matches the stored knowledge = script problem; a label that differs from it = the screen changed (see "Outdated knowledge").
3. **Keyboard or scrolling?** A field below the fold or behind the keyboard: add `hideKeyboard()` / `scrollTo()`.
4. **Timing?** If the recording shows the control appearing later, use a state wait (never a sleep).
5. **System pop-up?** A permission or system dialog on the screenshot means the script did not answer it.
6. **Is the expected value itself backed?** Exact text from `observations.md` or the documents → backed. A number that naturally changes → probably a test case problem.
7. Only when the app clearly shows wrong behaviour for a backed expectation, or crashed → candidate bug.

## Outdated knowledge (one screen only)

When a script fails because a screen looks different from the stored knowledge:

1. Look at **that one screen** on the device with the Appium MCP tools (own session, closed afterwards) or `tools/session-check.ts` + page source. No new exploration of other screens or flows.
2. Fix the screen object / script.
3. Save the fresh screen structure (same schema as `screens/*.json`) to a temp file and run
   `python "SKILL/scripts/refresh_exploration.py" --plan-dir "Exploration/<plan-key>" --platform <p> --flow <flow-key> --screen <screen> --new-json <tmp.json> --reason "<what changed>" --run-ts <run ts> [--screenshot <png>]`.
4. Add an observation for the report: "The <screen> screen looked different from the earlier exploration: <what>".

## Retries and intermittent results

- The config re-runs a failed case once automatically (`RETRIES=1`). A case that fails first and passes on the re-run has `"flaky": true`.
- Record it as `PASS` with Comment `Passed on retry, intermittent. Worth watching.` and list it under Observations. Not a bug unless you can reproduce the failure on demand.
- A case that fails on both attempts is a real failure: triage it.

## Attempt limit

- Count your **fix attempts** per case (not the automatic re-run). After the 3rd failed attempt with an unclear cause → `BLOCKED`, `Could not be automated: <reason>`.
- Re-run only the case you fixed: `npx wdio run wdio.<platform>.conf.ts --spec "tests/<suite>/<flow>.spec.ts" --mochaOpts.grep "<TC-ID>"`. The reporter merges it into `results.json`.

## One device

Only one run drives the device at a time. Never start a second `wdio` run, an Appium MCP session and a bug reproduction together; finish one, then start the next.

## Never

- Never edit an expected result just to make a case pass.
- Never file a bug from a script failure, an environment problem, test data or an intermittent result.
- Never mark a case `PASS` without a run that passed.
- Never change device settings to make a case pass.
