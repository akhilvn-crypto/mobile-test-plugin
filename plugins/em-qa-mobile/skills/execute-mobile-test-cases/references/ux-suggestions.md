# UX suggestions (mobile)

While executing, note improvements a real QA engineer would mention to the product team.

## What counts

- Only what was **actually seen** during this run (in a screenshot, a recording, or a screen you looked at). Never invent, never repeat generic best practice that does not apply to what you saw.
- Friction for the user, for example:
  - the **keyboard covers** the active field or the main button;
  - the screen loses entered data or scroll position **after rotation** or after minimising the app;
  - **layout on the connected device**: text cut off, buttons too close together or too small to tap comfortably, content hidden behind the system bars or the notch;
  - a message that disappears too fast, unclear wording, a missing confirmation, an empty state that gives no next step;
  - a **permission asked without explanation**, or asked again right after it was denied;
  - pull to refresh missing on a list that clearly changes, the back gesture leaving the app unexpectedly.
- Not a defect: if the app breaks an expected result, it is a bug (or a test case problem), not a suggestion.

## How to write one

One or two plain sentences with three parts: **where** (screen or step), **what was noticed**, **the improvement and its benefit**.

Examples:
- *"On the Sign in screen, the keyboard covers the Sign in button on the Pixel 7. Moving the button up or letting the screen scroll would let users sign in without closing the keyboard."*
- *"On the Edit profile screen, rotating the phone clears the Name field. Keeping the entered text after rotation would save users from typing it again."*
- *"The app asks for location access on first launch without saying why. A short explanation before the pop-up would make it more likely that users allow it."*

## Limits and placement

- **Up to 5 per run**; pick the ones with the most user impact.
- Plain language, no tool terms (same banned list as bugs and the report).
- They appear only in the MD test report (`ux_suggestions` in the report context). They are never filed as bugs.
