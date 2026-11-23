"""Which import data is Admin-only (DEC-47: only Admins see salary and cost). Pure rules."""

# Whole sheets that carry salary amounts.
ADMIN_ONLY_SHEETS: frozenset[str] = frozenset(
    {"Employee_Salary", "Salary_Revisions", "Salary_Revision_Lines"}
)

# Company_Settings keys that are money, rates or budget inputs.
ADMIN_ONLY_SETTING_KEYS: frozenset[str] = frozenset(
    {
        "standard_ot_divisor_hours",
        "ot1_multiplier",
        "ot2_multiplier",
        "hr_overhead_rate",
        "gratuity_days_per_year",
        "leave_salary_divisor",
        "budget_only_staff_types",
        "default_salary_revision_code",
    }
)

SHEET_ADMIN_ONLY = "SHEET_ADMIN_ONLY"
SETTING_ADMIN_ONLY = "SETTING_ADMIN_ONLY"


def is_admin_only_setting(key: object) -> bool:
    """True for provision_* keys and the money/rate keys above."""
    k = str(key or "").strip().lower()
    return k.startswith("provision_") or k in ADMIN_ONLY_SETTING_KEYS


def is_admin_only_row(sheet: str, setting_key: object = None) -> bool:
    """True when a row of ``sheet`` must not be seen or written by non-Admins."""
    if sheet in ADMIN_ONLY_SHEETS:
        return True
    return sheet == "Company_Settings" and is_admin_only_setting(setting_key)
