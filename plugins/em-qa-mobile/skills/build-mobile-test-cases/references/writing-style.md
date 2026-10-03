# Writing style (mobile)

Test cases must read as if a human QA engineer wrote them for a manual tester holding the phone.

**Do**
- Use mobile words: open the app, tap, double tap, long press, swipe, scroll, pull to refresh, enter, rotate the device, minimise the app, reopen the app, close the app, allow or deny the permission, turn on airplane mode, turn off Wi-Fi, go back (system back button or gesture).
- Title: `<Feature> - <what is verified>`. Description: one sentence starting "Verify that…".
- Steps: short imperative lines, 3 to 6 per case, one action each. The first step starts from a state anyone can reach: "Open the app.", "Open the app and sign in as <role>.".
- Preconditions: the app state (`App freshly installed.`, `Signed out.`, `Signed in as <role>.`) and, for MOB cases, the device condition the case needs.
- Expected result: what the user sees, with the **exact message text** where the app shows one (snackbar, dialog, field message, permission explanation).
- One purpose per case. One case per meaningful value or boundary.
- Test data as `Label: value` lines. Mask passwords, PINs, OTPs and tokens.
- No API, security or accessibility cases (out of scope for now).

**Do not** (the lint script flags these)
- Automation or tool terms: Appium, WebdriverIO, driver, capabilities, session, XPath, resource id, content description, accessibility id, UiSelector, widget tree, context, `NATIVE_APP`, `FLUTTER`, adb, logcat, Semantics, and the web terms (Playwright, locator, selector, DOM, fixture, snapshot, trace, assert…).
- Phrases like "network call", "XHR", "intercept" or "mock".
- Long run-on steps, filler ("ensure that", "successfully validate"), or more than one verification theme per case.
- Any reference to screenshots, recordings, device logs or exploration files.

Exact app text in double quotes is exempt: `The message "Your session has expired." is shown.` is fine; `Verify that the session expires` is not ("Verify that the sign-in expires after 15 minutes").

**Example**
- Machine-like: *"Find element by accessibility id 'Subscribe' and click, assert text of snackbar."*
- Human-like:
  - Steps: 1. Open the Subscribe screen. 2. Enter an invalid email address. 3. Tap Subscribe.
  - Expected: The message "Enter a valid email address." is shown below the field.
- MOB example:
  - Preconditions: App freshly installed. Location permission not yet granted.
  - Steps: 1. Open the app. 2. Tap Find stores. 3. Tap Don't allow on the location pop-up.
  - Expected: The message "Allow location to see stores near you." is shown with a Settings button.
