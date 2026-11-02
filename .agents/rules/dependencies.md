# Dependencies
Before adding or upgrading any library, framework, tile provider or service:
1. Check the latest release date and recent maintenance activity (releases, commits, open maintainer concerns). Do not use libraries that have not been actively released for about 12 months. Leaflet was rejected for exactly this reason.
2. Check the licence (permissive only unless approved) and that it supports our pinned major versions (for example MapLibre, React, Python, SQLAlchemy).
3. Prefer fewer, well-maintained dependencies. Do not add a library for something small that the platform or an existing dependency already does.
4. Pin exact versions with a lock file. Record the library, version, verification date and status in `docs/17-dependencies.md`.
5. If a check fails or is uncertain, stop and ask. Anything that looks risky needs an ADR.
6. Map libraries live only in `web/src/features/map/` behind a small wrapper, so they can be replaced in one place.
Use the `add-dependency` skill.
