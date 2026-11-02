# 004 - Country rule packs and per-country deployment
Status: Superseded in part by 007 (rule packs stay; per-country deployment replaced by one deployment, DEC-34)
Date: 2026-10-28

## Context
The system serves the UAE first and Saudi Arabia later. Weekends, public holidays, OT days, summer midday restrictions, Ramadan hours, gratuity rules, currency and time zone differ. Data-residency expectations also differ.

## Options considered
1. Hard-code UAE rules and branch later.
2. One multi-country deployment with per-record country flags everywhere.
3. A Country Rule Pack interface plus one deployment (database, storage, queue) per country.

## Decision
Option 3. Engines receive a `CountryRulePack` (Protocol) and never branch on country. `DEPLOYMENT_COUNTRY` selects the pack. Each country has its own stack and database, same code and images.

## Why
Keeps engines clean, makes adding Saudi Arabia a data/config task, and keeps each country's personal data in-country by construction.

## Consequences
No cross-country reporting in one database (aggregate outside if ever needed). Worksites still carry `country` for validation. Two deployments to operate once KSA starts. See `docs/03-business-rules.md` section 8 and DEC-12, DEC-18, DEC-26.
