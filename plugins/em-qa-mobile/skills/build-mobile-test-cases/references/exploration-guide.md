# Exploration guide (mobile)

Exploration knowledge lives in `Exploration/<plan-key>/<platform>/` in the user's project root – never inside `Test Cases/`. One `qa-mobile-explorer` explores **one flow** on the **one selected real device** and writes only inside its own `<platform>/<flow-key>/` folder. Flows run **one after another** (one device, one driver).

## Folder layout

```
Exploration/<plan-key>/
├── manifest.json                    <- written only by snapshot_diff.py update-manifest / update-app
├── project-understanding.md         <- written by the main skill (Phase 1)
├── history/<IST-timestamp>/         <- plan-level files archived by --force-full
├── android/                         <- or ios/
│   └── <flow-key>/
│       ├── observations.md
│       ├── screens/<screen>.json    <- one file per screen
│       ├── screenshots/<screen>__<state>.png
│       ├── recordings/<flow-key>.mp4
│       ├── logs/<flow-key>_device-log.txt   (secrets removed; crash evidence)
│       ├── testability.md           <- controls without a label or key
│       └── history/<IST-timestamp>/ <- replaced files, same relative paths
└── runs/<IST-timestamp>/changes.md
```

- `plan-key` = slug of the test plan **file name** (`parse_args.py` prints it).
- `flow-key` = slug of the flow heading without `Flow 3:` numbering (`snapshot_diff.py plan` prints it).
- `<screen>` = short slug of the screen: `login`, `home`, `profile-edit`. Screenshot states: `login__empty-submit.png`, `login__landscape.png`, `login__keyboard-open.png`, `home__dark-mode.png`.

## Driving the device

### Appium MCP (main tool)

The Appium MCP server (`appium-mcp`) plays the role Playwright plays on web. Its tools are often *deferred*: load them first with ToolSearch (query `appium`, or `select:<full names>`). Names end in: `select_device`, `appium_session_management`, `appium_find_element`, `appium_gesture`, `appium_set_value`, `appium_get_text`, `appium_get_page_source`, `appium_screenshot`, `appium_screen_recording`, `appium_app_lifecycle`, `appium_mobile_keyboard`, `appium_alert`, `appium_context`, `appium_mobile_device_control`, `appium_driver_settings`; more may exist (orientation, permissions, deep links) – use what the server offers.

1. **Pick the device:** `select_device` with the serial/UDID from Phase 0 (a real device; never an emulator or simulator).
2. **Session through the local Appium server** (it has the Flutter driver installed): `appium_session_management` with `action=create`, `remoteServerUrl` = the Appium address from Phase 0 (default `http://127.0.0.1:4723`), and capabilities:
   - Android, Flutter layer: `platformName: Android`, `appium:automationName: FlutterIntegration`, `appium:udid`, `appium:app` (APK path) or `appium:appPackage`, `appium:noReset: true`, `appium:flutterServerLaunchTimeout: 60000`.
   - iOS, Flutter layer: `platformName: iOS`, `appium:automationName: FlutterIntegration`, `appium:udid`, `appium:app` (IPA) or `appium:bundleId`, WebDriverAgent signing capabilities.
