# Personal data breach response runbook (DRAFT)

Target: decide and notify within **72 hours** of becoming aware (SDAIA requires 72 hours for harmful breaches; the UAE period will be set by regulation, so use 72 hours as the internal standard in both countries).

## Roles
- **Incident owner** [NAME, backup NAME]: leads the response and records everything.
- **Technical lead** [NAME]: contains and investigates.
- **Data protection contact / DPO** [NAME]: assesses harm, decides notifications.
- **Management** [NAME]: approves external communication.
- **Counsel** [NAME].

## Steps
| Time | Action |
|---|---|
| 0 h | Whoever notices tells the incident owner. Record time of awareness. Do not delete evidence. |
| 0-4 h | Contain: revoke affected sessions/devices, rotate keys/passwords, block access paths. Preserve logs and snapshots. |
| 4-24 h | Investigate: what data, whose, how many people, which country, how it happened, still ongoing? Check the audit log for who accessed what. |
| 24-48 h | Assess harm (location trails, salary, worker IDs, document dates). Decide: notify regulator? notify workers? Brief counsel. |
| By 72 h | If required, notify: Saudi Arabia: SDAIA through the National Data Governance Platform. UAE: UAE Data Office (period per regulation, once issued; notify as soon as possible). If you cannot give everything within 72 hours, give what you have and explain the delay. |
| Without undue delay | Tell affected workers in clear language: what happened, what data, what to do, who to contact. |
| After | Root-cause review within 14 days, fix, update this runbook, record in the incident log. |

## Notification content checklist
What happened and when; categories and approximate number of people and records; likely consequences; measures taken and planned; contact person. Use the regulator's form fields where available.

## Processor incidents
If the cloud host or another provider reports an incident, the clock starts when we become aware; ask them for details immediately.

## Records
Keep an incident log (date, description, data, people affected, decisions, notifications, fixes) even when no notification was needed.
