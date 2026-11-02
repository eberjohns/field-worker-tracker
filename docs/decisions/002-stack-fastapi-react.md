# 002 - Backend and frontend stack
Status: Accepted
Date: 2026-10-28

## Context
We need typed APIs with an auto-generated contract for a separate mobile team, strong spatial support, Excel handling, and a map-heavy dashboard.

## Options considered
Backend: NestJS (TypeScript) vs FastAPI (Python) vs Django REST. Queue: Celery+Redis vs Procrastinate (PostgreSQL). Frontend: React vs others.

## Decision
FastAPI + Pydantic v2 + SQLAlchemy 2 (async) + Alembic + PostGIS (GeoAlchemy2, Shapely); Procrastinate for background jobs behind a `JobQueue` port; React + TypeScript + Vite with a client generated from OpenAPI; MapLibre GL for maps.

## Why
FastAPI generates the OpenAPI schema from code, so the mobile contract cannot drift and field additions/removals show up as a diff. Python suits Excel import/export, geometry and decimal-safe payroll. A PostgreSQL-backed queue avoids running Redis initially. FastAPI has no enforced structure, so we add it with the module layout, rules and `import-linter`.

## Consequences
Discipline is required to keep boundaries (see 001). Queue can be swapped via the port if volume demands. Pin dependency versions in lock files. See `docs/13-architecture.md`.
