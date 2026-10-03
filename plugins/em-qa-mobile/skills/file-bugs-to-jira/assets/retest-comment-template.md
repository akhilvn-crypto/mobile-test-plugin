Retested on {{date}} at {{time}} IST {{where}}{{build}}.
Steps followed: {{steps}}
Result: {{result}}
The issue is fixed. Related test case{{s}} {{test_cases}} passed. Closing this bug.

<!--
How to fill (one comment per bug, plain sentences, no testing-tool words):
- date / time: when the last linked case passed (ended_ist from retest_evidence.py collect), dd-mm-yyyy and hh:mm.
- where: web: "in the <environment name>", e.g. "in the development environment (web-app-dev)".
  Mobile: "on a <device model> (real device), <OS>", e.g. "on a Google Pixel 7 (real device), Android 14"
  (from the retest run's device_info.py).
- build: web: ", build <version>" only when the application shows a version. Mobile: always ", app <version> (build <n>)"
  of the build used for the retest.
- steps: the bug's Steps to Reproduce, numbered on one line: "1. Open … 2. Enter … 3. Click …".
- result: what the user now sees, with the exact message text in quotes. Use the passing case's Actual Result
  and its Expected Result, e.g. 'The message "Enter a valid email address." is now displayed and the email is
  not subscribed.'
- s / test_cases: "s" when more than one case; the case IDs joined with ", " and "and".
- When the issue cannot be moved to a done status (close_pending), end with
  "Ready to be closed." instead of "Closing this bug."
Check the finished text with scripts/lint_human_text.py --text-file before sending it.
-->
