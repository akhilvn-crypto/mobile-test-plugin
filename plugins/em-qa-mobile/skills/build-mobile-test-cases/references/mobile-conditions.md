# Mobile conditions (MOB cases)

Considered for **every flow where they apply**. Each MOB case says in its Preconditions what it needs. Cases that the test run cannot set up on a real device are still written; at execution time they stay `PENDING` with `Needs manual check: <reason>` in Comments (shown as `UNEXECUTED` in the report).

| Group | What to consider | Can the test run do it on a real device? |
|---|---|---|
| **App lifecycle** | First launch (onboarding, permission pop-ups), close and reopen, put in background (minimise) and return, restart after a forced stop, data kept or cleared as the docs say | Yes (minimise for some seconds, close, reopen, clear app data) |
| **Permissions** | Allow, deny, deny with "don't ask again", allow only this time / while using, turn off later in settings and come back | Android: yes (answer the pop-up, grant/revoke from outside the app). iOS: answering the pop-up yes; turning off later in Settings needs a person |
| **Interruptions** | Incoming call, notification arriving, low battery warning, alarm | **No** – write the case and leave it for a manual check |
| **Network** | No connection, connection lost during an action, slow connection, switching Wi-Fi and mobile data | Android: Wi-Fi and mobile data usually yes; airplane mode and slow connection usually not (needs a rooted phone). iOS: no. Otherwise manual check |
| **Orientation** | Portrait and landscape, rotating during input or loading – only if the app supports both | Yes |
| **Device settings** | Language, dark mode, font/display size, the screen size of the connected device | Dark mode and language need the phone's settings: manual check unless the plan says the tester may change them. Screen size: the connected device only |
| **Navigation** | System back button or back gesture, deep links, pull to refresh, scroll to the end of long lists | Yes (back, deep links on Android and iOS, pull to refresh, scrolling) |

## How to write them

- Title names the condition: `Profile - photo upload continues after minimising the app`, `Store finder - location permission denied`.
- Preconditions: `App freshly installed. Location permission not yet granted.`, `Signed in as <user>. Wi-Fi on, mobile data off.`
- Steps say exactly what the tester does to the device: `Minimise the app for 10 seconds.`, `Turn on airplane mode.`, `Rotate the device to landscape.`, `Tap Don't allow on the permission pop-up.`, `Swipe from the left edge to go back.`
- Expected result: what the user sees after the condition (message text, data kept, screen shown).
- Do not change device settings during exploration unless the plan allows it; write the case from the documents and mark it in Observations as not explored.

## Not covered in v1

Performance, battery drain, install and upgrade testing, push notifications and biometrics. Mention them in Observations when the documents ask for them.
