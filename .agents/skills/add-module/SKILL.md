---
name: add-module
description: Use when creating a new backend module (a new business area such as payroll or reports). Scaffolds the folder structure, public interface, ports, migration and docs page.
---
1. Confirm the module's single responsibility and the tables it will own with the user. Check `docs/13-architecture.md` for the module list.
2. Create `backend/src/fw/modules/<name>/` with: `__init__.py` (public interface only), `api.py`, `schemas.py`, `service.py`, `repository.py`, `models.py`, `ports.py`.
3. Export only the intended public functions and types from `__init__.py`.
4. Register the router in `backend/src/fw/main.py`.
5. Add the module to the `import-linter` contract in `backend/pyproject.toml`.
6. Create the Alembic migration for its tables (use the `db-migration` skill).
7. Create `docs/modules/<name>.md`: purpose, owned tables, public interface, dependencies, and why it is a separate module.
Do not import another module's models, repository or service.
