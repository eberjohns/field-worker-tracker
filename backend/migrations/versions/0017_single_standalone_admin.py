"""Enforce single standalone system ADMIN decoupled from employees table.

Revision ID: 0017_single_standalone_admin
Revises: 0016_leave_cover_and_batches
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_single_standalone_admin"
down_revision: str | Sequence[str] | None = "0016_leave_cover_and_batches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Allow NULL employee_id on users (reserved strictly for the standalone ADMIN account)
    op.alter_column(
        "users",
        "employee_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # 2. Keep at most one surviving ADMIN user (preferring username = 'ADMIN001'),
    #    repoint any nullable FK references from duplicate test/stray ADMIN users,
    #    and unlink employee_id from the surviving ADMIN user.
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                primary_admin_id UUID;
                dup_admin_ids UUID[];
                admin_emp_ids UUID[];
            BEGIN
                SELECT id INTO primary_admin_id
                FROM users
                WHERE role = 'ADMIN'
                ORDER BY (username = 'ADMIN001') DESC, created_at ASC
                LIMIT 1;

                IF primary_admin_id IS NOT NULL THEN
                    SELECT COALESCE(array_agg(id), ARRAY[]::UUID[])
                    INTO dup_admin_ids
                    FROM users
                    WHERE role = 'ADMIN' AND id <> primary_admin_id;

                    IF array_length(dup_admin_ids, 1) IS NOT NULL THEN
                        DELETE FROM user_sessions WHERE user_id = ANY(dup_admin_ids);
                        UPDATE base_roster_templates SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE standing_assignments SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE scheduled_work SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE leave_requests SET recorded_by_user_id = primary_admin_id WHERE recorded_by_user_id = ANY(dup_admin_ids);
                        UPDATE leave_requests SET approved_by_user_id = primary_admin_id WHERE approved_by_user_id = ANY(dup_admin_ids);
                        UPDATE reassignment_requests SET requested_by_user_id = primary_admin_id WHERE requested_by_user_id = ANY(dup_admin_ids);
                        UPDATE reassignment_requests SET decided_by_user_id = primary_admin_id WHERE decided_by_user_id = ANY(dup_admin_ids);
                        UPDATE public_holidays SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE time_rules SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE company_setting_values SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE consent_policies SET published_by_user_id = primary_admin_id WHERE published_by_user_id = ANY(dup_admin_ids);
                        UPDATE import_batches SET uploaded_by_user_id = primary_admin_id WHERE uploaded_by_user_id = ANY(dup_admin_ids);
                        UPDATE employee_salary SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE payroll_runs SET created_by_user_id = primary_admin_id WHERE created_by_user_id = ANY(dup_admin_ids);
                        UPDATE payroll_runs SET approved_by_user_id = primary_admin_id WHERE approved_by_user_id = ANY(dup_admin_ids);
                        UPDATE report_exports SET requested_by_user_id = primary_admin_id WHERE requested_by_user_id = ANY(dup_admin_ids);
                        UPDATE alerts SET target_user_id = primary_admin_id WHERE target_user_id = ANY(dup_admin_ids);
                        UPDATE alerts SET resolved_by_user_id = primary_admin_id WHERE resolved_by_user_id = ANY(dup_admin_ids);
                        UPDATE live_location_access_logs SET user_id = primary_admin_id WHERE user_id = ANY(dup_admin_ids);
                        DELETE FROM users WHERE id = ANY(dup_admin_ids);
                    END IF;

                    -- Decouple surviving ADMIN user from employees table
                    UPDATE users SET employee_id = NULL WHERE id = primary_admin_id;
                END IF;

                -- Remove any dummy ADMIN rows from employees table (and stray child rows)
                SELECT COALESCE(array_agg(id), ARRAY[]::UUID[])
                INTO admin_emp_ids
                FROM employees
                WHERE role = 'ADMIN';

                IF array_length(admin_emp_ids, 1) IS NOT NULL THEN
                    DELETE FROM employee_reporting_lines
                    WHERE employee_id = ANY(admin_emp_ids) OR manager_id = ANY(admin_emp_ids);
                    DELETE FROM employee_grade_history WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM employee_documents WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM job_cost_allocations
                    WHERE payroll_record_id IN (
                        SELECT id FROM payroll_records WHERE employee_id = ANY(admin_emp_ids)
                    );
                    DELETE FROM payroll_records WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM employee_salary WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM base_roster_entries WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM standing_assignments WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM scheduled_work
                    WHERE employee_id = ANY(admin_emp_ids) OR original_employee_id = ANY(admin_emp_ids);
                    DELETE FROM leave_requests
                    WHERE employee_id = ANY(admin_emp_ids) OR cover_employee_id = ANY(admin_emp_ids);
                    DELETE FROM reassignment_requests
                    WHERE original_employee_id = ANY(admin_emp_ids) OR new_employee_id = ANY(admin_emp_ids);
                    DELETE FROM attendance_comments
                    WHERE attendance_id IN (
                        SELECT id FROM attendance_records WHERE employee_id = ANY(admin_emp_ids)
                    );
                    UPDATE attendance_records SET current_calculation_id = NULL
                    WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM attendance_calculations
                    WHERE attendance_record_id IN (
                        SELECT id FROM attendance_records WHERE employee_id = ANY(admin_emp_ids)
                    );
                    DELETE FROM attendance_records WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM pending_visits WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM employee_last_position WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM tracking_gaps WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM site_visits WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM consent_records WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM registered_devices WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM sync_changes WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM alerts WHERE employee_id = ANY(admin_emp_ids);
                    DELETE FROM employees WHERE id = ANY(admin_emp_ids);
                END IF;
            END $$;
            """
        )
    )

    # 3. Enforce structural guardrails at the DB level
    op.create_check_constraint(
        "check_users_admin_standalone",
        "users",
        "(role = 'ADMIN' AND employee_id IS NULL) OR (role <> 'ADMIN' AND employee_id IS NOT NULL)",
    )
    op.create_index(
        "uq_users_single_admin",
        "users",
        [sa.text("(true)")],
        unique=True,
        postgresql_where=sa.text("role = 'ADMIN'"),
    )

    # Remove 'ADMIN' from allowed employee roles completely
    op.drop_constraint("check_employees_role_valid", "employees", type_="check")
    op.create_check_constraint(
        "check_employees_role_valid",
        "employees",
        "role IN ('WORKER', 'SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER')",
    )


