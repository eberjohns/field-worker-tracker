# 009 - One stack per country, and hosting
Status: Accepted (supersedes ADR-007)
Date: 2026-10-30

## Context
Saudi Arabia's data regulator published draft amendments in October 2026 proposing in-Kingdom storage of personal data, and transfers abroad need a legal basis. In March 2026 the AWS UAE region was physically damaged and some data held in one zone was permanently lost, showing that multiple zones in one region are not enough.

## Decision
- **One stack per country** from the same code and images: the UAE stack now, a **separate Saudi stack inside the Kingdom** when Saudi goes live. All records stay country-keyed; rule packs per country remain (ADR-004).
- UAE hosting: **Azure UAE North** with managed PostgreSQL/PostGIS, zone-redundant HA and geo-redundant backup to UAE Central; quarterly restore drills. An extra encrypted off-region copy only if counsel agrees.
- Management comparisons across countries use non-personal totals.

## Consequences
Two stacks to operate once Saudi starts. Backups stay in-country. Saudi hosting provider is chosen when it launches (availability and legal position re-checked). See `13-architecture.md` section 9, `14-nonfunctional.md` section 11 and `legal/`.
