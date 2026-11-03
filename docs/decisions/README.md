# Architecture Decision Records

One decision per file, numbered. Use the `write-adr` skill. Status: Proposed, Accepted, Superseded by NNN.

| # | Title | Status |
|---|---|---|
| 001 | [Modular monolith](001-modular-monolith.md) | Accepted |
| 002 | [Backend and frontend stack](002-stack-fastapi-react.md) | Accepted |
| 003 | [Per-worker sync change log](003-sync-change-log.md) | Accepted |
| 004 | [Country rule packs and per-country deployment](004-country-rule-packs.md) | Superseded in part by 007 |
| 005 | [Immutable events and versioned calculations](005-immutable-events-versioned-calculations.md) | Accepted |
| 006 | [Map stack, tile provider and dependency policy](006-map-stack-and-dependency-policy.md) | Accepted (M3 compatibility gate) |
| 007 | [Multi-country operation in one deployment](007-multi-country-single-deployment.md) | Superseded by 009 |
| 008 | [Effective-dated configuration and time rules](008-effective-dated-configuration.md) | Accepted |
| 009 | [One stack per country, and hosting](009-country-deployments-and-hosting.md) | Accepted |
| 010 | [Foundation dependency pins and verification](010-foundation-dependency-pins.md) | Accepted |
| 011 | [Transitive scope resolution and session token rotation](011-transitive-scope-and-session-tokens.md) | Accepted |

See also [decision-register.md](decision-register.md) for business decisions awaiting client confirmation.

## Template
```
# NNN - Title
Status: Proposed | Accepted | Superseded by NNN
Date: YYYY-MM-DD
## Context
## Options considered
## Decision
## Why
## Consequences
```
