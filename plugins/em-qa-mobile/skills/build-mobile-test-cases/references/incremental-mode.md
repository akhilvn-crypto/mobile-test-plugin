# Incremental mode (mobile)

Goal: on a re-run for the same plan and platform, explore **only what changed**. The app build gives a cheap and reliable signal: **if the documents, the plan and the app file hash are unchanged, stop without opening the device and spend no more tokens.**

Everything below is per platform: `manifest.json` → `platforms.<android|ios>`.

## What is hashed

| Item | Hash input | Stored as |
|---|---|---|
| Each project document | raw file bytes (sha256), keyed by path relative to `--project-dir` | `doc_hashes{}` |
| Whole plan | normalised plan text | `plan_hash` |
| Plan common part | normalised text of everything that is not a flow section (platform, app, device, credentials, data, out-of-scope) | `common_hash` |
| Each flow | normalised text of that flow's section | `flows.<key>.section_hash` |
| **App build** | sha256 of the APK/IPA file; for an app given only by package name, the sha256 of the installed APK on the device; else version + build number | `app_hash` (+ `app_version`, `app_build`) |
| Each screen | fingerprint of its screen JSON | `flows.<key>.screens[].fingerprint` |

Normalisation: line endings unified, trailing spaces removed, runs of blank lines collapsed, so re-saving a file does not count as a change.

## How the plan is split into flows

Same as web (`snapshot_diff.py plan`): plan name from YAML `title:` / first H1 / first line; flows = children of a `Flows` / `Test Flows` / `Scenarios` heading, else headings starting with `Flow`, else every H2 that is not a common section. Common sections include the mobile ones: Platform(s), App, App build, Device(s), Appium, Permissions, Test environment. `plan` also prints `environment` hints (platforms, app files, package ids, device, Appium address) – the skill reads the plan itself and decides.

## Decision (`snapshot_diff.py compare --platform <p> --app <file or id>`)

| Situation | Decision | Action |
|---|---|---|
| No exploration for this platform, or `--force-full` | `full` | Archive (force-full only), explore every flow |
| Documents, plan **and app hash** all unchanged | `stop` (`needs_device: false`) | **Stop.** No device needed, no files created. Print `No changes detected, existing test cases are still valid.` |
| App build changed, documents and plan unchanged | `check-drift` | **Light check** of the unchanged flows (action `light-check`), then call `compare` again with `--drift -` |
| Flow edited or new in the plan | `partial` | Explore that flow only (`full-explore`). Unchanged flows get `light-check` only when the app build also changed |
| Flow removed from the plan | `partial` | `archive`: mark `archived` in the manifest, keep the files, its cases get `[OBSOLETE]` |
| Plan common part changed (credentials, data, device) | `partial` | No re-exploration for that alone; the designer re-checks every case that uses the changed data |
| Project documents changed | `partial` | Regenerate `project-understanding.md`; re-check cases touching the changed features |

Second call with the light-check data (`--drift <file>` or `--drift -`):

| Result | Meaning | Next step |
|---|---|---|
| `partial` with `screens_drifted` | Some screens changed | `recapture-screens` for those screens only, regenerate only the affected cases |
| `stop` with `update_app_only: true` | New build, no screen changed | `snapshot_diff.py update-app --plan-dir … --platform … --app … --drift -` (records the new build so the next run stops without the device), print `No changes detected, existing test cases are still valid.` and add "The new app build <version> (<build>) was checked; no screen changed." No test case file is written |

## Light-check JSON

A quick visit to each screen listed in the manifest for every **unchanged, active** flow: follow `reached_by`, read the page source, build the screen structure. No screenshots, no recording, **no files written in the project**. Hand the result to `compare` via stdin (or a temp file outside the project, deleted afterwards):

```json
{
  "login": [
    {"screen": "login", "structure": {"title": "Sign in", "controls": [...], "input_fields": [...]}},
    {"screen": "home", "fingerprint": "sha256…"},
    {"screen": "settings", "unreachable": true}
  ]
}
```

A screen is **changed** when its fingerprint differs, it is unreachable, or it is a manifest screen missing from the data.

Screens refreshed by `execute-mobile-test-cases` carry `"updated_by": "execute-mobile-test-cases"`; that skill updates the manifest fingerprint at the same time. Treat them as valid captures.

## After exploration and design

1. Archive replaced files to the flow's `history/<IST-timestamp>/` (`snapshot_diff.py archive`).
2. Write `runs/<IST-timestamp>/changes.md`: one `## <Platform>` section per platform with what changed (docs, flows, app build old → new, screens), what was re-explored, cases added/updated/obsoleted, version change.
3. Write the new output file (never overwrite earlier ones).
4. `snapshot_diff.py update-manifest --platform <p> --app <file or id> --serial <serial> --device "<model>" --os-version "<OS>" …` with the new output file, version, mode and summary.

## Versioning and carry-over of IDs

Same as web:
- Start from the previous output of this platform (`platforms.<p>.last_output_file`). Copy every case of unchanged flows exactly – same ID, same execution columns – and **clear** a previous `[NEW]` / `[UPDATED]` tag.
- Changed case: same ID, new content, Comments `[UPDATED]`, execution columns reset.
- New case: next running number (`lint_testcases.py <previous.md> --stats` → `max_number` + 1), Comments `[NEW]`.
- Case no longer valid: keep the row, Comments `[OBSOLETE]`; it leaves the coverage matrix and the conditions table.
- Never renumber, never reuse a number.
- Version: `V1.0` → `V1.1` → … per platform file; add a Version History row with the change summary. A new app build that changed screens is named in the row: `Re-run: app 2.4.2 (build 124), Login screen changed (1 updated)`.
- If the team edited the previous XLSX, that data is not read back. Say so in the summary when relevant.
