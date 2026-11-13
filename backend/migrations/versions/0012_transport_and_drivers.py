"""Transport vehicles, runs, stops, and passengers.

Revision ID: 0012_transport_and_drivers
Revises: 0011_live_map_and_alerts
Create Date: 2026-11-12 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_transport_and_drivers"
down_revision: str | None = "0011_live_map_and_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create vehicles table
    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="VAN"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
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
    op.create_index("ix_vehicles_is_active", "vehicles", ["is_active"])

    # 2. Create transport_runs table
    op.create_table(
        "transport_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column(
            "driver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "vehicle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("needs_update", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
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
        "ix_transport_runs_date_dir",
        "transport_runs",
        ["run_date", "direction"],
    )
    op.create_index(
        "ix_transport_runs_driver",
        "transport_runs",
        ["driver_id"],
    )
    op.create_index(
        "uq_transport_runs_active_driver_date_dir",
        "transport_runs",
        ["run_date", "direction", "driver_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # 3. Create transport_run_stops table
    op.create_table(
        "transport_run_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transport_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stop_type", sa.String(length=20), nullable=False, server_default="SITE"),
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
        sa.Column("planned_time", sa.Time(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_transport_run_stops_run_seq",
        "transport_run_stops",
        ["run_id", "sequence"],
    )

    # 4. Create transport_run_passengers table
    op.create_table(
        "transport_run_passengers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transport_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stop_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transport_run_stops.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_transport_run_passengers_run_emp",
        "transport_run_passengers",
        ["run_id", "employee_id"],
    )
    op.create_index(
        "ix_transport_run_passengers_stop",
        "transport_run_passengers",
        ["stop_id"],
    )
    op.create_unique_constraint(
        "uq_transport_run_passengers_run_emp",
        "transport_run_passengers",
        ["run_id", "employee_id"],
    )


def downgrade() -> None:
    op.drop_table("transport_run_passengers")
    op.drop_table("transport_run_stops")
    op.drop_table("transport_runs")
    op.drop_table("vehicles")

