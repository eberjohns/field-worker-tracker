# Time and money
- Store every timestamp as UTC `timestamptz`. Name columns `*_at` (instants) or `*_date` (calendar dates).
- The **work date** of an event or shift is its local date in the **site's country time zone** (`Asia/Dubai` for AE, `Asia/Riyadh` for SA). Never use the server's clock or time zone for this.
- Durations are whole **minutes** (integers). Signed variation = actual - planned (negative = shortfall).
- Money uses `Decimal` / `numeric(14,2)`. Never `float`. Round half-up to 2 decimals at the line level and record the rounding rule in the calculation version.
- OT rates, divisors, provisions, grace, breaks and thresholds come from company settings or the Country Rule Pack. Never constants in code.
- Finalized attendance and payroll store a snapshot of every input value they used.
