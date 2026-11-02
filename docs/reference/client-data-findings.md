# Findings from the client's reference workbooks

Source files (kept outside the repo): Staff Hierarchy R3, Site Grouping, Model for Scheduling (sheets 2021-2026), Staff Grade Review 2026 R2.

## Staff hierarchy
- 180 rows, 162 unique Tally IDs. Several people appear on more than one sheet.
- The hierarchy is **implied by merged cells**: the Supervisor column is a merged block per team; the Superintendent column is merged across a whole sheet.
- Supervisor/Superintendent cells are strings like `Name - IP (G4A26) 1198 D/L`; the Tally ID is the last 4-digit number. Names carry `- IP`/`- TS` suffixes (meaning unknown) and `D/L` (driving licence).
- 18 people appear under two different superintendents across sheets; 36 are listed under two engineers (`Renin/ Mohammed`). **Engineers have no Tally IDs** (names only: Renin, Mohammed, Sijo).
- Only 5 Staff Grade Descriptions exist in the hierarchy (Gardner Helper, Gardner Expert, Team Leader, Supervisor, Superintent) while jobs require Irrigation Technician, Palm Tree Technician, Foreman With/Without DL, Admin, Engineers etc.
- Spelling variants: Gardner/Gardener, Technitian, Forman, Superintent.

## Site grouping
Clean: 34 jobs, 5 groups (e.g. 106 Al Futtaim Real Estate - AFRE, 102 Dr. Moopens, 107 Unilever, 104 Dubai Developments, 999 Miscellaneous), 4 zones, customer type Direct (29) / Indirect (5).

## Job model (2026 sheet)
- 30 parent job blocks, up to 15 item slots each, 225 active items (many placeholders with 0 activities).
- 8 job cells are not a single job number (combined `A & B`, ranges, suffix ` - 4`).
- Job items include Admin, Project Manager, HSE Engineer, Commercial QS and Engineers (hours such as 8/month): **overhead allocations**.
- Frequencies: Daily (6/week = 312/yr), one per week, one per 2 weeks, monthly, two per month, quarterly, N per year. Free text with typos.
- Monthly/quarterly items carry large per-occurrence hours (e.g. 42.69, 115.38): "days per frequency" = hours / 9.
- Break time 00:30 on all items. Tally numbers in trailing columns list standing staff (sometimes more than the required headcount).
- 9 of 225 items disagree with their own frequency columns (e.g. `Daily` 6 x 52 listed as 104; `Three Time / Year` listed as 9; a 62 where 52 was meant). Annual hours otherwise equal activities x staff x hours.
- Older yearly sheets repeat the layout; some start/end dates hold unrelated numbers.

## Salary review (R2)
- Three sheets with different values; only `Revised 2rd July 26` has Grade Codes (26 codes: G1-G7 x A/B/C plus G11A, G14A, G16A, G20A, G25A).
- Provisions: accommodation 850, air ticket 75, uniform 30, medical 65, visa 200, transportation 500.
- `OH` column = total provisions (leave salary + gratuity + accommodation + uniform + medical + air ticket + visa + transportation). Total Cost = CTC + OH. The separate 5% HR overhead is not in the sheet.
- FOT is formula-driven: 1 fixed OT hour/day for 8-hour grades, 4 for 12-hour grades (G4, G6), none for G7 and office grades. Group titles state duty hours and "(No OT)".
- Unlabelled columns T, U, V (a sum with double counting, a hard-coded figure, a difference) - meaning unknown; ignore.
- Verified example (G1C26): provisions 1,806.07; total cost 2,906.32.

## Not in the files
Weekly off days, accommodations and who lives where, document validity dates, join dates, public holidays, drivers (only `D/L`), any job boundaries, KSA data.
