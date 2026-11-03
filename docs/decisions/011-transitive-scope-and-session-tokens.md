# 011 - Transitive Scope Resolution and Session Token Rotation

Status: Accepted  
Date: 2026-11-03  

## Context
In Phase 01, role-based visibility and access controls are established. Client decisions DEC-10, DEC-33, and DEC-53 define how reporting lines, accounts, and permissions work.
Two key architectural questions arose during implementation:
1. Whether reporting scope `scope(U)` should be limited to direct reports (`manager_id = U.id`) or recursively expand descendant links when an Engineer oversees Superintendents who oversee Supervisors who oversee Workers.
2. How web refresh tokens should be stored and managed to support rotation and instant session revocation (`POST /auth/logout` and device revocation).

## Options considered
- **For Scope Resolution**:
  - *Option A (Direct links only)*: Every worker must have a direct link explicitly assigned to their supervisor, superintendent(s), and engineer(s). If an engineer is linked only to a supervisor, the engineer cannot view the supervisor's workers.
  - *Option B (Transitive closure)*: Scope expands through descendant management links. If an engineer manages a supervisor who manages workers, all workers are automatically within the engineer's visibility scope. Direct links to multiple superintendents or engineers are also supported.
- **For Refresh Token Lifecycle**:
  - *Option A (Stateless JWT refresh token)*: Store tokens only in httpOnly cookies without server state. Logout requires maintaining a token blacklist.
  - *Option B (Stateful `user_sessions` with SHA-256 token hashing)*: Active sessions are recorded in a dedicated `user_sessions` table with SHA-256 hashed refresh tokens. Each refresh request rotates the token, and logout or Admin password resets instantly revoke all sessions.

## Decision
- Adopt **Option B (Transitive closure)** for scope resolution: An employee `E` is within `scope(U)` if `E.id = U.id` or there exists a directed management path from `U` to `E` in `employee_reporting_lines`.
- Adopt **Option B (`user_sessions` table with token hashing)** for refresh token lifecycle: Refresh tokens are stored hashed, rotated upon every refresh, and immediately revocable on logout or password reset.

## Why
- Transitive scope mirrors real organizational hierarchies while still honoring DEC-10 (a worker can have several superintendents and several engineers).
- Stateful hashed sessions provide strict security compliance without exposing plaintext tokens in the database, allowing reliable logout and forced credential resets.

## Consequences
- The pure domain rules engine (`fw.rules.hierarchy`) calculates transitive closure over directed reporting links and enforces cycle-free graph integrity.
- Database migration `0002_access_and_people.py` adds `user_sessions` table with cascade deletion upon user removal.

