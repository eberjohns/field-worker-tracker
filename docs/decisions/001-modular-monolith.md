# 001 - Modular monolith
Status: Accepted
Date: 2026-10-28

## Context
The domain is tightly coupled (schedule -> events -> attendance -> payroll). The team is small. We must still be able to swap providers and change parts later without breaking the whole system.

## Options considered
1. Microservices per area.
2. Single unstructured application.
3. One deployable application with enforced internal module boundaries.

## Decision
Option 3: a modular monolith. Modules expose a public interface; layering is enforced by `import-linter`; lower modules communicate upward through domain events; external providers sit behind ports and adapters.

## Why
Microservices add operational cost (networking, distributed transactions, deployment) with no benefit at this size. Option 2 would erode quickly. Enforced boundaries keep the option to extract a module later (for example event ingestion) if load demands it.

## Consequences
We must keep boundaries honest (CI contract, review checklist). Cross-module reads go through public interfaces. The sync module reacts to domain events rather than being called by lower modules. See `docs/13-architecture.md`.
