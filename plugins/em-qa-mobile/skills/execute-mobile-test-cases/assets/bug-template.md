# BUG-<NNN>: <Feature> - <what is wrong>

| Field | Value |
|---|---|
| Severity | <Critical \| Major \| Minor \| Trivial> |
| Priority | <High \| Medium \| Low> |
| Status | Open |
| Platform | <Android \| iOS> |
| Test case(s) | <TC-…> |
| Test case file | <exact test case file name, e.g. Demo App Plan_Android_2026-10-03_10-44-55-IST.md> |
| Reported on | <dd-mm-yyyy hh:mm:ss IST> |
| Jira | Not filed |

## Summary
<One line: what is wrong and where.>

## Description
<Two or three plain sentences: what the user tries to do, what goes wrong and why it matters. Say whether it
happened on one device or on both when a second real device was tried.>

## Steps to Reproduce
1. Open the app <from a fresh install | signed out | signed in as <role>>.
2. Tap <control>.
3. Enter "<value>" in the <field> field.
4. Tap <button>.

## Expected Result
<What should happen, with the exact message text in quotes.>

## Actual Result
<What the user sees instead, with the exact text in quotes. For a crash: "The app closes by itself after tapping
Save and returns to the home screen. The entry is not saved.">

## Environment
- App: <app name> <version> (build <number>)
- Device: <model> (real device)
- Operating system: <Android 14 | iOS 17.5>
- Network: <Wi-Fi | mobile data | offline>
- Screen: <portrait or landscape>, <language>, <dark mode on/off if relevant>
- User/role: <role, never the password>

## Insights for Developers
- <What the device log shows, quoted exactly as the app printed it: The device log shows: "<text>".>
- <When it happens: every time from a fresh app state / only after minimising the app / only on this device.>
- Possible cause: <a short possibility, clearly marked as such>.

## Attachments
- screenshots/BUG-<NNN>_<what-it-shows>.png
- recordings/BUG-<NNN>_<what-it-shows>.mp4
- logs/BUG-<NNN>_device-log.txt
