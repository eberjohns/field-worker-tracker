"""Seed script for Phase 07 demo and mobile tester proxy.

Provisions:
1. Company settings for mobile default password and day plan.
2. Active Consent Policy.
3. Accommodation (Warsan Staff Accommodation) with polygon boundary.
4. Worksite (Dubai Marina Towers) with polygon boundary and Job Item.
5. Worker (1193 - Shanto Miah) with default password 'Welcome123!' (must_change_password=True).
6. Admin user (ADMIN001) with 'Admin123!'.
7. ScheduledWork items for the next 7 days for worker 1193.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from fw.core.db import async_session_factory
from fw.modules.identity import hash_password
from fw.modules.identity.models import User
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.org.models import Accommodation, Employee, EmployeeReportingLine, Group, Zone
from fw.modules.scheduling.models import ScheduledWork
from fw.modules.settings.models import CompanySettingValue, ConsentPolicy
from fw.modules.sync.service import SyncService


async def seed():
    print("🌱 Starting Phase 07 Demo Seeding...")
    async with async_session_factory() as session:
        # 1. Company Settings
        settings_to_seed = [
            ("mobile_default_password", "Welcome123!"),
            ("day_plan_alarm_lead_minutes", 30),
            ("day_plan_window_days_ahead", 30),
            ("sync_retention_days", 30),
            ("geofence_circle_radius_m", 300),
            ("approach_polling_interval_s", 60),
            ("confirmation_polling_interval_s", 300),
        ]
        for key, val in settings_to_seed:
            res = await session.execute(
                select(CompanySettingValue).where(CompanySettingValue.setting_key == key)
            )
            existing = res.scalar_one_or_none()
            if not existing:
                setting = CompanySettingValue(
                    setting_key=key,
                    value=val,
                    effective_from=date(2026, 1, 1),
                )
                session.add(setting)
            else:
                existing.value = val
        await session.flush()
        print("  ✓ Company settings configured")

        # 2. Consent Policy
        res = await session.execute(
            select(ConsentPolicy).where(
                ConsentPolicy.version == 1,
                ConsentPolicy.language == "en",
            )
        )
        policy = res.scalar_one_or_none()
        if not policy:
            policy = ConsentPolicy(
                version=1,
                language="en",
                title="UAE Location & Work Tracking Consent Policy",
                body=(
                    "### Worker Location Tracking Consent\n\n"
                    "By using this mobile application, you agree to allow Field Worker Tracker "
                    "to collect your GPS location strictly during working hours and within designated "
                    "worksite geofences in accordance with UAE Federal Decree-Law No. 45 of 2021 on Personal Data Protection."
                ),
            )
            session.add(policy)
            await session.flush()
        print("  ✓ Consent Policy v1 (en) verified")

        # 3. Group & Zone
        res = await session.execute(select(Group).where(Group.code == "DUBAI_PARKS"))
        group = res.scalar_one_or_none()
        if not group:
            group = Group(code="DUBAI_PARKS", name="Dubai Parks & Resorts")
            session.add(group)
            await session.flush()

        res = await session.execute(select(Zone).where(Zone.code == "ZONE_A"))
        zone = res.scalar_one_or_none()
        if not zone:
            zone = Zone(code="ZONE_A", name="Zone A (Marina / JBR)")
            session.add(zone)
            await session.flush()

        # 4. Accommodation with Polygon Boundary (Warsan)
        res = await session.execute(
            select(Accommodation).where(Accommodation.accommodation_code == "WARSAN_01")
        )
        accom = res.scalar_one_or_none()
        warsan_poly_wkt = (
            "POLYGON((55.4100 25.1560, 55.4145 25.1560, 55.4145 25.1605, 55.4100 25.1605, 55.4100 25.1560))"
        )
        if not accom:
            accom = Accommodation(
                accommodation_code="WARSAN_01",
                name="Warsan Staff Accommodation Camp",
                address="Al Warsan 3, Dubai, UAE",
                boundary=WKTElement(warsan_poly_wkt, srid=4326),
                rep_latitude=Decimal("25.158250"),
                rep_longitude=Decimal("55.412250"),
                is_active=True,
            )
            session.add(accom)
            await session.flush()
        else:
            accom.name = "Warsan Staff Accommodation Camp"
            accom.address = "Al Warsan 3, Dubai, UAE"
            accom.boundary = WKTElement(warsan_poly_wkt, srid=4326)
            accom.rep_latitude = Decimal("25.158250")
            accom.rep_longitude = Decimal("55.412250")
            await session.flush()
        print(f"  ✓ Accommodation '{accom.name}' ready")

        # 5. Worksite with Polygon Boundary (Dubai Silicon Oasis, ~4.1 km from Warsan)
        res = await session.execute(
            select(Worksite).where(Worksite.job_number == "12A14301")
        )
        worksite = res.scalar_one_or_none()
        silicon_poly_wkt = (
            "POLYGON((55.3800 25.1280, 55.3880 25.1280, 55.3880 25.1340, 55.3800 25.1340, 55.3800 25.1280))"
        )
        if not worksite:
            worksite = Worksite(
                job_number="12A14301",
                job_name="Dubai Silicon Oasis Landscape Maintenance",
                group_id=group.id,
                zone_id=zone.id,
                customer_type="COMMERCIAL",
                is_outdoor=True,
                country="AE",
                boundary=WKTElement(silicon_poly_wkt, srid=4326),
                rep_latitude=Decimal("25.131000"),
                rep_longitude=Decimal("55.384000"),
                is_active=True,
            )
            session.add(worksite)
            await session.flush()
        else:
            worksite.job_name = "Dubai Silicon Oasis Landscape Maintenance"
            worksite.boundary = WKTElement(silicon_poly_wkt, srid=4326)
            worksite.rep_latitude = Decimal("25.131000")
            worksite.rep_longitude = Decimal("55.384000")
            await session.flush()
        print(f"  ✓ Worksite '{worksite.job_name}' ready (~4.1 km commute from camp)")

        # 6. Job Item
        res = await session.execute(
            select(JobItem).where(
                JobItem.worksite_id == worksite.id,
                JobItem.sub_item_code == "01",
            )
        )
        job_item = res.scalar_one_or_none()
        if not job_item:
            job_item = JobItem(
                worksite_id=worksite.id,
                sub_item_code="01",
                staff_grade_description="Landscape Gardener",
                planned_grade_code="LG-01",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("5.00"),
                period_interval=1,
                required_staff_count=5,
                hours_per_occurrence_per_staff=Decimal("8.000"),
                start_date=date(2026, 1, 1),
                deployment_type="PERMANENT",
                is_active=True,
            )
            session.add(job_item)
            await session.flush()
        print("  ✓ Job Item ready")

        # 7. Supervisor Employee (SUP001 - Shakir Khisham)
        res = await session.execute(
            select(Employee).where(Employee.tally_id == "SUP001")
        )
        supervisor = res.scalar_one_or_none()
        if not supervisor:
            supervisor = Employee(
                tally_id="SUP001",
                name="Shakir Khisham",
                role="SUPERVISOR",
                staff_grade_description="Field Supervisor",
                phone="+971501234567",
                country="AE",
                is_active=True,
            )
            session.add(supervisor)
            await session.flush()
        else:
            supervisor.name = "Shakir Khisham"
            supervisor.phone = "+971501234567"
            supervisor.is_active = True
            await session.flush()
        print(f"  ✓ Supervisor '{supervisor.name}' (ID: SUP001) ready")

        # 8. Employee 1193 (Shanto Miah)
        res = await session.execute(
            select(Employee).where(Employee.tally_id == "1193")
        )
        worker = res.scalar_one_or_none()
        if not worker:
            worker = Employee(
                tally_id="1193",
                name="Shanto Miah",
                role="WORKER",
                staff_grade_description="Landscape Gardener",
                phone="+971509876543",
                accommodation_id=accom.id,
                weekly_off_day="FRIDAY",
                country="AE",
                is_active=True,
            )
            session.add(worker)
            await session.flush()
        else:
            worker.accommodation_id = accom.id
            worker.weekly_off_day = "FRIDAY"
            worker.is_active = True
            await session.flush()
        print(f"  ✓ Employee '{worker.name}' (ID: 1193) ready")

        # 9. Reporting line: worker -> supervisor
        rep_res = await session.execute(
            select(EmployeeReportingLine).where(
                EmployeeReportingLine.employee_id == worker.id,
                EmployeeReportingLine.relationship == "SUPERVISOR",
            )
        )
        rep_line = rep_res.scalar_one_or_none()
        if not rep_line:
            rep_line = EmployeeReportingLine(
                employee_id=worker.id,
                manager_id=supervisor.id,
                relationship="SUPERVISOR",
            )
            session.add(rep_line)
            await session.flush()
        else:
            rep_line.manager_id = supervisor.id
            await session.flush()
        print(f"  ✓ Reporting line linked: {worker.name} reports to {supervisor.name}")

        # 10. User for Employee 1193
        res = await session.execute(
            select(User).where(User.username == "1193")
        )
        user_worker = res.scalar_one_or_none()
        if not user_worker:
            user_worker = User(
                username="1193",
                employee_id=worker.id,
                role="WORKER",
                credential_hash=hash_password("Welcome123!"),
                must_change_password=False,
                is_active=True,
            )
            session.add(user_worker)
            await session.flush()
        else:
            user_worker.employee_id = worker.id
            user_worker.credential_hash = hash_password("Welcome123!")
            user_worker.must_change_password = False
            user_worker.is_active = True
            await session.flush()
        print("  ✓ Worker user account (1193 / Welcome123!) ready (must_change_password=False)")

        # 9. Admin User (ADMIN001)
        res = await session.execute(
            select(User).where(User.username == "ADMIN001")
        )
        admin = res.scalar_one_or_none()
        if not admin:
            # Check or create Admin Employee
            admin_emp_res = await session.execute(
                select(Employee).where(Employee.tally_id == "ADMIN001")
            )
            admin_emp = admin_emp_res.scalar_one_or_none()
            if not admin_emp:
                admin_emp = Employee(
                    tally_id="ADMIN001",
                    name="System Administrator",
                    role="ADMIN",
                    country="AE",
                    is_active=True,
                )
                session.add(admin_emp)
                await session.flush()

            admin = User(
                username="ADMIN001",
                employee_id=admin_emp.id,
                role="ADMIN",
                credential_hash=hash_password("Admin123!"),
                must_change_password=False,
                is_active=True,
            )
            session.add(admin)
            await session.flush()
        print("  ✓ Admin account (ADMIN001 / Admin123!) ready")

        # 11. Scheduled Work for Today and next 30 days (excluding Fridays after today)
        today = date.today()
        seeded_count = 0
        for i in range(30):
            target_date = today + timedelta(days=i)
            # Ensure today always has a shift; other days skip weekly off (Friday = weekday 4)
            if i > 0 and target_date.weekday() == 4:
                continue

            res = await session.execute(
                select(ScheduledWork).where(
                    ScheduledWork.employee_id == worker.id,
                    ScheduledWork.work_date == target_date,
                    ScheduledWork.status == "ACTIVE",
                )
            )
            existing_sched = res.scalar_one_or_none()
            if not existing_sched:
                sched = ScheduledWork(
                    employee_id=worker.id,
                    work_date=target_date,
                    job_item_id=job_item.id,
                    worksite_id=worksite.id,
                    assigned_hours=Decimal("8.00"),
                    sequence=1,
                    status="ACTIVE",
                    source="STANDING",
                )
                session.add(sched)
                seeded_count += 1
            else:
                existing_sched.worksite_id = worksite.id
                existing_sched.job_item_id = job_item.id
                existing_sched.assigned_hours = Decimal("8.00")
                seeded_count += 1
        await session.flush()
        print(f"  ✓ Scheduled Work seeded ({seeded_count} active shifts) for {worker.name} over next 30 days")

        await session.commit()
    print("✨ Phase 07 Demo Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
