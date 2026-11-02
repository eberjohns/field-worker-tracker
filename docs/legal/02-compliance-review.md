# Compliance review: FWT (field workforce tracking and payroll)

Prepared 30 Oct 2026 from public sources. **This is a working compliance review, not legal advice.** It must be reviewed and signed off by qualified counsel in each country before go-live. Items needing a person to act are listed in `01-human-actions.md`.

## 1. Legal position in short

### UAE (mainland)
- The federal personal data law (Federal Decree-Law 45/2021, "PDPL") is **in force since 2 Jan 2022**. Its executive regulations are **still unpublished** as of October 2026, so the breach-notification period, the DPO appointment triggers, additional consent-free cases and the cross-border transfer mechanics are not yet specified. The principles apply today.
- Consent is the default basis (with listed exceptions); the controller must be able to prove it; it can be withdrawn. Before processing, the controller must tell people the purposes, who the data is shared with and the safeguards for cross-border transfers. Impact assessments, breach reporting to the UAE Data Office and encryption/pseudonymisation are required.
- **Free zones with their own data laws (DIFC, ADGM) are outside the federal PDPL.** The employing entity must be confirmed.
- Labour law (Federal Decree-Law 33/2021): worker files must be kept for at least **two years after end of service**; labour claims lapse two years after termination. Payroll/attendance practice is commonly 3 to 7 years.

### Saudi Arabia
- The PDPL has applied since 14 Sep 2023 and has been enforceable since 14 Sep 2024, with Implementing Regulations and a Transfer Regulation (v2.0, Aug 2024). SDAIA is actively enforcing.
- Consent is the default basis but contract, legal obligation and legitimate interest can apply. Requirements include a privacy notice at collection, a legal basis for every activity, records of processing, answering data-subject requests within 30 days, and **notifying SDAIA within 72 hours** of a breach that may cause harm.
- Controllers register on SDAIA's National Data Governance Platform (in practice most do; mandatory in several cases, including where data is transferred abroad). DPO rules apply by threshold.
- **Draft amendments published in October 2026 propose requiring personal data to be stored inside the Kingdom** (transfers abroad would still be allowed under the PDPL), stricter breach rules and wider registration. Not yet law; plan for it.
- Transferring Saudi personal data outside the Kingdom (including backups, dashboards or analytics hosted abroad) needs a transfer basis under the Transfer Regulation.

## 2. Requirements mapped to the system

| # | Requirement | How the design addresses it | Status | Owner |
|---|---|---|---|---|
| 1 | Notice and lawful basis before collecting location | Versioned consent notice shown on first use; tracking cannot start until accepted; consent records (policy version, device, time); re-consent when the version changes | Built into design; text drafted (03) | Counsel approves text |
| 2 | Purpose limitation, minimisation | Location only from alarm stop during working hours; no document numbers or scans; no device data beyond what attendance needs; events carry no free-form source field | In design | - |
| 3 | Storage limitation | Retention schedule (04); yearly archive; anonymisation at expiry | **Needs decision** | Business + counsel |
| 4 | Security | TLS, encryption at rest, role and scope access, device binding, audit logs, password policy, Argon2 hashing, immutable events | In design; verify in hardening phase | Dev |
| 5 | Data-subject rights (access, correction, deletion, objection) | Admin can export one employee's data and correct records; request log; 30-day clock (KSA) | **Procedure and owner needed**; export tool to build | Company + dev |
| 6 | Breach handling | Runbook drafted (05), 72-hour target in both countries | Needs named incident owner | Company |
| 7 | Impact assessment | DPIA drafted (04) | Needs sign-off | Counsel/DPO |
| 8 | Records of processing | Data inventory drafted (04) | Keep updated | Company |
| 9 | Processors and third parties | Hosting, push, email, map/tile/geocoding providers need data-processing terms; the map provider only sees the area viewed, never worker coordinates | **Contracts to verify/sign** | Company |
| 10 | Cross-border transfers and residency | UAE: in-country regions plus any off-country backup subject to legal OK. KSA: plan in-Kingdom storage | **Needs decision (see 3)** | Company + counsel |
| 11 | Registration, DPO | KSA registration and DPO threshold check at Saudi go-live; UAE DPO triggers undefined | At KSA go-live | Company |
| 12 | Employee transparency | In-app notice plus a clause in the employment contract/handbook | **Contract clause needed** | HR + counsel |
| 13 | Understandable language | Notice must be in languages the workers read | **Languages to decide** | HR |
| 14 | App-store rules | Background-location justification and privacy disclosures | Mobile team | Mobile team |

## 3. What this changes in the design
1. **Saudi data.** With the in-Kingdom storage direction, the plan is **a separate Saudi stack (database, storage and backups in the Kingdom) when Saudi goes live**, built from the same code and country-keyed data (decided in ADR-009). A combined cross-country dashboard would show only non-personal aggregates. The UAE stack stays on the UAE.
2. **Backups.** Keep each country's backups in that country (UAE: second UAE region). An off-country copy (for example outside the Gulf for physical resilience) only after counsel confirms the basis; encrypt it.
3. **Retention.** "Keep forever" for raw location history is hard to justify under storage limitation. Proposal in 04: raw location 13 months live, then encrypted archive for a fixed period, then deletion; payroll and attendance summaries longer.
4. **New features to add**: employee data export, anonymisation at retention expiry (the system never deletes referenced records, so anonymise instead), consent withdrawal handling (tracking stops, Admin notified), and audit logging of **who viewed** location data (live map, timelines).
5. **Notice and consent texts** are versioned in the system so wording changes are tracked.

## 4. Sources checked (30 Oct 2026)
UAE PDPL status and obligations: commentary from DLA Piper (Data Protection Laws of the World), Chambers 2026 (as cited by businessdubai.ae), trytrustable.com (status early Oct 2026), vigilbase.com. UAE labour record-keeping: Gulf News, ATB Legal, Zoho Payroll guide. Saudi PDPL: DLA Piper (Saudi), governancedocs.com, recordinglaw.com, waqisec.com guide (reviewed 1 Oct 2026), **Clyde & Co, "SDAIA publishes draft amendments to the Implementing Regulations of the PDPL" (Oct 2026)**. A claim that SDAIA suggests a 90-day baseline for routine monitoring data appears only in a vendor article and is **unverified**; counsel should confirm. These are secondary sources; counsel should verify against the official texts.
