# Architecture rules
- Modular monolith. Each folder in `backend/src/fw/modules/` is a module with a public interface exported from its `__init__.py`.
- A module may import another module's `__init__` only. Never its models, repository or service.
- `backend/src/fw/rules/` holds pure business logic. It must not import FastAPI, SQLAlchemy or anything from `modules/` or `adapters/`.
- Outside services (push, email, storage, maps) are used only through a Protocol in the module's `ports.py`, implemented in `backend/src/fw/adapters/`. Choose the implementation by configuration.
- Routes are thin: validate input, call a service function, return a schema. No SQL and no business rules in routes.
- Country-specific behaviour (weekend, holidays, OT days, gratuity, restrictions) comes from the Country Rule Pack in `rules/country/`, never from `if country == ...` scattered in code.
- Enforce boundaries with `import-linter` (contract in `backend/pyproject.toml`).
