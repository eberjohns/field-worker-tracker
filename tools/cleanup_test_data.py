"""Clean up ephemeral test users, zones, and groups created by pytest fixtures."""

import asyncio
from sqlalchemy import text
from fw.core.db import async_session_factory, engine

async def cleanup():
    async with async_session_factory() as session:
        # Re-assign foreign key references to ADMIN001 so audit and salary history remains intact
        await session.execute(text("""
            UPDATE employee_salary 
            SET created_by_user_id = (SELECT id FROM users WHERE username = 'ADMIN001') 
            WHERE created_by_user_id IN (
                SELECT id FROM users WHERE username ~ '^ADM[0-9a-f]{4,8}$' AND username != 'ADMIN001'
            )
        """))
        await session.execute(text("""
            UPDATE audit_logs 
            SET actor_user_id = (SELECT id FROM users WHERE username = 'ADMIN001') 
            WHERE actor_user_id IN (
                SELECT id FROM users WHERE username ~ '^ADM[0-9a-f]{4,8}$' AND username != 'ADMIN001'
            )
        """))

        # Re-assign or delete ephemeral import batches created during tests
        await session.execute(text("""
            DELETE FROM import_rows 
            WHERE batch_id IN (
                SELECT id FROM import_batches 
                WHERE uploaded_by_user_id IN (
                    SELECT id FROM users WHERE username ~ '^ADM[0-9a-f]{4,8}$' AND username != 'ADMIN001'
                )
            )
        """))
        await session.execute(text("""
            DELETE FROM import_batches 
            WHERE uploaded_by_user_id IN (
                SELECT id FROM users WHERE username ~ '^ADM[0-9a-f]{4,8}$' AND username != 'ADMIN001'
            )
        """))

        # Delete test users created by test fixtures
        res_users = await session.execute(text("""
            DELETE FROM users 
            WHERE username ~ '^ADM[0-9a-f]{4,8}$' 
              AND username != 'ADMIN001'
            RETURNING username
        """))
        deleted_users = res_users.fetchall()
        print(f"Cleaned up {len(deleted_users)} test admin users.")

        # Clean up test worksites and occurrences created by tests
        await session.execute(text("""
            DELETE FROM job_occurrences 
            WHERE job_item_id IN (
                SELECT id FROM job_items WHERE worksite_id IN (
                    SELECT id FROM worksites 
                    WHERE job_name IN ('Dubai Marina Landscape', 'Dubai Marina Indoor', 'Budget Only Test Job', 'Dubai Hills Estate Landscape', 'Dubai Hills Club Indoor Feature', 'Phase 04 Test Job')
                       OR job_number ~ '^99A'
                )
            )
        """))
        await session.execute(text("""
            DELETE FROM job_items 
            WHERE worksite_id IN (
                SELECT id FROM worksites 
                WHERE job_name IN ('Dubai Marina Landscape', 'Dubai Marina Indoor', 'Budget Only Test Job', 'Dubai Hills Estate Landscape', 'Dubai Hills Club Indoor Feature', 'Phase 04 Test Job')
                   OR job_number ~ '^99A'
            )
        """))
        res_ws = await session.execute(text("""
            DELETE FROM worksites 
            WHERE job_name IN ('Dubai Marina Landscape', 'Dubai Marina Indoor', 'Budget Only Test Job', 'Dubai Hills Estate Landscape', 'Dubai Hills Club Indoor Feature', 'Phase 04 Test Job')
               OR job_number ~ '^99A'
            RETURNING job_number
        """))
        deleted_ws = res_ws.fetchall()
        print(f"Cleaned up {len(deleted_ws)} ephemeral test worksites.")

        # Clean up test groups not linked to anything
        res_groups = await session.execute(text("""
            DELETE FROM groups 
            WHERE (name IN ('Test Group', 'Demo Facility Management', 'Phase 04 Demo Group', 'Phase 04 Test Group')
               OR code ~ '^G[0-9a-f]{4}$'
               OR code ~ '^GRP[0-9a-f]{3}$')
              AND id NOT IN (SELECT group_id FROM worksites)
            RETURNING code
        """))
        deleted_groups = res_groups.fetchall()
        print(f"Cleaned up {len(deleted_groups)} unused test groups.")

        # Clean up test zones not linked to anything
        res_zones = await session.execute(text("""
            DELETE FROM zones 
            WHERE (name IN ('Test Zone', 'Dubai Marina Zone', 'Phase 04 Test Zone')
               OR code ~ '^Z[0-9a-f]{4}$'
               OR code ~ '^ZON[0-9a-f]{3}$')
              AND id NOT IN (SELECT zone_id FROM worksites)
            RETURNING code
        """))
        deleted_zones = res_zones.fetchall()
        print(f"Cleaned up {len(deleted_zones)} unused test zones.")

        await session.commit()
    await engine.dispose()
    print("Database cleanup complete.")

if __name__ == "__main__":
    asyncio.run(cleanup())