3. **Check the Flutter layer at the start.** The session opens only when the build contains `appium_flutter_server`. If it fails with a Flutter server error, create the session again with `appium:automationName: UiAutomator2` (Android) / `XCUITest` (iOS) – the **native fallback** – and write in `observations.md`: `Flutter layer: not reachable (<reason>); explored through the accessibility tree.` Record `Flutter layer: reachable` otherwise.
4. **Find controls** in the locator order the scripts will use: Semantics label (`accessibility id`), Semantics identifier (`id` on Android), Flutter key (`-flutter key`, Flutter layer only), visible text (`-flutter text`, or `-android uiautomator` `new UiSelector().text("…")` natively), widget type / tooltip last. **Never** tap screen coordinates to explore; if a control can only be reached by coordinates, that is a testability finding.
5. **Read the screen:** `appium_get_page_source` (native accessibility tree: labels, resource ids, classes, `clickable`, `enabled`, bounds) plus `appium_screenshot`. On the Flutter layer the page source shows only what Flutter exposes; the Flutter driver's `flutter: renderTree` command (through an execute tool if the server has one) lists keys and widget types.
6. **Act:** `appium_gesture` (`tap`, `double_tap`, `long_press`, `swipe`, `scroll`, `scroll_to_element`, `back`), `appium_set_value` to type, `appium_mobile_keyboard` to hide the keyboard, `appium_alert` for system alerts.
7. **Record:** `appium_screen_recording` `action=start` at the start of a full exploration, `action=stop` at the end → copy the MP4 to `recordings/<flow-key>.mp4`. Screenshots → copy into `screenshots/` with meaningful names. (The MCP saves files to its own folder, `SCREENSHOTS_DIR` or the temp folder; copy them, then leave the temp files.)
8. **End:** `appium_session_management` `action=delete` – always, even after an error.

### adb / Xcode tools (through Bash) for what the MCP lacks

Android (always with `-s <serial>`):

| Need | Command |
|---|---|
| Install / reinstall the test build | `adb -s S install -r -t "<apk>"` |
| Clear app data (fresh state) | `adb -s S shell pm clear <package>` |
| Start / stop the app | `adb -s S shell monkey -p <package> -c android.intent.category.LAUNCHER 1` / `adb -s S shell am force-stop <package>` |
| Minimise / return | `adb -s S shell input keyevent KEYCODE_HOME`, then start the app again |
| System back | `adb -s S shell input keyevent KEYCODE_BACK` |
| Grant / revoke a permission | `adb -s S shell pm grant <package> android.permission.<NAME>` / `pm revoke …` (only when the plan allows the tester to change permissions) |
| Orientation | `adb -s S shell settings put system accelerometer_rotation 0` then `settings put system user_rotation 1` (landscape) / `0` (portrait); put both back afterwards |
| Deep link | `adb -s S shell am start -W -a android.intent.action.VIEW -d "<url>" <package>` |
| Device log | `adb -s S logcat -c` at the start; `adb -s S logcat -d -v time > "<tmp>/raw.txt"` at the end (then scrub, below) |
| Screen recording (if the MCP cannot) | `adb -s S shell screenrecord --time-limit 170 /sdcard/<flow>.mp4` then `adb -s S pull /sdcard/<flow>.mp4 "<flow_dir>/recordings/"` and `adb -s S shell rm /sdcard/<flow>.mp4` |
| Screenshot (if the MCP cannot) | `adb -s S exec-out screencap -p > "<flow_dir>/screenshots/<screen>__<state>.png"` |

iOS (macOS): `xcrun devicectl` / `idevicesyslog` for logs; screenshots and recordings through the MCP.

**Never** change device settings (language, dark mode, Wi-Fi, airplane mode, font size) unless the plan explicitly allows it; put anything you changed back. Keep the device unlocked and awake; if it locks, ask the orchestrator to tell the user.

## How to explore (behave like a real user and a QA engineer)

Scope: **only the flow you were given**. Stay inside the app; do not open other apps beyond the system pop-ups the flow triggers.

1. **First launch** (fresh app state, if the flow starts there): onboarding, permission pop-ups and their exact texts.
2. **Happy path first**, exactly as the plan describes it. Capture each screen you reach.
3. **Invalid input**: empty submit, wrong formats, too long values, emoji, special characters. Write down the **exact** message text.
4. **Empty states**: lists with no data, search with no results.
5. **Back navigation**: system back button / back gesture on each step; note lost data or broken states.
6. **Scrolling and pull to refresh** on lists; scroll to the end of long lists.
7. **Keyboard**: does it cover the active field or the main button? Does the right keyboard type appear (email, number)? Does "Next" move between fields?
8. **Mobile conditions** from `mobile-conditions.md` that the device allows without changing settings: minimise and reopen, close and reopen, permission allow/deny (only the permissions the plan lets the tester grant), rotation (if the app supports it).
9. **Other roles**: repeat key steps with each role the plan gives credentials for.
10. Watch the device log for crashes (`FATAL EXCEPTION`, `ANR in`, `E/flutter`, `Unhandled Exception`) throughout.

