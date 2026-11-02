# Field Worker Tracker - Documentation Index

Start with `phases/README.md` to build. Reference documents are numbered; design documents describe the screens and flows; phase files tell the agent what to read and build for each step.

| # | File | What it answers |
|---|------|-----------------|
| 01 | [product-overview](01-product-overview.md) | What we are building, scope, actors, glossary |
| 02 | [roles-and-permissions](02-roles-and-permissions.md) | Who can do what; accounts and passwords; reporting scope |
| 03 | [business-rules](03-business-rules.md) | Rules, conventions, settings catalog |
| 04 | [scheduling-engine](04-scheduling-engine.md) | Yearly plan, assignments, roster markers, suggestions |
| 05 | [attendance-engine](05-attendance-engine.md) | Events to visits to attendance, overtime, review |
| 06 | [payroll-and-cost](06-payroll-and-cost.md) | Salary structure, month-end draft/approve, budget |
| 07 | [data-model](07-data-model.md) | Tables, fields, constraints |
| 08 | [api-spec](08-api-spec.md) | Web API |
| 09 | [mobile-sync-contract](09-mobile-sync-contract.md) | **Shared with the mobile team** |
| 10 | [ui-views](10-ui-views.md) | Screens by role |
| 11 | [import-pipeline](11-import-pipeline.md) | Excel import: keys, preview, rules |
| 12 | [reports](12-reports.md) | 16 reports, live monitoring, alerts, generated history |
| 13 | [architecture](13-architecture.md) | Stack, modules, deployment |
| 14 | [nonfunctional](14-nonfunctional.md) | Security, retention, backup, hosting |
| 15 | [dev-process](15-dev-process.md) | Working method, git, definition of done |
| 17 | [dependencies](17-dependencies.md) | Dependency register |

## Design documents (`design/`)
[D1 planner](design/D1-planner.md) | [D2 leave and reassignment](design/D2-leave-and-reassignment.md) | [D3 time rules and attendance table](design/D3-time-rules-and-attendance-report.md) | [D4 month-end and reports](design/D4-month-end-and-reports.md) | [D5 transport](design/D5-transport-and-drivers.md) | [D6 import and setup](design/D6-import-and-setup.md)

## Other folders
- [phases/](phases/README.md): the build plan, one file per phase with context list, deliverables and checklist
- [decisions/](decisions/README.md): ADRs and the [decision register](decisions/decision-register.md)
- [legal/](legal/01-human-actions.md): compliance review, draft worker notice, data inventory/DPIA, breach runbook, human actions
- [import-templates/](import-templates/README.md): the client import workbook (v1.0)
- [reference/](reference/): client requirements, client documents, answers log, data findings
- [KICKOFF_PROMPT](KICKOFF_PROMPT.md): prompts for the agent

## Precedence when documents disagree
1. Client requirements (`reference/`) 2. Decision register and accepted ADRs 3. Numbered and design docs 4. Code comments
