# Coverage matrix (mobile)

Each flow section ends with a coverage matrix: **5 in-scope levels × 6 scenario types = 30 cells**, followed by the **mobile conditions table** (7 condition groups). API, security and accessibility are out of scope for now and have no row.

A matrix cell lists the IDs of the cases that cover it (comma-separated), or `N/A – <reason>` when no case applies. An empty cell, or `N/A` without a reason, is a lint error. IDs in a cell must match the level and type in the ID, and every case in the flow must appear in its cell.

Build the ID cells automatically: `python scripts/lint_testcases.py <file.md> --write-matrix` (keeps existing N/A reasons, fills ID cells, adds `N/A – TODO` where nothing exists, adds the conditions table skeleton when missing).

Good N/A reasons are specific: "N/A – the screen has no free-text input", "N/A – the app supports portrait only". Bad: "N/A", "not needed".

## What each cell should cover

| Level | POS | NEG | EDG | BND | VAL | ERR |
|---|---|---|---|---|---|---|
| **CMP** component | A single field, button or list item works with normal input | Control rejects wrong input (letters in a number field) | Empty, very long, emoji, paste, double tap, fast repeated taps | Min/max length, min/max value, first/last item of a picker | Field messages, required markers, formats, keyboard type (number pad for a phone field) | Control shows a clear message when it cannot load its data |
| **INT** integration | Two screens/services work together (save, list updates; filter + list) | Data not shown where it should not be (other user, other role) | Stale data after returning to the screen, pull to refresh shows the new state | Long lists, paging at the end of a list | Server-side validation shown on the screen | Back-end failure surfaces as a friendly message, the screen keeps the entered data |
| **E2E** end to end | Full happy path of the flow as the plan describes it | User abandons midway, goes back, closes the app mid-flow | Signed out by the app mid-flow, deep link into a middle step | Max items, max steps | Whole-flow validation before submit | Recovery after a failed submit |
| **UI** basic UI/UX | Layout, labels and copy match the design/docs on the connected device | Disabled controls look disabled and cannot be used | Long names wrap or truncate cleanly, empty states give guidance, keyboard does not cover the active field | Small and large screen of the connected device, landscape (if supported), larger font size | Consistent message wording and placement | Loading and error states are visible and understandable, dark mode keeps text readable |
| **MOB** mobile conditions | The app behaves correctly through a condition (permission allowed, back from background) | Condition refused or lost (permission denied, connection lost during save) | Condition changes mid-action (rotate while typing, minimise during upload) | Limits of a condition (deny with "don't ask again", very slow connection) | The app explains the condition (permission rationale, offline banner) | The app recovers after the condition ends (network back, permission turned on later in settings) |

## Mobile conditions table

One row per condition group (`mobile-conditions.md`), in this order: App lifecycle, Permissions, Interruptions, Network, Orientation, Device settings, Navigation. `Covered by` lists case IDs of this flow (any level), or `N/A – <reason>` ("N/A – the flow asks for no permission", "N/A – the app supports portrait only"). `Notes` says what is special, for example "needs a person: calls cannot be triggered on a real device".

## Minimum expectations per flow

- E2E POS: at least one case (the main happy path).
- At least one NEG and one VAL case at CMP or INT for every form in the flow.
- At least one MOB case for every condition group that applies to the flow; groups that do not apply get a reason in the conditions table.
- App lifecycle (minimise and reopen) and Navigation (system back) apply to almost every flow.