**Never** do destructive actions (delete account, payments, sending real messages to real people, changing shared passwords) unless the plan explicitly allows them. Stop before the final confirmation and record what you saw.

Use the plan's credentials **only to sign in**. Never write them anywhere – write `Password: ********` / `Email: <from test plan>`.

## What to capture per screen

### `screens/<screen>.json`

```json
{
  "screen": "login",
  "platform": "android",
  "captured_ist": "03-10-2026 17:45:09 IST",
  "reached_by": "App launch (fresh install) > tap 'Sign in'",
  "title": "Sign in",
  "layer": "flutter",
  "controls": [
    {"label": "Email", "type": "text field", "enabled": true, "size": "328x56", "has_label": true, "key": "email_field", "id": ""},
    {"label": "Password", "type": "text field", "enabled": true, "size": "328x56", "has_label": true, "key": "", "id": "password"},
    {"label": "", "type": "icon button", "enabled": true, "size": "48x48", "has_label": false, "key": "", "id": "", "note": "eye icon next to Password"},
    {"label": "Sign in", "type": "button", "enabled": false, "size": "328x48", "has_label": true, "key": "sign_in", "id": ""}
  ],
  "input_fields": [
    {"label": "Email", "type": "email", "required": true, "rules": "valid email format", "keyboard": "email"},
    {"label": "Password", "type": "password", "required": true, "rules": "min 8 characters (from PRD)", "keyboard": "text, hidden"}
  ],
  "messages": ["Enter a valid email address.", "Password is required."],
  "fingerprint": "sha256… (written by snapshot_diff.py fingerprint --write)"
}
```

- `layer`: `flutter` (reached through the Flutter layer) or `native` (accessibility tree fallback).
- `controls`: every tappable or readable control. `label` = the Semantics/accessibility label as exposed; `has_label` false when the control has no label **and** no visible text; `key` = Flutter key when the Flutter layer shows one; `id` = Semantics identifier (Android resource id) when present. Types in plain words: button, text field, switch, checkbox, list item, tab, icon button, image, link.
- `messages`: visible texts **exactly** as shown (snackbars, dialogs, field messages, empty states, permission explanations).
- After writing the files: `python "<skill_dir>/scripts/snapshot_diff.py" fingerprint --write "<flow_dir>/screens/"*.json`. The fingerprint uses title, controls (label, type, key, labelled or not) and input fields; enabled state, sizes and messages are left out, and digits are normalised, so counters do not cause false changes.

### `screenshots/`
One per screen in its default state, plus one per interesting state (validation errors, empty state, keyboard open, landscape, permission pop-up). Mask nothing by hand – just never type real secrets into a field that stays visible; if a screenshot shows a credential, delete it and take a new one after clearing the field.

### `recordings/<flow-key>.mp4`
One screen recording of the whole full-mode exploration. If recording fails, write `Recording not available: <reason>` in `observations.md`. Do not fake it.

### `logs/<flow-key>_device-log.txt`
An excerpt of the device log around anything interesting (crash, error, freeze), not the whole log. **Always scrub before leaving it on disk:**

```
python "<skill_dir>/scripts/snapshot_diff.py" scrub "<flow_dir>/logs/<flow-key>_device-log.txt" --secret "<password>" --secret "<username>"
```

Scrubbing replaces Bearer/Basic tokens, JWTs, `password=` / `token:` style values, and every `--secret` value with `********`. Write "No crash or error observed." in `observations.md` when the log showed nothing.

