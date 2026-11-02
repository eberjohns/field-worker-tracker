# 007 - Multi-country operation in one deployment
Status: Superseded by 009 (one stack per country)
Date: 2026-10-29
Supersedes the per-country-deployment part of ADR-004 (Country Rule Packs remain).

## Context
The client has jobs, staff and accommodations in both the UAE and Saudi Arabia and wants one system. ADR-004 proposed one deployment per country. The client wants both countries managed together and does not want to deal with policy questions during development.

## Options considered
1. One deployment per country (ADR-004): clean data separation, two logins, no combined view.
2. One deployment, country stored on every record, rule packs chosen per record.
3. One deployment now, designed so it can be split later.

## Decision
Options 2 and 3. Employees, worksites, accommodations, salary revisions, public holidays, country-scoped settings and work-period rules each carry a `country` (AE or SA). The Country Rule Pack is chosen per record: the site's country for scheduling and attendance (time zone, rest days, holidays), the employee's country for payroll (currency, salary scale). Payroll runs are per country. Users see both countries within their reporting scope.

## Why
One login and one dashboard for the client, and no duplicate operations. Country-keyed data and pack-per-record logic keep the option of splitting into separate deployments if a legal or hosting requirement appears.

## Consequences
A legal and hosting review of Saudi personal data (KSA PDPL and transfer rules) is required **before Saudi go-live**; it does not block development. Reports can filter by country; money is never summed across currencies. Settings need a country dimension (see ADR-008). See `docs/03-business-rules.md` section 8 and `docs/13-architecture.md` section 6.
