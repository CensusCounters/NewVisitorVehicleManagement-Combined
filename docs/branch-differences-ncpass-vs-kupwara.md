# NCPass vs kupwara (User-Visible Differences)

This document describes how the **user experience and features** differ between the two branches:

- **NCPass**: `origin/NCPass` @ `1f840dd` (2026-01-27)
- **kupwara**: `origin/kupwara` @ `6696b09` (2026-01-27)

It focuses on what an operator/user sees in the web UI and the workflows they follow.

## Summary (at a glance)

| Area | NCPass | kupwara |
|---|---|---|
| Visitor types | Driver / Passenger | Pass holder / Permission / Civilian / Guest / Others (and related flows) |
| ID lookup | Primarily AADHAR-first | **ID Type + ID Number** (AADHAR / Driver’s License / PASS) |
| Known person page | Mostly “view → continue” | **Editable fields + Update** (including retaking ID images) |
| Unknown person page | Aadhar front/back + (driver DL-related fields) | Generic **ID front/back** capture; DL capture removed from the page |
| Trip flow | Simpler driver/passenger trip | Adds a **multi-passenger add** loop (prompting for IDs) and “Skip” option when adding passengers |
| Vehicle form fields | More vehicle fields (type/category/RC show up in UI) | Simplified vehicle fields; RC/type/category removed from UI |
| Trip close | Close trip without associating closing user | Close trip stores which user closed it (“exit gate” attribution) |
| Reports | “To Meet” field shown in tables | Renames/repurposes to **Remarks**, adds entry/exit related fields in reports |

## Functional changes by workflow

### 1) ID lookup (starting a person flow)

**What a user does**
- Select visitor type
- Enter an ID to fetch a known person, or proceed as “unknown”

**NCPass**
- The lookup is effectively **AADHAR-centric** (single ID input expectation).
- Visitor type options are centered around **DRIVER** and **PASSENGER**.

**kupwara**
- The lookup is expanded to two steps:
  1) Select **ID Type** (AADHAR / DRIVERS LICENSE / PASS)
  2) Enter the **ID Number**
- The UI validates ID numbers differently depending on the selected ID type (e.g., length rules).
- When the system is in a “add passengers” mode, the lookup page can show a **Skip** button to jump ahead in the trip flow.

### 2) Known person page (person already exists)

**NCPass**
- The screen behaves like a review step: user confirms the person details and **continues** to the next step.
- Fields are typically treated as read-only from the operator perspective.

**kupwara**
- The screen supports **editing and updating** a known person’s details directly:
  - Editable fields (name, gender, phone, address, C/O, purpose/remarks, etc.).
  - Ability to **retake the person’s primary ID images** (front/back) and save them.
  - Clear separation of actions: **Update** vs **Continue**.

### 3) Unknown person capture (person not found)

**NCPass**
- The page is oriented around **Aadhar** capture (front/back).
- Includes **driver license related** capture fields (DL number and DL image capture) for DRIVER-type flows.
- Visit purpose is presented as a dropdown list in the UI.

**kupwara**
- The page is generalized from “Aadhar” to “ID”:
  - Capture **ID Front** and **ID Back** (generic wording).
  - Driver’s license section is removed from this page.
- “Visit purpose” is treated more like a free-form text input (and aligns with reports showing “Remarks”).

### 4) Trip registration / adding passengers

**NCPass**
- The trip flow is primarily a single traveler at a time (driver/passenger).
- Permits/passenger counts are shown based on the simpler traveler-type logic.

**kupwara**
- Adds a “register more people for the same trip” feel:
  - After registering a driver, the system can prompt the operator to add **male passengers** one-by-one via repeated ID lookups.
  - The system tracks how many passengers remain to add and updates the messaging accordingly.
  - A **Skip** option appears on ID lookup while in passenger-add mode.
- Permit-image requirement rules are adjusted to match the kupwara traveler categories (civilian/guest/permission/others).

### 5) Vehicle identification & vehicle details

**NCPass**
- Vehicle screens include more structured fields (vehicle type/category and RC appear in the UI).
- Driver/passenger permissions affect which vehicle fields are required/shown.

**kupwara**
- Vehicle entry screens are simplified:
  - Removes vehicle type/category dropdowns and RC field from the UI.
  - Keeps focus on vehicle number, owner, make/model/color (and similar essentials).
  - Trip registration UI includes a link to **select another vehicle** more explicitly.

### 6) Closing a trip (end/exit)

**NCPass**
- Operator closes a trip; the system records the time.

**kupwara**
- Closing a trip captures additional “exit” attribution:
  - The close action includes the logged-in user id, enabling “who closed this trip” tracking.
  - Report tables align with this by showing additional entry/exit style columns.

### 7) Reports (vehicles/people/trips)

**NCPass**
- Reports use older terminology like “To Meet” and show certain fields that reflect the driver/passenger-centric setup.

**kupwara**
- Reports shift terminology and add fields:
  - “To Meet” is replaced/repurposed as **Remarks** in tables.
  - Trip reports include additional columns consistent with entry/exit tracking.

## Notes / non-UI impact that still affects users

- The two branches are deployed differently (Compose layout differs). This can change whether an operator’s instance “just runs” standalone vs depends on external/shared services, but it’s not a UI feature change.
- Both branches include blacklist/face-quality work in their histories; however, the most visible day-to-day operator differences between these two branches are the **ID handling**, **editing**, **trip close attribution**, and **report terminology**.

