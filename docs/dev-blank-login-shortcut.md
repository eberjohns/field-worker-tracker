# Temporary Dev-Only Blank Admin Login Shortcut

> [!WARNING]
> **DEVELOPMENT PHASE ONLY**  
> This feature is a temporary convenience shortcut designed strictly for local development and rapid manual testing. It must be reverted before final release or deployment to staging/production.

---

## 1. Purpose

During active development, testing features as an administrator requires frequent logins across browser restarts, cache clears, and test database resets. To eliminate the repetitive friction of manually entering `ADMIN001` and `Admin123!`, the web dashboard login flow allows submitting empty fields to instantly log in as the active system administrator.

---

## 2. Behavioral Effects

- **Web Dashboard (`/login`)**:
  - Leaving the **Worker / Employee ID** and **Password** inputs blank and clicking **Sign in** (or pressing Enter) immediately authenticates as the active `ADMIN` (`ADMIN001`).
  - Standard authentication remains 100% operational: typing any specific username and password (e.g., a worker, supervisor, or specific admin credentials) still verifies credentials normally.
- **Environment Isolation (`APP_ENV == "local"`)**:
  - This shortcut is strictly active only when `APP_ENV` is set to `"local"`.
  - In `"staging"` or `"production"` environments, submitting blank credentials is immediately rejected with HTTP `401 Unauthorized` (`UNAUTHENTICATED`).
- **Scope Limit**:
  - Only affects the web dashboard login endpoint (`POST /api/v1/auth/login`).
  - The mobile contract endpoint (`POST /api/v1/mobile/auth/login`) and Mobile Tester Proxy (`tools/mobile-proxy/`) are **not** affected.

---

## 3. Cons, Downsides & Considerations

Before relying on this shortcut, keep in mind:

1. **Security Risk if Misconfigured**:
   - If an environment is mistakenly deployed with `APP_ENV=local` on a network-accessible host, administrative access has zero authentication.
   - *Mitigation*: The backend explicitly checks `settings.APP_ENV == "local"`. Never run `APP_ENV=local` on shared or cloud infrastructure.
2. **Bypassing Exploratory Auth Verification**:
   - Because manual testing skips typing credentials, UI bugs in form validation, password mask toggles, or lockout warnings for the admin account won't be caught during day-to-day manual browsing.
   - *Mitigation*: Automated test suites (`backend/tests/test_auth_api.py`) explicitly test standard valid and invalid authentication paths.
3. **Audit Log Rows**:
   - Every blank login still creates an audit log entry (`LOGIN` for `ADMIN001`). This is normal for audit trail tracking.

---

## 4. Modified Files & Diffs

### A. `backend/src/fw/modules/identity/service.py`
In `AuthService.authenticate`:
```python
# DEV-ONLY SHORTCUT (Development Phase Convenience):
# In local environment only, submitting blank username & password logs in as active ADMIN.
is_dev_blank_admin = (
    settings.APP_ENV == "local"
    and not request.username.strip()
    and not request.password.strip()
)

if is_dev_blank_admin:
    # Prefer default bootstrap ADMIN001 if present, otherwise the first created active ADMIN
    query = (
        select(User)
        .where(User.role == "ADMIN", User.is_active.is_(True))
        .order_by(
            (User.username == "ADMIN001").desc(),
            User.created_at.asc(),
        )
        .limit(1)
    )
    result = await session.execute(query)
    user = result.scalars().first()
    if not user:
        raise AppError(
            code="UNAUTHENTICATED",
            message="No active ADMIN user found for dev blank login.",
            status_code=401,
        )
else:
    query = select(User).where(User.username == request.username)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.credential_hash):
        raise AppError(
            code="UNAUTHENTICATED",
            message="Invalid username or password.",
            status_code=401,
        )
```

### B. `web/src/routes/Login.tsx`
- Removed HTML5 `required` attribute from the `<input>` elements.
- Updated placeholder text.
- Added helper badge:
```tsx
<div className="p-2 rounded-lg bg-indigo-50/80 border border-indigo-200/80 text-[11px] text-indigo-900 flex items-center gap-1.5">
  <span>⚡</span>
  <span><strong>Dev Shortcut:</strong> Leave blank and click Sign in to log in as Admin.</span>
</div>
```

### C. `backend/tests/test_auth_api.py`
Added unit tests:
- `test_auth_service_blank_credentials_logs_in_admin_in_local_env`
- `test_auth_service_blank_credentials_rejected_in_production`

---

## 5. How to Revert After Development Phase

To restore production authentication behavior:

### Step 1: In `backend/src/fw/modules/identity/service.py`
Replace the `if is_dev_blank_admin:` block with standard query:
```python
query = select(User).where(User.username == request.username)
result = await session.execute(query)
user = result.scalar_one_or_none()

if not user or not verify_password(request.password, user.credential_hash):
    raise AppError(
        code="UNAUTHENTICATED",
        message="Invalid username or password.",
        status_code=401,
    )
```

### Step 2: In `web/src/routes/Login.tsx`
1. Re-add `required` attribute to both username and password `<input>` tags.
2. Revert placeholders back to `placeholder="e.g. ADMIN001 or WRK001"` and `placeholder="••••••••"`.
3. Delete the `Dev Shortcut` banner div.

### Step 3: In `backend/tests/test_auth_api.py`
Remove the two dev shortcut test functions or update them to verify that blank credentials are unconditionally rejected.
