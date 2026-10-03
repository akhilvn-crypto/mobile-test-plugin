# Script writing guide (mobile)

Scripts turn the written test cases into WebdriverIO + TypeScript tests that drive the app on the real device through Appium, one test per case. They are read by engineers, never by the people who read the test cases, bugs or reports.

## Inputs (per flow)

- The flow's cases from `parse_testcases.py --flow <key> --to-run` (ID, title, preconditions, steps, test data, expected result, `app_state` hint, `device_condition` for MOB cases).
- `Exploration/<plan-key>/<platform>/<flow-key>/screens/*.json`: controls with labels, keys, ids, types; input fields and their rules; exact messages; `reached_by`.
- `observations.md` (exact message texts, behaviour notes, `Flutter layer: reachable | not reachable`), `testability.md` (controls with no label or key – expect weaker locators there). Screenshots only when the layout matters.
- Existing `screens/*.ts` (reuse; extend instead of duplicating), `helpers/`, `fixtures/`.
- Do **not** open the device. If the stored knowledge is not enough to write a step, say so in the return value.

## Spec file

```ts
// Source: Test Cases/Demo App Plan_Android_2026-10-03_10-44-55-IST.md (V1.0) – flow: login
import { expect } from '@wdio/globals';
import { startFrom, manualCheck, credentials } from '../../fixtures';
import { LoginScreen } from '../../screens/LoginScreen';
import { HomeScreen } from '../../screens/HomeScreen';
import { sendToBackground } from '../../helpers/appState';

describe('Login', () => {
  it('TC-E2E-POS-001 - Login - sign in with valid details', async () => {
    await startFrom('fresh install');                       // Preconditions: App freshly installed.
    const login = new LoginScreen();
    // 1. Open the app.  2. Tap Sign in.
    await login.openFromWelcome();
    // 3. Enter the email and password.
    const { user, password } = credentials('user');
    await login.enterEmail(user);
    await login.enterPassword(password);
    // 4. Tap Sign in.
    await login.tapSignIn();
    // Expected: the Home screen with the greeting "Welcome back".
    await new HomeScreen().waitUntilShown();
    await login.expectMessage('Welcome back');
  });

  it('TC-MOB-NEG-009 - Login - incoming call during sign in', async () => {
    return manualCheck('an incoming call cannot be triggered on a real device by the test run');
  });
});
```

- **One test per case**, titled exactly `<ID> - <Test Case Title>`.
- Steps in the code follow the case's steps **in order**, each with a short plain-English comment.
- **App state per case:** the first line of every test is `await startFrom('fresh install' | 'logged out' | 'logged in', '<role>')`, taken from the case's Preconditions (`app_state` is only a hint). Cases never depend on each other: no shared state between `it` blocks, no order dependence.
- Signed-in cases: `startFrom('logged in', 'admin')`. Sign-in cases themselves start `logged out` and use `credentials('<role>')`.

## Screen objects

- One class per screen in `screens/<Name>Screen.ts`, extending `BaseScreen`, built from that screen's JSON. `anchor` = a control that proves the screen is shown.
- Controls as `Loc` fields (`readonly email: Loc = { label: 'Email', key: 'email_field', name: 'Email field' }`), actions as methods named like the manual steps: `enterEmail()`, `tapSignIn()`, `openFromWelcome()`.
- Specs read like the manual steps; no raw strategies inside specs.

## Locators (section 3 of the plan)

Give each `Loc` every identifier the screen JSON has; `utils/flutter.ts` tries them in this order:
1. Semantics label (`label`) or Semantics identifier (`id`)
2. Flutter key (`key`, Flutter layer only)
3. Visible text (`text`, `textContains`)
4. Widget type (`type`) or tooltip (`tooltip`) – last resort

**Never** screen coordinates, never index-based paths, never XPath. If a control has nothing but a position (see `testability.md`), report it under `knowledge_gaps` and use the nearest labelled parent plus a gesture helper only if the case cannot be written otherwise.

## Waits and scrolling

- Wait for an expected control or message: `waitUntilShown()`, `expectShown()`, `expectMessage()`, `expectGone()` (all state waits with `WAIT_TIMEOUT_MS`).
- **Never** `driver.pause()` in a spec, never a fixed sleep. (`utils/flutter.ts` polls inside its waits; that is the only place.)
- Scroll until visible with `scrollTo(loc)` (the driver's scroll helper), never by swiping a fixed number of times.

## System pop-ups and the native layer

Permission pop-ups, the share sheet, notifications and system dialogs live outside Flutter: use `helpers/permissions.ts` (`answerPermission('deny')`, `isPermissionDialogShown()`) or `findNative()`; the Flutter Integration Driver switches between the app and the native layer by itself – no context switching in specs.

## Expected results

- Assert the exact message text and visible state from the Expected Result and `observations.md`.
- Every sentence of the Expected Result that can be checked objectively gets an assertion. Use `expect.soft` only where WebdriverIO supports it; otherwise assert the main check last.
- **Never** weaken or edit an assertion to make a case pass. If the expected result itself looks wrong, keep the faithful assertion and report it under `doubts`.

## Levels

| Level | How it is checked |
|---|---|
| CMP, INT, E2E | Through the app, as a user would (taps, typing, scrolling) |
| UI | Objective layout checks on the connected device: control visible and not covered (`isFullyVisible`, `isKeyboardShown`), rotation (`rotate`) when the app supports it, message wording. Subjective look-and-feel → `manualCheck` |
| MOB | Device controls: `sendToBackground()`, `reopen()`, `terminate()`/`launch()`, `answerPermission()`, `setPermissions()` (Android), `rotate()`, `goOffline()`/`goOnline()`/`wifiOnly()`, `openDeepLink()`, `back()`, `pullToRefresh()`. A network change returns `{ok, reason}`: when `ok` is false, `return manualCheck(\`the device did not allow the network change: ${r.reason}\`)` |

Cases the script cannot do on a real device: incoming calls, notifications arriving, low battery, airplane mode on most phones, changing language/dark mode/font size unless the plan allows it, anything on iOS that needs the Settings app:

```ts
it('TC-MOB-NEG-012 - Upload - low battery warning during upload', async () => {
  return manualCheck('a low battery warning cannot be triggered on a real device by the test run');
});
```

The case stays `PENDING` with `Needs manual check: <reason>` (`UNEXECUTED` in the report). It is not a failure and not a bug. Partially automatable cases: automate the objective part and add the manual part to the return notes.

API, security and accessibility cases are not part of this version (no such cases exist in the file).

## Data

- From the case's Test Data. Masked values map to `.env` through `credentials.map.json` (`User: <admin>` → `credentials('admin')`).
- Create flows use `uniqueEmail()`, `uniqueName()` so repeated runs do not collide.
- No real payments, no deleting accounts, no messages to real people unless the plan explicitly allows it.

## Return to the orchestrator

```json
{"flow": "<flow-key>", "spec": "mobile-automation/tests/<Suite>_<date>/<flow-key>.spec.ts",
 "screen_objects": ["screens/LoginScreen.ts (extended: openFromWelcome)", "screens/HomeScreen.ts (new)"],
 "cases": ["TC-…"],
 "manual": [{"id": "TC-MOB-NEG-012", "reason": "a low battery warning cannot be triggered on a real device"}],
 "knowledge_gaps": [{"id": "TC-…", "screen": "<screen>", "what": "the eye icon has no label or key"}],
 "doubts": [{"id": "TC-…", "what": "…"}],
 "typecheck": "passed"}
```

Run `cd mobile-automation && npx tsc --noEmit` before returning; it must pass.
