# em-qa-mobile marketplace

Claude Code marketplace for the **em-qa-mobile** plugin: the mobile half of the Emvigo QA toolkit, for **Flutter** apps tested with **Appium** on **real devices**. It has the same structure, output formats and rules as the web plugin (`em-qa-agent`); only the mobile differences are new.

| Command | What it does |
|---|---|
| `/em-qa-mobile:build-mobile-test-cases --project-dir <dir> --test-plan <file> [--xlsx] [--force-full]` | Checks the prerequisites and the real device, explores the plan's flows on the phone with the Appium MCP tools, stores the knowledge in `Exploration/<plan-key>/<platform>/`, and writes human-style test cases (CMP, INT, E2E, UI, MOB) to `Test Cases/<Plan>_<Platform>_<ts>-IST.md` (XLSX with `--xlsx`). One file per platform. A re-run with unchanged docs, plan and app build stops without opening the device. |
| `/em-qa-mobile:execute-mobile-test-cases --testcase "<file name>" [--test-report xlsx]` | Writes WebdriverIO + TypeScript Appium scripts in `mobile-automation/` from the stored knowledge, runs them one by one on the real device, fixes script problems, writes results back to the MD/XLSX, files genuine bugs in `bugs/` (screenshot, MP4 recording, device log), and writes a test report to `Test Reports/`. |
| `/em-qa-mobile:file-bugs-to-jira [--bug-id <BUG-ID>] [--link-story <STORY-KEY>]` | The web `file-bugs-to-jira`, extended for mobile: mobile Environment lines, `mobile` + `android`/`ios` labels, evidence uploaded when the Jira REST settings exist (size limit checked, big recordings shrunk with ffmpeg or reported), possible duplicates on the other platform, closing with the retest device/OS/build. Handles web bugs exactly as before. |

Agents (namespaced `em-qa-mobile:`): `qa-mobile-explorer`, `qa-mobile-script-writer`, `qa-mobile-bug-reviewer`, `qa-reviewer` (the web reviewer with the mobile terms).

Out of scope for now: API, security and accessibility testing (level codes reserved), emulators and simulators, parallel devices, device farms, performance/battery/install/upgrade, push notifications, biometrics.

## Install

```
/plugin marketplace add akhilvn-crypto/mobile-test-plugin      # or a local path to this folder
/plugin install em-qa-mobile@em-qa-mobile-marketplace
```

The plugin ships an MCP config for the Appium MCP server (`npx -y appium-mcp@latest`). If its tools do not show up (for example on native Windows), add it once yourself:

```
claude mcp add appium-mcp -- npx -y appium-mcp@latest            # macOS / Linux
claude mcp add appium-mcp -- cmd /c npx -y appium-mcp@latest     # Windows
```

## Requirements (checked in Phase 0, with the exact fix for anything missing)

- Python 3.10+ with `openpyxl` (XLSX test cases and reports).
- Node.js 22+ and npm; Java 8+.
- Android: Android SDK with `ANDROID_HOME` and `adb`. iOS: a Mac with Xcode and a provisioned iPhone (developer mode, WebDriverAgent signing).
- Appium 3 with the drivers `uiautomator2` / `xcuitest` and `appium-flutter-integration-driver` (installed by the skill when missing: `--install`).
- **A real device** connected by USB (Android: USB debugging on and authorised; iPhone: trusted, developer mode on). Emulators and simulators are refused.
- **A Flutter test build** with `appium_flutter_server` in `pubspec.yaml` and `integration_test/appium_test.dart` (Android: debug build, `./gradlew app:assembleDebug -Ptarget=<project>/integration_test/appium_test.dart`; real iPhone: release build, `flutter build ipa --release integration_test/appium_test.dart`). A normal store build does not contain it; then only the native fallback (Semantics labels and identifiers) is possible, with limited coverage.
- Optional: `ffmpeg` (shrinks large screen recordings for Jira).
- Jira: the Atlassian Rovo connector. For uploading mobile evidence, also `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` in `mobile-automation/.env` (or the root `.env`).

## What the test plan must contain (mobile)

Platform(s); the app file (APK/IPA path) or the package name / bundle id of an installed app; the real device to use (name and OS); the Appium address (default local); credentials and roles; flows (with story references if any); allowed actions; permissions the tester may grant; test data; out-of-scope items. Without an app file or identifier the skill stops.

## Project layout it uses

```
Test Cases/        <Plan>_<Platform>_<YYYY-MM-DD>_<HH-MM-SS>-IST.md (+ .xlsx)       shared with web
Test Reports/      <Plan>_<Platform>_Test_Report_<…>-IST.md (+ .xlsx)                shared with web
Exploration/<plan-key>/manifest.json, project-understanding.md, <platform>/<flow>/…, runs/<ts>/changes.md
bugs/              shared with web (one running BUG-nnn); mobile bugs also have logs/; jira-sync.json
mobile-automation/ the Appium framework (WebdriverIO + TypeScript), with its own git-ignored .env
```

## Shared with the web plugin

The folders above, the Jira state file, the bug numbering and the XLSX templates. The wording list `skills/execute-mobile-test-cases/assets/banned-terms.txt` holds the web and the mobile terms; the web skills should use the same list (copy it over `em-qa-agent`'s `execute-test-cases/assets/banned-terms.txt`).
