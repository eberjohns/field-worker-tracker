# Payroll Module (`fw.modules.payroll`)

## 1. Purpose
The `payroll` module handles month-end payroll processing, draft generation, issue detection (unapproved overtime, missing salary structures), draft re-runs, administrator approvals, immutable snapshot creation, employee attendance locking, salary revisions with side-by-side diff previews, worker mobile pay slips, and dynamic job budget vs actual cost allocation.

## 2. Architecture & Layering
- **Pure Rules**: `fw.rules.payroll.formulas`
  - Zero DB / zero HTTP dependencies.
  - Computes standard rates (208 divisor), OT1 rate (1.25x), OT2 rate (1.50x), missed hours deductions, statutory gratuity, leave salary provisions, employer company provisions, 5% HR overhead, and planned grade hourly costs.
- **Data Models**: `fw.modules.payroll.models`
  - `SalaryRevision` & `SalaryRevisionLine`: Commercial grade cost revisions.
  - `PayrollRun`: Month-end header (`DRAFT` / `APPROVED`, `run_no`, `calculation_version`).
  - `PayrollRecord`: Per-worker approved snapshot with full immutable audit JSON (`snapshot`).
  - `JobCostAllocation`: Prorated allocation of worker final staff cost to worksites based on worked minutes.
  - `EmployeeSalary`: Worker salary structures with effective dating.
- **Repository**: `fw.modules.payroll.repository`
  - Encapsulates database queries, optimistic locking, and attendance record locking.
- **Service**: `fw.modules.payroll.service`
  - `PayrollSalaryService`: Salary structure history and management.
  - `PayrollService`: Draft run generation, issue inspection, approval locking, diff preview, budget vs actual calculations, and auto-draft runner.
- **API**: `fw.modules.payroll.api`
  - FastAPI endpoints exposed under `/api/v1`.

## 3. Key Endpoints
| Method | Path | Roles | Description |
|---|---|---|---|
| `POST` | `/api/v1/payroll/runs` | ADMIN | Generate draft or re-run draft (increments `run_no`). |
| `GET` | `/api/v1/payroll/runs` | ADMIN, ENGINEER (scoped) | List payroll runs. |
| `GET` | `/api/v1/payroll/runs/{id}` | ADMIN, ENGINEER (scoped) | Get payroll run details and worker records. |
| `GET` | `/api/v1/payroll/runs/{id}/issues` | ADMIN, ENGINEER | List draft issues (unapproved overtime, missing salaries). |
| `POST` | `/api/v1/payroll/runs/{id}/approve` | ADMIN | Freeze records as immutable snapshots and lock attendance. |
| `GET` | `/api/v1/payroll/records` | ADMIN, ENGINEER (scoped) | Query frozen payroll records. |
| `GET` | `/api/v1/payroll/my-records` | WORKER | Worker's own approved monthly slips (employee side only). |
| `GET` | `/api/v1/mobile/me/payroll` | WORKER | Alias for mobile client contract. |
| `GET` | `/api/v1/salary-revisions` | ADMIN, ENGINEER | List salary revision headers. |
| `POST` | `/api/v1/salary-revisions` | ADMIN | Create new salary revision with grade lines. |
| `GET` | `/api/v1/salary-revisions/{code}` | ADMIN, ENGINEER | Get revision detail with planned hourly cost. |
| `POST` | `/api/v1/salary-revisions/diff` | ADMIN | Side-by-side diff comparing incoming lines to base revision. |
| `GET` | `/api/v1/payroll/budget-vs-actual` | ADMIN, ENGINEER | Contract labor budget vs actual allocated cost. |
| `PUT` | `/api/v1/payroll/worksites/{id}/revision` | ADMIN | Bind specific salary revision code to a worksite. |
| `POST` | `/api/v1/payroll/auto-run-check` | ADMIN | Background runner checking completed months past delay days. |

## 4. Business Rules & Formulas
1. **Working Hours Divisor**: 208 hours (26 days × 8 hours).
2. **OT1 Rate**: `(basic / 208) * 1.25` (hours worked beyond standard hours on normal working days).
3. **OT2 Rate**: `(basic / 208) * 1.50` (all hours worked on public holidays and worker's weekly off day).
4. **Missed Hours Deduction**: `(unpaid_leave_hours + shortfall_hours) * (basic / 208)`. Paid leaves incur zero deduction.
5. **Gratuity Provision**: `(basic / 30) * (21 / 12)`.
6. **Leave Salary Provision**: `((basic + housing_allowance) / 30) * (30 / 12)`.
7. **Company Provisions**: 5 settings (Visa, Air Ticket, Uniform, Medical, Accommodation).
8. **HR Overhead**: 5% of Subtotal Staff Cost.
9. **Final Total Staff Cost**: Subtotal Staff Cost + 5% HR OH.
10. **Budget Provision Distinction**: Job Budgets use the static commercial provisions in the salary revision file; Actual Allocated Costs use dynamic statutory provisions derived from live company settings and attendance calculations.
