"""Reset the database to a clean bootstrap state.

Clears all test artifacts, employees, salaries, and worksites,
leaving only the clean bootstrap ADMIN001 user and default settings.
All master data can then be cleanly imported via FieldWorkerTracker_Import_Template_v1.0.xlsx.
"""

import asyncio
from datetime import UTC, date, datetime
from sqlalchemy import text
from fw.core.db import async_session_factory, engine
from fw.modules.identity import hash_password

DEFAULT_PASSWORD = "ChangeMe123!"

async def reset_db():
    async with async_session_factory() as session:
        print("Clearing tables in dependency order...")
        
        # 1. Nullify user reference in audit logs so users can be deleted
        await session.execute(text("UPDATE audit_logs SET actor_user_id = NULL;"))

        # 2. Delete transactional and child tables
        tables = [
            "import_rows",
            "import_batches",
            "job_occurrences",
            "job_items",
            "worksites",
            "employee_salary",
            "employee_grade_history",
            "employee_documents",
            "employee_reporting_lines",
            "registered_devices",
            "user_sessions",
            "consent_policies",
            "time_rules",
            "company_setting_values",
            "public_holidays",
            "users",
            "employees",
            "accommodations",
            "groups",
            "zones",
        ]
        
        for table in tables:
            await session.execute(text(f"DELETE FROM {table};"))
            print(f"  Cleared {table}")
        
        await session.commit()
        print("All target tables cleared.")

        # Re-create bootstrap admin
        now = datetime.now(UTC)
        print("Creating bootstrap ADMIN001 user...")
        
        # 1. Admin employee record
        emp_res = await session.execute(text("""
            INSERT INTO employees (
                id, tally_id, name, email, role, country, is_driver, 
                join_date, is_active, version, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), 'ADMIN001', 'System Administrator', 'admin@fieldworkertracker.local',
                'ADMIN', 'AE', false, '2026-01-01', true, 1, :now, :now
            ) RETURNING id
        """), {"now": now})
        admin_emp_id = emp_res.scalar()

        # 2. Admin user account
        cred_hash = hash_password(DEFAULT_PASSWORD)
        await session.execute(text("""
            INSERT INTO users (
                id, employee_id, username, credential_hash, role,
                must_change_password, password_changed_at, is_active, version, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), :emp_id, 'ADMIN001', :cred_hash, 'ADMIN',
                false, :now, true, 1, :now, :now
            )
        """), {"emp_id": admin_emp_id, "cred_hash": cred_hash, "now": now})

        # 3. Default password company settings via SettingsService
        from fw.modules.settings import SettingsService
        await SettingsService.set_setting(
            session,
            key="default_password",
            value=DEFAULT_PASSWORD,
            effective_from=date(2026, 1, 1),
        )
        await SettingsService.set_setting(
            session,
            key="default_password_max_days",
            value=7,
            effective_from=date(2026, 1, 1),
        )

        await session.commit()
        print("Bootstrap ADMIN001 user and settings created.")

    await engine.dispose()
    print("Database reset completed successfully! Pristine state ready for master import.")

if __name__ == "__main__":
    asyncio.run(reset_db())
