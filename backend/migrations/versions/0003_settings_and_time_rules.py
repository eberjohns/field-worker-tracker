"""Settings, time rules, public holidays and consent policies (Phase 02)

Revision ID: 0003_settings_and_time_rules
Revises: 0002_access_and_people
Create Date: 2026-11-03 16:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_settings_and_time_rules"
down_revision: str | None = "0002_access_and_people"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. time_rules
    op.create_table(
        "time_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("applies_to", sa.String(length=20), nullable=False, server_default="ALL"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("accommodation_start", sa.Time(), nullable=True),
        sa.Column("first_site_start", sa.Time(), nullable=True),
        sa.Column("break_minutes", sa.Integer(), nullable=True),
        sa.Column("last_site_end", sa.Time(), nullable=True),
        sa.Column("accommodation_end", sa.Time(), nullable=True),
        sa.Column("standard_hours_change_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('COMPANY', 'TEAM', 'DRIVERS', 'EMPLOYEE')",
            name="ck_time_rules_scope_type",
        ),
        sa.CheckConstraint(
            "applies_to IN ('ALL', 'OUTDOOR_ONLY', 'INDOOR_ONLY')",
            name="ck_time_rules_applies_to",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scope_employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_time_rules_scope", "time_rules", ["scope_type", "scope_employee_id"])
    op.create_index("ix_time_rules_dates", "time_rules", ["start_date", "end_date"])
    op.create_index("ix_time_rules_country", "time_rules", ["country"])

    # 2. public_holidays
    op.create_table(
        "public_holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("country IN ('AE', 'SA')", name="ck_public_holidays_country"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("holiday_date", "country", name="uq_public_holidays_date_country"),
    )
    op.create_index(
        "ix_public_holidays_country_date", "public_holidays", ["country", "holiday_date"]
    )

    # 3. consent_policies
    op.create_table(
        "consent_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", "language", name="uq_consent_policies_version_lang"),
    )
    op.create_index("ix_consent_policies_version_lang", "consent_policies", ["version", "language"])

    # 4. Seed catalog settings into company_setting_values
    now = datetime.now(UTC)
    eff_date = date(2026, 1, 1)

    catalog_defaults = [
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

    settings_table = sa.table(
        "company_setting_values",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("setting_key", sa.String),
        sa.column("country", sa.String),
        sa.column("value", postgresql.JSONB),
        sa.column("unit", sa.String),
        sa.column("effective_from", sa.Date),
        sa.column("effective_to", sa.Date),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    settings_data = [
        {
            "id": uuid4(),
            "setting_key": key,
            "country": country,
            "value": val,
            "unit": unit,
            "effective_from": eff_date,
            "effective_to": None,
            "created_at": now,
        }
        for key, country, val, unit in catalog_defaults
    ]
    op.bulk_insert(settings_table, settings_data)

    # 5. Seed default company time rule
    time_rules_table = sa.table(
        "time_rules",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("country", sa.String),
        sa.column("scope_type", sa.String),
        sa.column("scope_employee_id", postgresql.UUID(as_uuid=True)),
        sa.column("applies_to", sa.String),
        sa.column("start_date", sa.Date),
        sa.column("end_date", sa.Date),
        sa.column("accommodation_start", sa.Time),
        sa.column("first_site_start", sa.Time),
        sa.column("break_minutes", sa.Integer),
        sa.column("last_site_end", sa.Time),
        sa.column("accommodation_end", sa.Time),
        sa.column("standard_hours_change_minutes", sa.Integer),
        sa.column("notes", sa.Text),
        sa.column("is_active", sa.Boolean),
        sa.column("version", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        time_rules_table,
        [
            {
                "id": uuid4(),
                "name": "Company Standard",
                "country": "AE",
                "scope_type": "COMPANY",
                "scope_employee_id": None,
                "applies_to": "ALL",
                "start_date": eff_date,
                "end_date": None,
                "accommodation_start": time(5, 0),
                "first_site_start": time(6, 0),
                "break_minutes": 30,
                "last_site_end": time(15, 30),
                "accommodation_end": time(17, 0),
                "standard_hours_change_minutes": 0,
                "notes": "Company default schedule (D3 client example: 12:00 total, 09:00 worked)",
                "is_active": True,
                "version": 1,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    # 6. Seed statutory public holidays
    holidays_table = sa.table(
        "public_holidays",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("holiday_date", sa.Date),
        sa.column("name", sa.String),
        sa.column("country", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        holidays_table,
        [
            # UAE 2026
            {
                "id": uuid4(),
                "holiday_date": date(2026, 1, 1),
                "name": "New Year's Day",
                "country": "AE",
                "created_at": now,
            },
            {
                "id": uuid4(),
                "holiday_date": date(2026, 12, 1),
                "name": "Commemoration Day",
                "country": "AE",
                "created_at": now,
            },
            {
                "id": uuid4(),
                "holiday_date": date(2026, 12, 2),
                "name": "National Day",
                "country": "AE",
                "created_at": now,
            },
            {
                "id": uuid4(),
                "holiday_date": date(2026, 12, 3),
                "name": "National Day holiday",
                "country": "AE",
                "created_at": now,
            },
            # Saudi Arabia 2026
            {
                "id": uuid4(),
                "holiday_date": date(2026, 2, 22),
                "name": "Founding Day",
                "country": "SA",
                "created_at": now,
            },
            {
                "id": uuid4(),
                "holiday_date": date(2026, 9, 23),
                "name": "National Day",
                "country": "SA",
                "created_at": now,
            },
        ],
    )

    # 7. Seed Consent Policy v1
    consent_table = sa.table(
        "consent_policies",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("version", sa.Integer),
        sa.column("language", sa.String),
        sa.column("title", sa.String),
        sa.column("body", sa.Text),
        sa.column("published_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        consent_table,
        [
            {
                "id": uuid4(),
                "version": 1,
                "language": "en",
                "title": "Location Data and Privacy Notice",
                "body": (
                    "We collect your location during working hours to coordinate field activities, "
                    "verify site attendance, and calculate payroll accurately. Location tracking is active "
                    "only during scheduled shifts."
                ),
                "published_at": now,
                "created_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("consent_policies")
    op.drop_table("public_holidays")
    op.drop_table("time_rules")
