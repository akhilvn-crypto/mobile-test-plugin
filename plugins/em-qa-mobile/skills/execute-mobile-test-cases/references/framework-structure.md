# Framework structure (mobile-automation/)

The Appium automation lives in **`mobile-automation/`** at the project root (the web Playwright framework, if any, stays at the root and is never touched). It is WebdriverIO + TypeScript with Appium, created from `assets/framework-template/` on the first run and extended afterwards.

## Layout after the first run

```
<project root>
├── mobile-automation/
│   ├── package.json, tsconfig.json, .env.example, .env (git-ignored), .gitignore
│   ├── wdio.shared.conf.ts       # Appium address from .env, mocha, 1 instance, RETRIES, evidence hooks
│   ├── wdio.android.conf.ts      # UiAutomator2 / Flutter Integration Driver capabilities
│   ├── wdio.ios.conf.ts          # XCUITest / Flutter Integration Driver capabilities (macOS only)
│   ├── screens/                  # screen objects: BaseScreen, LoginScreen, <Name>Screen (shared across runs)
│   ├── helpers/                  # appState (fresh install / logged out / logged in, background, reopen, deep link),
│   │                             # permissions, network, orientation, logReader
│   ├── fixtures/                 # index.ts (startFrom, manualCheck, blockedCheck, credentials, data), auth.ts (signIn per role)
│   ├── utils/                    # env.ts, flutter.ts (locators and state waits), ist.ts, data.ts, device.ts
│   ├── tools/session-check.ts    # opens a session, says whether the Flutter layer can be reached
│   ├── test-data/credentials.map.json   # role -> .env variable NAMES
│   ├── reporters/results-reporter.ts    # results.json + evidence per case
│   ├── tests/<PlanName>_<Platform>_<YYYY-MM-DD>/<flow-key>.spec.ts
│   └── test-results/<PlanName>_<Platform>_<YYYY-MM-DD>/
│       ├── results.json          # one entry per case ID, merged across re-runs of the same day
│       └── evidence/<TC-ID>/     # attempt<n>_screenshot.png, attempt<n>_recording.mp4, attempt<n>_device-log.txt
│                                 # (failed attempts), retest_screenshot.png / retest_recording.mp4 (RETEST_EVIDENCE=1)
├── bugs/ , Test Reports/ , Test Cases/ , Exploration/
```

## Template files

| File | Content |
|---|---|
| `package.json` | `type: module`; `@wdio/cli`, `@wdio/local-runner`, `@wdio/mocha-framework`, `@wdio/spec-reporter`, `@wdio/globals`, `webdriverio`, `typescript`, `tsx`, `dotenv`. Scripts `test:android`, `test:ios`, `typecheck` |
| `wdio.shared.conf.ts` | Appium host/port/path from `APPIUM_URL`; `maxInstances: 1` (one device); mocha `retries` from `RETRIES` (default 1: a failed case runs once more automatically); `beforeTest`/`afterTest` call the results reporter |
| `wdio.android.conf.ts` | `FLUTTER_MODE=integration` → `appium:automationName: FlutterIntegration` (the build has `appium_flutter_server`; native locators still work through it); `native` → `UiAutomator2`. `appium:udid`, `appium:app` / `appium:appPackage`, `noReset: true`, `autoGrantPermissions: false` |
| `wdio.ios.conf.ts` | Same for iOS (`XCUITest`), plus WebDriverAgent signing (`IOS_XCODE_ORG_ID`, `IOS_XCODE_SIGNING_ID`) |
| `utils/flutter.ts` | `Loc` (label, id, key, text, textContains, type, tooltip), `find()` with a state wait (polling, never a fixed sleep) across the strategies in the agreed order, `isShown`, `waitGone`, `scrollTo` (Flutter `scrollTillVisible`, UiScrollable or `mobile: scroll`), `findNative` for system pop-ups |
| `screens/BaseScreen.ts` | `waitUntilShown`, `tap`, `longPress`, `enter`, `textOf`, `expectShown`, `expectGone`, `expectMessage`, `scrollTo`, `back`, `hideKeyboard`, `isKeyboardShown`, `pullToRefresh`, `swipe`, `isFullyVisible` |
| `helpers/appState.ts` | `startFrom(state, role)`, `launch`, `terminate`, `clearData`, `sendToBackground`, `reopen`, `state`, `isInForeground`, `openDeepLink` |
| `helpers/permissions.ts` | `isPermissionDialogShown`, `answerPermission('allow' \| 'while-using' \| 'only-this-time' \| 'deny' \| 'deny-dont-ask')`, `setPermissions('grant' \| 'revoke', [...])` (Android), `grantedPermissions` |
| `helpers/network.ts` | `goOffline`, `goOnline`, `wifiOnly`, `mobileDataOnly`, `setConnectivity` → `{ok, reason}`; a refused change becomes a manual check |
| `helpers/orientation.ts` | `rotate('LANDSCAPE' \| 'PORTRAIT')`, `resetToPortrait`, `screenSize` |
| `helpers/logReader.ts` | `readDeviceLog()` (logcat / syslog since the last read, secrets removed), `crashLines()` |
| `fixtures/index.ts` | `startFrom`, `signIn`, `manualCheck(reason)`, `blockedCheck(reason)`, `credentials`, `uniqueEmail` … |
| `reporters/results-reporter.ts` | `results.json`: `{id, title, file, status (passed/failed/manual/blocked), flaky, attempts, startedAt, endedAt, endedAtIst, durationMs, rawError, evidenceFiles[], manualReason, blockedReason, retestEvidence[], appCrashed, crashLines[], appState}` |

