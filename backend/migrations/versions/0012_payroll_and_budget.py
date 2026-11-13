"""Month-end payroll runs, immutable records, salary revisions, and job budget costing.

Revision ID: 0012_payroll_and_budget
Revises: 0011_live_map_and_alerts
Create Date: 2026-11-13 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_payroll_and_budget"
down_revision: str | None = "0011_live_map_and_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. salary_revisions
    op.create_table(
        "salary_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(10), nullable=False, server_default="AE"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_salary_revisions_code", "salary_revisions", ["code"])

    # 2. salary_revision_lines
    op.create_table(
        "salary_revision_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "revision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("salary_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("grade_code", sa.String(50), nullable=False),
        sa.Column("grade_group_title", sa.String(100), nullable=True),
        sa.Column("basic_salary", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("special_allowance", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("fixed_ot_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("bonus", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("visa_provision", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("air_ticket_provision", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("uniform_provision", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("medical_provision", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("accommodation_provision", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("transportation_provision", sa.Numeric(14, 2), nullable=True, server_default="0.00"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("revision_id", "grade_code", name="uq_salary_revision_lines_rev_grade"),
    )
    op.create_index("ix_salary_revision_lines_revision", "salary_revision_lines", ["revision_id"])
    op.create_index("ix_salary_revision_lines_grade", "salary_revision_lines", ["grade_code"])

    # 3. payroll_runs
    op.create_table(
        "payroll_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("country", sa.String(10), nullable=False, server_default="AE"),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("run_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(50), nullable=False, server_default="SYSTEM"),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculation_version", sa.String(50), nullable=False, server_default="1.0"),
        sa.Column("totals_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_payroll_runs_lookup",
        "payroll_runs",
        ["period_start", "period_end", "country", "status"],
    )

    # 4. payroll_records
    op.create_table(
        "payroll_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "payroll_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "salary_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employee_salary.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("standard_hours", sa.Numeric(4, 1), nullable=False, server_default="8.0"),
        sa.Column("scheduled_hours", sa.Numeric(6, 1), nullable=False, server_default="0.0"),
        sa.Column("worked_hours", sa.Numeric(6, 1), nullable=False, server_default="0.0"),
        sa.Column("paid_leave_hours", sa.Numeric(6, 1), nullable=False, server_default="0.0"),
        sa.Column("unpaid_leave_hours", sa.Numeric(6, 1), nullable=False, server_default="0.0"),
        sa.Column("shortfall_hours", sa.Numeric(6, 1), nullable=False, server_default="0.0"),
        sa.Column("missed_hours_deduction", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("ot1_hours", sa.Numeric(6, 2), nullable=False, server_default="0.00"),
        sa.Column("ot2_hours", sa.Numeric(6, 2), nullable=False, server_default="0.00"),
        sa.Column("salary_portion", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("ot1_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("ot2_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("gross_pay", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("net_pay", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("gratuity", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("leave_salary", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("provisions", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("per_month_provision", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("total_staff_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("hr_oh_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("final_total_staff_cost", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_records_run_employee"),
    )
    op.create_index("ix_payroll_records_run", "payroll_records", ["payroll_run_id"])
    op.create_index("ix_payroll_records_employee", "payroll_records", ["employee_id"])

    # 5. job_cost_allocations
    op.create_table(
        "job_cost_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "payroll_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "worksite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allocated_amount", sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_job_cost_allocations_record", "job_cost_allocations", ["payroll_record_id"])
    op.create_index("ix_job_cost_allocations_worksite", "job_cost_allocations", ["worksite_id"])

    # 6. Add salary_revision_code to worksites
    op.add_column("worksites", sa.Column("salary_revision_code", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("worksites", "salary_revision_code")
    op.drop_table("job_cost_allocations")
    op.drop_table("payroll_records")
    op.drop_table("payroll_runs")
    op.drop_table("salary_revision_lines")
    op.drop_table("salary_revisions")