def downgrade() -> None:
    # Restore 'ADMIN' in employees role constraint
    op.drop_constraint("check_employees_role_valid", "employees", type_="check")
    op.create_check_constraint(
        "check_employees_role_valid",
        "employees",
        "role IN ('WORKER', 'SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER', 'ADMIN')",
    )

    op.drop_index("uq_users_single_admin", table_name="users")
    op.drop_constraint("check_users_admin_standalone", "users", type_="check")

    # Recreate a bootstrap employee row for any standalone ADMIN user before restoring NOT NULL
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                adm RECORD;
                new_emp_id UUID;
            BEGIN
                FOR adm IN SELECT id, username FROM users WHERE employee_id IS NULL LOOP
                    INSERT INTO employees (
                        id, tally_id, name, email, role, country, is_driver,
                        join_date, is_active, version, created_at, updated_at
                    ) VALUES (
                        gen_random_uuid(), adm.username, 'System Administrator',
                        'admin@fieldworkertracker.local', 'ADMIN', 'AE', false,
                        '2026-01-01', true, 1, NOW(), NOW()
                    ) RETURNING id INTO new_emp_id;

                    UPDATE users SET employee_id = new_emp_id WHERE id = adm.id;
                END LOOP;
            END $$;
            """
        )
    )

    op.alter_column(
        "users",
        "employee_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
