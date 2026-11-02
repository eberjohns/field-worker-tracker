# D6 - Import experience, boundary setup queue, accounts

Users: Admin (import, accounts), Admin and Engineer (boundaries). Rules: `11-import-pipeline.md`.

## Import screens
1. **Upload**: choose the template workbook (download link on the page). The page states the cell rules: **blank keeps the existing value; `_` clears it; nothing is ever deleted**.
2. **Preview** (nothing is written yet):
```
Import preview  FieldWorkerTracker_Import.xlsx   Employees: 12 new | 30 updated | 118 unchanged | 2 errors
Filter [All|New|Updated|Unchanged|Errors|Warnings]   Sheet [Employees]
Row  Key   Status    Changes
 7   1193  UPDATED   weekly_off_day: (blank) -> FRIDAY ; accommodation_code: ACC-01 -> ACC-02
 9   1411  NEW       Gardener Helper, G1C, AE
15   1202  ERROR     KEY_CLASH: appears twice with different grade
```
Every row shows its classification and, for updates, **old value -> new value per field**. Warnings (unknown staff type, salary missing) are listed. Download the preview as Excel.
3. **Confirm**: Admin presses Commit; one transaction; a result page lists created/updated counts and links to the records. Cannot commit while errors exist.
4. **History**: past batches, who, when, counts, original file; rollback offered only while nothing created by the batch is used.

## Inspecting and editing imported data
Each imported entity has its own section (Employees, Worksites, Job items, Salary structures, Time rules...). Admin can edit fields on screen (audited); Engineers edit within their rights. **Records are never deleted if used; they are deactivated** (greyed, kept in history, hidden from pickers). Worker ID and job number can be corrected on screen (history follows the internal ID).

## Boundary setup queue
After import, every worksite and accommodation shows "**boundary not set**".
```
Boundaries to draw: 312 worksites, 14 accommodations   Done 41 / 326   [Next unset]
Job        Name                         Zone        Status
82A11204   Dubai Marina Landscape       Marina      NOT SET   [Draw]   [Copy boundary from...]
82B11204   Dubai Marina Indoor          Marina      NOT SET   [Draw]   [Use same as 82A11204]
```
Draw: search a place (by name) to focus the map, switch to satellite, draw the polygon, see area and a validity check, save, and go to the next. **A boundary can be copied to other jobs** at the same property (A and B jobs often share one). Until drawn, a site shows a warning in the planner and phones skip geofencing for it.

## Accounts
Created from the employees import: username = worker ID, company default password, forced change at first login. Admin screen: users list, **reset to default** (Admin only), lock status, device binding (model, OS, app version, last seen), reset binding.

## Acceptance
A file with new, changed, unchanged, duplicate and invalid rows previews correctly with field-level diffs; `_` clears an optional field and is refused on a required one; commit is atomic; boundary queue progresses and copy works; password reset and binding reset work and are audited.
