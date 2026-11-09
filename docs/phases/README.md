# Development Phases

The system is built **phase by phase**. Each phase is independent, ends with something demonstrable, and has its own context pack and checklist. Start a **new agent conversation per phase** and tell it: *"Work on PHASE-NN. Read only the files listed under Context."* Always read `AGENTS.md`, `.agents/rules/` and the decision-register rows named in the phase.

## Order and status

| Phase | Title | Depends on | Status |
|---|---|---|---|
| [00](PHASE-00-foundation.md) | Foundation | - | done |
| [01](PHASE-01-access-and-people.md) | Access and people | PHASE-00 | done |
| [02](PHASE-02-settings-and-time-rules.md) | Settings, time rules and calendars | PHASE-01 | done |
| [03](PHASE-03-import-and-salary.md) | Import framework, master data import and salary structures | PHASE-02 | done |
| [04](PHASE-04-sites-boundaries-jobs.md) | Sites, boundaries and job items | PHASE-03 | done |
| [05](PHASE-05-planner.md) | Planner: yearly plan and weekly roster | PHASE-04 | done |
| [06](PHASE-06-leave-reassignment-approvals.md) | Leave, temporary reassignment and approvals | PHASE-05 | done |
| [07](PHASE-07-mobile-contract-and-sync.md) | Mobile contract, login and sync | PHASE-06 | done |
| [08](PHASE-08-events-and-attendance.md) | Events and attendance | PHASE-07 | done |
| [09](PHASE-09-live-map-pending-alerts.md) | Live map, pending visits, alerts and documents | PHASE-08 | not started |
| [10](PHASE-10-transport.md) | Drivers and transport runs | PHASE-07 (needs Phase 05 for schedules) | not started |
| [11](PHASE-11-payroll-and-budget.md) | Month-end payroll and job budget | PHASE-08 | not started |
| [12](PHASE-12-reports-and-generated-history.md) | Reports and the Generated Reports section | PHASE-11 | not started |
| [13](PHASE-13-hardening-and-go-live.md) | Hardening, archive, backup and go-live | all | not started |

## How to run a phase
1. Open a new agent conversation. Paste the **phase prompt** from `docs/KICKOFF_PROMPT.md` with the phase number.
2. The agent reads the context list, asks questions, and writes a plan. **Approve the plan before any code.**
3. The agent builds on a branch, ticks the checklist, updates docs, opens a pull request.
4. You review, run the demo script, merge, and mark the phase done above.

## Phase independence
Phases 01 to 06 build the planning half (people, settings, import, sites, planner, approvals). Phase 07 opens the mobile contract so the mobile team can start. Phases 08 to 12 build attendance, supervision, transport, payroll and reports. Phase 10 (transport) can be done any time after Phase 07. Phase 13 closes the project. If a phase proves too large for one session, split it by its Deliverables list and keep the same checklist.

## Cross-phase rules
- Never change a published mobile field without a contract version bump and owner approval (`.agents/rules/safety.md`).
- Respect module boundaries (`.agents/rules/architecture.md`).
- Anything marked PROPOSED in the decision register is built behind a setting.
