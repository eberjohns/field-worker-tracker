# 06 - Salary, Month-end Payroll and Cost

Pure formulas: `backend/src/fw/rules/payroll/`; runs and history: `modules/payroll`. Month-end UX: `design/D4-month-end-and-reports.md`.

## 1. Where the numbers come from
| Purpose | Source |
|---|---|
| **Actual pay** (what the worker earns) | The worker's own **salary structure** (`employee_salary`, imported from the client's salary structure file), keyed by worker ID, effective-dated |
| **Provisions** (actual) | **Company settings**: visa, air ticket, uniform, accommodation, medical - one value for everyone |
| **Gratuity and leave salary** | Calculated by formula for everyone (exceptions in the client's file are ignored) |
| **HR overhead** | Company setting (5%) |
| **Job budget** (planning only) | **Salary revision file** (cost per grade, with its own provisions, as in the grade review file) |

## 2. Salary structure
`employee_salary`: worker, `effective_from`, `standard_hours`, `basic_salary`, `special_allowance`, `fixed_ot_amount`, `bonus`, `telephone_allowance`, `housing_transport_allowance`. A new row = a salary change; changes apply **from the next payroll month**. The system shows the last change date and the difference (new - previous fixed salary). Grade code is **not** used for pay.
```
salary_portion = basic + special_allowance + fixed_ot + bonus + telephone_allowance + housing_transport_allowance
```

## 3. Monthly formulas (per worker, per month)
```
gratuity        = basic / 365 * 30
leave_salary    = basic / 12
provisions      = visa + air_ticket + uniform + accommodation + medical        # company settings
per_month_provision = provisions + gratuity + leave_salary
hourly_rate_ot1 = basic / 208 * 1.25          # divisor and multipliers are settings
hourly_rate_ot2 = basic / 208 * 1.50
ot1_amount = ot1_hours * hourly_rate_ot1 ; ot2_amount = ot2_hours * hourly_rate_ot2
gross_pay  = salary_portion + ot1_amount + ot2_amount          # net pay = gross pay (no deductions)
total_staff_cost       = gross_pay + per_month_provision
hr_oh                  = total_staff_cost * 5%
final_total_staff_cost = total_staff_cost + hr_oh              # the "real total staff cost" shown in the reports
```
Example: basic 1100 -> OT1 rate (1100/208)*1.25 = 6.61, OT2 7.93.
**Overtime hours** come from attendance (see 05): OT1 = hours beyond the worker's standard hours on normal assigned days, and **all** hours on weekly-off days or days with no assignment; OT2 = **all** hours on public holidays and on the OT2 weekdays (default Sunday, a setting). Only reviewed/approved overtime is paid. Rounding: money half-up to 2 dp per line.

Provisions use **company settings**; the grade-review provisions are used only in the **budget**. The reports state which basis each column uses.

## 4. Month-end flow
1. **Automatic draft**: `payroll_auto_run_delay_days` (default 5) after month-end, the system creates a **DRAFT payroll run** for the previous calendar month and generates the month-end reports.
2. **Review**: Admin (and Engineers in scope, read-only) inspect the draft; issues list: attendance still pending review (OT not yet approved), workers without a salary structure, missing standard hours (default 8), workers with events but no assignment.
3. **Re-run**: Admin can re-run the draft any number of times before approval; each re-run picks up everything uploaded so far and replaces the draft (earlier drafts kept in history).
4. **Approve** (Admin, in the dashboard): freezes the run, records approver and time, writes immutable per-worker snapshots, locks the month's attendance versions, and stores the final reports.
5. **After approval**: events that arrive later are stored and visible but **ignored for that month's payroll** (workers are told to connect to the internet). No automatic adjustment.
6. **Abnormal cases** (mid-month joiners/leavers, special payments) are handled **outside the system**; the draft cannot be edited by hand.
Workers see their own payroll (salary components, OT hours and amounts, gross/net) for approved months - never provisions, overhead or cost.

## 5. Snapshots
Each approved `payroll_record` stores everything used: salary version, standard hours, settings values (OT divisor and multipliers, provisions, gratuity/leave formulas, HR OH rate), daily attendance calculation IDs with OT minutes, computed amounts, rounding rule, run number, approver. Changing settings or salaries later never alters an approved record.

## 6. Job budget and costing
**Budget** (per contract, for display): from the **salary revision file** and the job items:
```
planned_hourly_cost(grade) = (revision line: salary portion + the line's own provisions) * (1 + HR OH) / 208
item_cost_per_year = expected_annual_hours(item) * planned_hourly_cost(item.planned_grade)
contract_budget    = sum(item_cost_per_year) * contract_years         # manual override on the worksite wins
```
Revision lookup: for the worksite's country, the latest ACTIVE revision effective at the report date that contains the grade (a revision may list only changed grades); the year suffix of grade codes is ignored. Budget-only staff types are included in the budget. The report states that budget provisions come from the revision file while actual provisions come from company settings.
**Actual**: each worker's monthly `final_total_staff_cost` is allocated to worksites in proportion to worked minutes at each. Compare cumulative actual since contract start with the budget pro-rated by elapsed days; variance = actual - budget.

## 7. Report columns required by the client (payroll cost report)
Salary portion, gratuity, leave salary, each provision, per-month provision, total staff cost, HR OH 5%, **final total staff cost**; worker rows with last salary change date and difference.
