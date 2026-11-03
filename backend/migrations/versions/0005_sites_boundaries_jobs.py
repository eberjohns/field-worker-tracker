"""Worksites, job items, and job occurrences (Phase 04)

Revision ID: 0005_sites_boundaries_jobs
Revises: 0004_import_and_salary
Create Date: 2026-11-03 18:30:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import uuid4

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_sites_boundaries_jobs"
down_revision: str | None = "0004_import_and_salary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. worksites
    op.create_table(
        "worksites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_number", sa.String(length=50), nullable=False),
        sa.Column("job_name", sa.String(length=255), nullable=False),
        sa.Column("renewal_reference", sa.String(length=50), nullable=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_type", sa.String(length=50), nullable=True),
        sa.Column("is_outdoor", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("contract_group_ref", sa.String(length=50), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "boundary",
            geoalchemy2.types.Geometry(
                geometry_type="POLYGON",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=True,
            ),
            nullable=True,
        ),
        sa.Column("rep_latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("rep_longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("budget_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("country IN ('AE', 'SA')", name="ck_worksites_country_valid"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_worksites_job_number", "worksites", ["job_number"], unique=True)
    op.create_index("ix_worksites_group_id", "worksites", ["group_id"])
    op.create_index("ix_worksites_zone_id", "worksites", ["zone_id"])
    op.create_index("ix_worksites_country", "worksites", ["country"])
    op.create_index("ix_worksites_is_active", "worksites", ["is_active"])

    # 2. job_items
    op.create_table(
        "job_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_item_code", sa.String(length=50), nullable=False),
        sa.Column("staff_grade_description", sa.String(length=100), nullable=False),
        sa.Column("planned_grade_code", sa.String(length=50), nullable=False),
        sa.Column("frequency_unit", sa.String(length=20), nullable=False),
        sa.Column("occurrences_per_period", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("period_interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("weekday_pattern", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("required_staff_count", sa.Integer(), nullable=False),
        sa.Column(
            "hours_per_occurrence_per_staff", sa.Numeric(precision=8, scale=3), nullable=False
        ),
        sa.Column("declared_activities_per_year", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column(
            "declared_total_hours_per_year", sa.Numeric(precision=12, scale=3), nullable=True
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("deployment_type", sa.String(length=20), nullable=False),
        sa.Column("break_override_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "frequency_unit IN ('WEEK', 'MONTH', 'QUARTER', 'YEAR')",
            name="ck_job_items_frequency_unit",
        ),
        sa.CheckConstraint(
            "deployment_type IN ('PERMANENT', 'REMOTE')",
            name="ck_job_items_deployment_type",
        ),
        sa.ForeignKeyConstraint(["worksite_id"], ["worksites.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("worksite_id", "sub_item_code", name="uq_job_items_worksite_sub_item"),
    )
    op.create_index("ix_job_items_worksite_id", "job_items", ["worksite_id"])
    op.create_index("ix_job_items_is_active", "job_items", ["is_active"])

    # 3. job_occurrences
    op.create_table(
        "job_occurrences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="GENERATED"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="GENERATED"),
        sa.Column("required_staff_count", sa.Integer(), nullable=False),
        sa.Column("required_hours_per_staff", sa.Numeric(precision=8, scale=3), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('GENERATED', 'ASSIGNED', 'COMPLETED', 'CANCELLED')",
            name="ck_job_occurrences_status",
        ),
        sa.CheckConstraint(
            "source IN ('GENERATED', 'MANUAL')",
            name="ck_job_occurrences_source",
        ),
        sa.ForeignKeyConstraint(["job_item_id"], ["job_items.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "job_item_id", "window_start", "slot_index", name="uq_job_occurrences_slot"
        ),
    )
    op.create_index("ix_job_occurrences_job_item_id", "job_occurrences", ["job_item_id"])
    op.create_index("ix_job_occurrences_due_date", "job_occurrences", ["due_date"])
    op.create_index("ix_job_occurrences_status", "job_occurrences", ["status"])

    # 4. Seed default company setting for budget_only_staff_types
    setting_table = sa.table(
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
    op.bulk_insert(
        setting_table,
        [
            {
                "id": uuid4(),
                "setting_key": "budget_only_staff_types",
                "country": None,
                "value": ["HSE Engineer", "Project Manager", "Irrigation Engineer"],
                "unit": None,
                "effective_from": date(2026, 1, 1),
                "effective_to": None,
                "created_at": datetime.now(UTC),
            }
        ],
    )


def downgrade() -> None:
    # Delete default budget_only_staff_types
    op.execute("DELETE FROM company_setting_values WHERE setting_key = 'budget_only_staff_types'")
    op.drop_table("job_occurrences")
    op.drop_table("job_items")
    op.drop_table("worksites")
