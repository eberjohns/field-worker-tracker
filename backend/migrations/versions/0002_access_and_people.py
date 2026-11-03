"""Access and people tables (Phase 01)

Revision ID: 0002_access_and_people
Revises: 0001_initial_postgis
Create Date: 2026-11-03 08:30:00.000000

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_access_and_people"
down_revision: str | None = "0001_initial_postgis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])

    # 2. groups
    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_groups_code", "groups", ["code"])

    # 3. zones
    op.create_table(
        "zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_zones_code", "zones", ["code"])

    # 4. accommodations
    op.create_table(
        "accommodations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accommodation_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accommodation_code"),
    )
    op.create_index("ix_accommodations_code", "accommodations", ["accommodation_code"])

    # 5. employees
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tally_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("grade_code", sa.String(length=50), nullable=True),
        sa.Column("staff_grade_description", sa.String(length=100), nullable=True),
        sa.Column("accommodation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("weekly_off_day", sa.String(length=15), nullable=True),
        sa.Column("is_driver", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="AE"),
        sa.Column("break_override_minutes", sa.Integer(), nullable=True),
        sa.Column("join_date", sa.Date(), nullable=True),
        sa.Column("employment_end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('WORKER', 'SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER', 'ADMIN')",
            name="check_employees_role_valid",
        ),
        sa.CheckConstraint("country IN ('AE', 'SA')", name="check_employees_country_valid"),
        sa.CheckConstraint(
            "weekly_off_day IS NULL OR weekly_off_day IN ('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY')",
            name="check_employees_weekly_off_day_valid",
        ),
        sa.ForeignKeyConstraint(["accommodation_id"], ["accommodations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tally_id"),
    )
    op.create_index("ix_employees_country", "employees", ["country"])
    op.create_index("ix_employees_grade_code", "employees", ["grade_code"])
    op.create_index("ix_employees_is_active", "employees", ["is_active"])
    op.create_index(
        "ix_employees_staff_grade_description", "employees", ["staff_grade_description"]
    )
    op.create_index("ix_employees_tally_id", "employees", ["tally_id"])

    # 6. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("credential_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('WORKER', 'SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER', 'ADMIN')",
            name="check_users_role_valid",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_employee_id", "users", ["employee_id"])
    op.create_index("ix_users_username", "users", ["username"])

    # 7. user_sessions
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    # 8. employee_reporting_lines
    op.create_table(
        "employee_reporting_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("employee_id <> manager_id", name="check_reporting_no_self_link"),
        sa.CheckConstraint(
            "relationship IN ('SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER')",
            name="check_reporting_relationship_valid",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["manager_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id", "manager_id", "relationship", name="uq_employee_manager_relationship"
        ),
    )
    op.create_index(
        "ix_unique_single_supervisor",
        "employee_reporting_lines",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("relationship = 'SUPERVISOR'"),
    )
    op.create_index(
        "ix_reporting_lines_manager_rel", "employee_reporting_lines", ["manager_id", "relationship"]
    )
    op.create_index("ix_reporting_lines_employee", "employee_reporting_lines", ["employee_id"])

    # 9. employee_grade_history
    op.create_table(
        "employee_grade_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("old_grade_code", sa.String(length=50), nullable=True),
        sa.Column("new_grade_code", sa.String(length=50), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employee_grade_history_employee_id", "employee_grade_history", ["employee_id"]
    )

    # 10. employee_documents
    op.create_table(
        "employee_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "document_type IN ('VISA', 'PASSPORT', 'EMIRATES_ID', 'LABOUR_CARD', 'DRIVING_LICENCE', 'IQAMA')",
            name="check_document_type_valid",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "document_type", name="uq_employee_document_type"),
    )
    op.create_index("ix_employee_documents_employee_id", "employee_documents", ["employee_id"])
    op.create_index("ix_employee_documents_expiry_date", "employee_documents", ["expiry_date"])

    # 11. registered_devices
    op.create_table(
        "registered_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_identifier", sa.String(length=100), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("device_model", sa.String(length=100), nullable=True),
        sa.Column("app_version", sa.String(length=50), nullable=True),
        sa.Column("os_version", sa.String(length=50), nullable=True),
        sa.Column("push_token", sa.String(length=255), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_acked_cursor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("location_permission_state", sa.String(length=50), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "platform IN ('ANDROID', 'IOS')", name="check_device_platform_valid"
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registered_devices_employee_id", "registered_devices", ["employee_id"])
    op.create_index(
        "ix_unique_active_device_per_employee",
        "registered_devices",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # 12. company_setting_values
    op.create_table(
        "company_setting_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "setting_key", "country", "effective_from", name="uq_setting_key_country_effective_from"
        ),
    )
    op.create_index(
        "ix_company_settings_key_date", "company_setting_values", ["setting_key", "effective_from"]
    )


def downgrade() -> None:
    op.drop_table("company_setting_values")
    op.drop_table("registered_devices")
    op.drop_table("employee_documents")
    op.drop_table("employee_grade_history")
    op.drop_table("employee_reporting_lines")
    op.drop_table("user_sessions")
    op.drop_table("users")
    op.drop_table("employees")
    op.drop_table("accommodations")
    op.drop_table("zones")
    op.drop_table("groups")
    op.drop_table("audit_logs")

