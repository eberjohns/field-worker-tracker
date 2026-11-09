"""Events enrichment, site visits, tracking gaps, and attendance records.

Revision ID: 0010_events_and_attendance
Revises: 0009_mobile_sync
Create Date: 2026-11-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_events_and_attendance"
down_revision: str | None = "0009_mobile_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add enrichment columns to mobile_event_logs
    op.add_column(
        "mobile_event_logs", sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "mobile_event_logs", sa.Column("device_clock_skew_s", sa.Integer(), nullable=True)
    )
    op.add_column(
        "mobile_event_logs",
        sa.Column(
            "processing_status", sa.String(length=30), nullable=False, server_default="ACCEPTED"
        ),
    )
    op.add_column(
        "mobile_event_logs", sa.Column("error_reason", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "mobile_event_logs",
        sa.Column(
            "server_site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "mobile_event_logs",
        sa.Column(
            "server_accommodation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accommodations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "mobile_event_logs", sa.Column("server_verdict", sa.String(length=30), nullable=True)
    )
    op.add_column(
        "mobile_event_logs", sa.Column("distance_to_polygon_m", sa.Float(), nullable=True)
    )
    op.add_column(
        "mobile_event_logs",
        sa.Column(
            "flags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::varchar[]"),
        ),
    )
    op.create_index(
        "ix_mobile_event_logs_processing_status",
        "mobile_event_logs",
        ["processing_status"],
    )

    # 2. Append-only trigger on mobile_event_logs
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_mobile_event_logs_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF current_setting('fwt.bypass_immutability', true) = 'on' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            IF (TG_OP = 'DELETE') THEN
                RAISE EXCEPTION 'mobile_event_logs rows cannot be deleted (append-only table)';
            ELSIF (TG_OP = 'UPDATE') THEN
                IF (OLD.event_id <> NEW.event_id OR
                    OLD.employee_id <> NEW.employee_id OR
                    OLD.device_id <> NEW.device_id OR
                    OLD.event_type <> NEW.event_type OR
                    OLD.event_timestamp_utc <> NEW.event_timestamp_utc OR
                    OLD.latitude IS DISTINCT FROM NEW.latitude OR
                    OLD.longitude IS DISTINCT FROM NEW.longitude OR
                    OLD.geom IS DISTINCT FROM NEW.geom OR
                    OLD.accuracy_meters IS DISTINCT FROM NEW.accuracy_meters OR
                    OLD.is_mock_location IS DISTINCT FROM NEW.is_mock_location OR
                    OLD.sequence_number IS DISTINCT FROM NEW.sequence_number OR
                    OLD.device_clock_utc IS DISTINCT FROM NEW.device_clock_utc OR
                    OLD.server_received_at <> NEW.server_received_at) THEN
                    RAISE EXCEPTION 'Device-reported fields on mobile_event_logs are immutable';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_mobile_event_logs_append_only
        BEFORE UPDATE OR DELETE ON mobile_event_logs
        FOR EACH ROW
        EXECUTE FUNCTION trg_mobile_event_logs_immutability();
        """
    )

    # 3. employee_last_position
    op.create_table(
        "employee_last_position",
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "last_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mobile_event_logs.event_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("accuracy_meters", sa.Float(), nullable=True),
        sa.Column("event_timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_verdict", sa.String(length=30), nullable=True),
        sa.Column(
            "server_site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tracking_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. site_visits
    op.create_table(
        "site_visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("place_type", sa.String(length=20), nullable=False),
        sa.Column(
            "worksite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "accommodation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accommodations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "entry_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mobile_event_logs.event_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "exit_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mobile_event_logs.event_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_inferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_inside_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("counts_as_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "flags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::varchar[]"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_site_visits_employee_date", "site_visits", ["employee_id", "work_date"])
    op.create_index("ix_site_visits_worksite_date", "site_visits", ["worksite_id", "work_date"])

    # 5. tracking_gaps
    op.create_table(
        "tracking_gaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column(
            "disabled_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mobile_event_logs.event_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "enabled_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mobile_event_logs.event_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disabled_latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("disabled_longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("disabled_location_captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("resumed_longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("distance_between_m", sa.Float(), nullable=True),
        sa.Column(
            "start_inside_site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "end_inside_site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_inferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tracking_gaps_employee_date", "tracking_gaps", ["employee_id", "work_date"])

    # 6. attendance_records
    op.create_table(
        "attendance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("current_calculation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("business_status", sa.String(length=30), nullable=False, server_default="ABSENT"),
        sa.Column("review_status", sa.String(length=30), nullable=False, server_default="AUTO"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("employee_id", "work_date", name="uq_attendance_records_employee_date"),
    )
    op.create_index("ix_attendance_records_date", "attendance_records", ["work_date"])
    op.create_index("ix_attendance_records_review_status", "attendance_records", ["review_status"])
    op.create_index(
        "ix_attendance_records_business_status", "attendance_records", ["business_status"]
    )

    # 7. attendance_calculations
    op.create_table(
        "attendance_calculations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "attendance_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attendance_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("engine_version", sa.String(length=20), nullable=False, server_default="1.0.0"),
        sa.Column("reason", sa.String(length=50), nullable=False, server_default="NEW_EVENTS"),
        sa.Column("planned_accommodation_departure", sa.Time(), nullable=True),
        sa.Column("planned_first_site_start", sa.Time(), nullable=True),
        sa.Column("planned_break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_last_site_end", sa.Time(), nullable=True),
        sa.Column("planned_accommodation_return", sa.Time(), nullable=True),
        sa.Column("planned_total_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_worked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("standard_hours_minutes", sa.Integer(), nullable=False, server_default="480"),
        sa.Column("accommodation_departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_site_entry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("break_minutes_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("break_source", sa.String(length=50), nullable=False, server_default="RULE"),
        sa.Column("last_site_exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accommodation_return_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_site_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shift_span_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unaccounted_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("variation_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shortfall_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grace_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grace_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("satisfied", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("productive_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transit_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("offsite_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idle_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ot1_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ot2_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ot_threshold_minutes", sa.Integer(), nullable=False, server_default="480"),
        sa.Column("day_type", sa.String(length=30), nullable=False, server_default="NORMAL"),
        sa.Column("assigned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("business_status", sa.String(length=30), nullable=False, server_default="ABSENT"),
        sa.Column(
            "flags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::varchar[]"),
        ),
        sa.Column(
            "review_reasons",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::varchar[]"),
        ),
        sa.Column(
            "visits_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "gaps_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "inputs_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "source_event_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.UniqueConstraint(
            "attendance_record_id", "version_no", name="uq_attendance_calc_record_version"
        ),
    )
    op.create_index(
        "ix_attendance_calc_record", "attendance_calculations", ["attendance_record_id"]
    )
    op.create_index("ix_attendance_calc_hash", "attendance_calculations", ["input_hash"])

    # 8. Add FK constraint for current_calculation_id
    op.create_foreign_key(
        "fk_attendance_records_current_calc",
        "attendance_records",
        "attendance_calculations",
        ["current_calculation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 9. attendance_comments
    op.create_table(
        "attendance_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "attendance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attendance_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("comment_type", sa.String(length=50), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column(
            "scheduled_work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_work.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_attendance_comments_attendance_id", "attendance_comments", ["attendance_id"]
    )

    # 10. attendance_approvals
    op.create_table(
        "attendance_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "attendance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attendance_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "calculation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attendance_calculations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_attendance_approvals_attendance_id", "attendance_approvals", ["attendance_id"]
    )
    op.create_index("ix_attendance_approvals_calc_id", "attendance_approvals", ["calculation_id"])

    # 11. pending_visits
    op.create_table(
        "pending_visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scheduled_work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_work.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "occurrence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_occurrences.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "worksite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("detected_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="OPEN"),
        sa.Column(
            "explanation_comment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attendance_comments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "rescheduled_to_scheduled_work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_work.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "closed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("closed_reason", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_pending_visits_status_due", "pending_visits", ["status", "due_date"])
    op.create_index("ix_pending_visits_employee", "pending_visits", ["employee_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_visits_employee", table_name="pending_visits")
    op.drop_index("ix_pending_visits_status_due", table_name="pending_visits")
    op.drop_table("pending_visits")

    op.drop_index("ix_attendance_approvals_calc_id", table_name="attendance_approvals")
    op.drop_index("ix_attendance_approvals_attendance_id", table_name="attendance_approvals")
    op.drop_table("attendance_approvals")

    op.drop_index("ix_attendance_comments_attendance_id", table_name="attendance_comments")
    op.drop_table("attendance_comments")

    op.drop_constraint(
        "fk_attendance_records_current_calc", "attendance_records", type_="foreignkey"
    )
    op.drop_index("ix_attendance_calc_hash", table_name="attendance_calculations")
    op.drop_index("ix_attendance_calc_record", table_name="attendance_calculations")
    op.drop_table("attendance_calculations")

    op.drop_index("ix_attendance_records_business_status", table_name="attendance_records")
    op.drop_index("ix_attendance_records_review_status", table_name="attendance_records")
    op.drop_index("ix_attendance_records_date", table_name="attendance_records")
    op.drop_table("attendance_records")

    op.drop_index("ix_tracking_gaps_employee_date", table_name="tracking_gaps")
    op.drop_table("tracking_gaps")

    op.drop_index("ix_site_visits_worksite_date", table_name="site_visits")
    op.drop_index("ix_site_visits_employee_date", table_name="site_visits")
    op.drop_table("site_visits")

    op.drop_table("employee_last_position")

    op.execute("DROP TRIGGER IF EXISTS trg_mobile_event_logs_append_only ON mobile_event_logs;")
    op.execute("DROP FUNCTION IF EXISTS trg_mobile_event_logs_immutability();")

    op.drop_index("ix_mobile_event_logs_processing_status", table_name="mobile_event_logs")
    op.drop_column("mobile_event_logs", "flags")
    op.drop_column("mobile_event_logs", "distance_to_polygon_m")
    op.drop_column("mobile_event_logs", "server_verdict")
    op.drop_column("mobile_event_logs", "server_accommodation_id")
    op.drop_column("mobile_event_logs", "server_site_id")
    op.drop_column("mobile_event_logs", "error_reason")
    op.drop_column("mobile_event_logs", "processing_status")
    op.drop_column("mobile_event_logs", "device_clock_skew_s")
    op.drop_column("mobile_event_logs", "batch_id")
