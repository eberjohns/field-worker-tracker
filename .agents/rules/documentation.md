# Documentation rule
After finishing any task, before presenting it:
1. Update or create the relevant file in `docs/` (structure, flow, rules, API, data model).
2. If a design choice was made or changed, add an ADR (`write-adr` skill) and link it from `docs/decisions/README.md`.
3. Add a line to `CHANGELOG.md`.
4. If an endpoint changed, make sure `docs/08-api-spec.md` (or `docs/09-mobile-sync-contract.md` for mobile endpoints) matches.
Docs explain **why**, not only what. A change without a docs update is not finished.