## Bootstrap (first run: `find_testcase.py` → `framework_exists: false`)

1. Copy every file of `assets/framework-template/` to `mobile-automation/` **without overwriting** anything that exists (check each file; never overwrite the user's `package.json`, `tsconfig.json`, configs or `.gitignore` – merge only what is missing and say so).
2. `cd mobile-automation && npm install` (only if `node_modules/@wdio/cli` is missing).
3. Appium drivers: `check_prerequisites.py --platform <p> --install` (installs `uiautomator2` / `xcuitest` and `appium-flutter-integration-driver` when missing).
4. `npx tsc --noEmit` must pass.
5. Report what was installed (npm packages, Appium drivers) in the final summary.

When `mobile-automation/` already exists: reuse it. Add only missing pieces and only when the config clearly lacks them; otherwise tell the user.

## .env and credentials

- `mobile-automation/.env` holds the real values (never copied anywhere): `APPIUM_URL`, `PLATFORM`, `DEVICE_UDID` (the selected real device), `APP_PATH` and/or `APP_ID`, `ANDROID_APP_ACTIVITY` (optional), `FLUTTER_MODE` (`integration` or `native` from the session check), `WAIT_TIMEOUT_MS`, `RETRIES`, one `<ROLE>_USER` / `<ROLE>_PASSWORD` pair per role, iOS signing values, and the optional `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` used by `file-bugs-to-jira`.
- `test-data/credentials.map.json` holds names only: `{"roles": {"admin": {"user": "ADMIN_USER", "password": "ADMIN_PASSWORD"}}}`.
- Test data in the test cases shows `User: <admin>` / `Password: ********`: map the role label to the entry in `credentials.map.json`.
- Never print `.env` values, never write them in specs, screen objects, test cases, bugs or reports.

## Naming and dated folders

- Suite = test plan name made path-safe + platform (`find_testcase.py` → `suite`): `Demo App Plan` on Android → `Demo_App_Plan_Android`.
- Run folder: `mobile-automation/tests/<Suite>_<YYYY-MM-DD>/` (IST date). One spec per flow: `<flow-key>.spec.ts`.
- Test title: `<TC-ID> - <Test Case Title>`. The ID at the start is how results map back.
- Same plan and platform, same day → reuse that folder. New day → create the new folder and **copy the specs of unchanged flows** from the latest earlier folder (`previous_suite_dir`); write only new or changed cases. A flow is unchanged when its cases' steps, data and expected results are the same as when the spec was written (the spec header comment stores the test case file name and version).
- Screen objects, helpers, fixtures and utils are shared: a dated folder only holds specs.

## Commands (always from `mobile-automation/`)

| Need | Command |
|---|---|
| Type check | `npx tsc --noEmit` |
| Session / Flutter layer check | `npx tsx tools/session-check.ts --platform android` |
| Whole suite | `npx wdio run wdio.android.conf.ts --spec "tests/<Suite>_<date>/*.spec.ts"` |
| One flow | `npx wdio run wdio.android.conf.ts --spec "tests/<Suite>_<date>/<flow>.spec.ts"` |
| One case | `… --spec "tests/<Suite>_<date>/<flow>.spec.ts" --mochaOpts.grep "TC-UI-NEG-014"` |
| No automatic re-run (bug reproduction) | prefix `RETRIES=0` (PowerShell: `$env:RETRIES='0';`) |
| Retest evidence for bugs filed in Jira | prefix `RETEST_EVIDENCE=1` |

There is no "list" mode: confirm the tests exist with `grep -c "it('TC-" tests/<Suite>_<date>/*.spec.ts` and that every case ID to run appears in a test title.
