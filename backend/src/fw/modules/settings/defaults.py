"""Default company settings: the values seeded by migration 0003 (effective 1 Jan 2026).

Used to re-seed settings after "Reset database" so payroll works straight away (payroll money
settings have no hard-coded fallbacks, DEC-58). Migration 0003 keeps its own frozen copy.
Tuples: (setting_key, country or None, value, unit).
"""

from datetime import date
from typing import Any

DEFAULTS_EFFECTIVE_FROM = date(2026, 1, 1)

DEFAULT_COMPANY_SETTINGS: list[tuple[str, str | None, Any, str | None]] = [
    ("currency", "AE", "AED", None),
    ("currency", "SA", "SAR", None),
    ("default_weekly_off_day", "AE", "SUNDAY", None),
    ("default_weekly_off_day", "SA", "FRIDAY", None),
    ("ot2_weekdays", "AE", ["SUNDAY"], "list"),
    ("ot2_weekdays", "SA", ["FRIDAY"], "list"),
    ("standard_ot_divisor_hours", None, 208, "h"),
    ("ot1_multiplier", None, 1.25, "x"),
    ("ot2_multiplier", None, 1.5, "x"),
    ("hr_overhead_rate", None, 0.05, "fraction"),
    ("provision_visa", None, 132, "per month"),
    ("provision_air_ticket", None, 65, "per month"),
    ("provision_uniform", None, 30, "per month"),
    ("provision_accommodation", None, 550, "per month"),
    ("provision_medical", None, 65, "per month"),
    ("gratuity_days_per_year", None, 30, "days"),
    ("leave_salary_divisor", None, 12, None),
    ("standard_hours_default", None, 8, "h"),
    ("planned_workday_hours", None, 9, "h"),
    ("grace_period_minutes", None, 10, "min"),
    ("min_visit_minutes", None, 10, "min"),
    ("gap_flag_minutes", None, 15, "min"),
    ("max_transit_minutes", None, 90, "min"),
    ("reassignment_min_notice_days", None, 3, "days"),
    ("payroll_auto_run_delay_days", None, 5, "days"),
    ("alarm_lead_minutes", None, 30, "min"),
    ("geofence_circle_radius_m", None, 300, "m"),
    ("approach_polling_interval_s", None, 60, "s"),
    ("confirmation_polling_interval_s", None, 300, "s"),
    ("schedule_sync_window_days", None, 30, "days"),
    ("document_expiry_lead_days", None, 30, "days"),
    ("live_active_window_minutes", None, 15, "min"),
    ("pending_visit_reminder_hours", None, 24, "h"),
    ("day_close_delay_minutes", None, 120, "min"),
    ("occurrence_horizon_months", None, 13, "months"),
    ("roster_materialise_weeks", None, 4, "weeks"),
    ("default_password_max_days", None, 7, "days"),
    (
        "budget_only_staff_types",
        None,
        ["Project Manager", "HSE Engineer", "QA/QC Engineer", "Irrigation Engineer"],
        "list",
    ),
    ("max_location_accuracy_m", None, 100, "m"),
    ("clock_skew_tolerance_s", None, 120, "s"),
    ("event_future_tolerance_s", None, 300, "s"),
    ("event_max_age_days", None, 7, "days"),
    ("no_activity_alert_after_minutes", None, 60, "min"),
    ("stale_device_hours", None, 24, "h"),
    ("location_policy_version", None, 1, None),
]
