---
name: add-endpoint
description: Use when adding or changing an HTTP endpoint. Defines schemas, a thin route, a service function, permission and scope checks, audit, and updates the API docs.
---
1. Look up the endpoint in `docs/08-api-spec.md` (web) or `docs/09-mobile-sync-contract.md` (mobile). If it is missing, propose the addition to the user first.
2. Add Pydantic request/response schemas in the module's `schemas.py`.
3. Add the route in `api.py`: validate, call one service function, return a schema. Declare the role requirement with the shared permission dependency, and apply reporting-scope filtering in the service/repository.
4. Implement the service function. Business rules go to `backend/src/fw/rules/`, not here.
5. State-changing calls write an audit entry. Editable resources check `version` (optimistic locking) and return `409` on conflict.
6. Tag the route `mobile` or `web` so the mobile OpenAPI file can be filtered.
7. Update the API doc and `CHANGELOG.md`. If it is a mobile endpoint, flag it as a contract change and ask the user before merging.