### `testability.md`

```
# <Flow name> – testability findings (<platform>)
Controls a tester or a script cannot identify reliably. Adding a Semantics label or a Key makes automation reliable.
This is a note for the team, not an accessibility check.

| Screen | Control (what it looks like) | Problem | Suggestion |
|---|---|---|---|
| login | Eye icon next to Password | No label, no key, no visible text | Add a Semantics label, e.g. "Show password" |
| home | Third icon in the bottom bar | Reachable only by position | Add a Key or Semantics label |
```
Write "No findings." when every control has a label, key or visible text.

### `observations.md`

```
# <Flow name> – observations (<platform>)
Explored at: <IST cell timestamp>   Mode: full | recapture-screens | light-check
Device: <model> (real device), <OS>   App: <version> (build <n>)   Flutter layer: reachable | not reachable (<reason>)
## Screens visited
## Happy path (as observed)
## Validation and error messages (exact text)
## Empty states / back navigation / scrolling / keyboard
## Mobile conditions tried        <- minimise/reopen, permissions, rotation… and what happened; conditions not tried and why
## Roles
## Crashes and device log         <- "No crash or error observed." or what the log showed (scrubbed)
## Mismatches with docs or plan   <- "Docs say X; app does Y." Never guess which is right.
## Blockers                       <- e.g. sign-in failed, screen not reachable, device locked
```

## Re-runs

- **Light check** (app build changed, flow unchanged): open the app, go to each screen listed for the flow (follow `reached_by`), read the page source and build the screen JSON **in memory only**. No screenshots, no recording, no files in the project. Return the light-check JSON (`incremental-mode.md`) to the orchestrator.
- **Screen re-capture** (a screen changed in an unchanged flow): archive the screen's old files first –
  `python "<skill_dir>/scripts/snapshot_diff.py" archive --flow-dir "<flow_dir>" --files screens/<screen>.json "screenshots/<screen>__*"`
  – then capture only that screen again (JSON, screenshots, testability rows of that screen). Append a dated note to `observations.md`.
- **Full flow exploration** (flow new or edited, or `--force-full`): `archive --flow-dir "<flow_dir>" --all` first, then explore as above.

## manifest.json

Written by `snapshot_diff.py update-manifest` (after an output) and `update-app` (light check without changes) only; never hand-edit.

```json
{
  "plan_key": "demo-app-plan",
  "plan_name": "Demo App Plan",
  "plan_file": "plans/Demo App Plan.md",
  "test_plan_path": "plans/Demo App Plan.md",
  "platforms": {
    "android": {
      "platform": "android",
      "app_file_path": "builds/app-debug.apk", "app_id": "com.example.demo",
      "app_hash": "sha256 of the APK", "app_version": "2.4.1", "app_build": "123",
      "device": "Pixel 7", "os_version": "Android 14", "flutter_layer": true,
      "plan_hash": "…", "common_hash": "…", "doc_hashes": {"PRD.pdf": "…"},
      "flows": {
        "login": {"flow_key": "login", "name": "Login", "section_hash": "…", "status": "active",
                  "user_story_ref": "#12", "user_story_title": "Sign in with email",
                  "screens": [{"screen": "login", "reached_by": "App launch > Sign in", "fingerprint": "…",
                               "last_captured_ist": "03-10-2026 17:45:09 IST"}]}
      },
      "last_output_file": "Test Cases/Demo App Plan_Android_2026-10-03_17-45-09-IST.md",
      "version": "V1.0",
      "runs": [{"at_ist": "…", "mode": "first", "output": "…", "version": "V1.0", "summary": "Initial generation"}],
      "outputs": [{"file": "Test Cases/…md", "at_ist": "…", "version": "V1.0"}]
    }
  }
}
```

No credentials, tokens or device logs ever go into the manifest.
