"""Seed script for Phase 01 (Access and People).

Populates fictional seed data demonstrating:
- Company setting default_password and default_password_max_days
- Admin bootstrap account
- Hierarchical personas (Engineers, Superintendents, Supervisors, Workers)
- Multiple superintendents linked to a worker (DEC-10 demo)
- Accommodations, Groups, Zones
- Employee documents and registered devices
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import async_session_factory
from fw.modules.identity import User, hash_password
from fw.modules.org import (
    Accommodation,
    Employee,
    EmployeeDocument,
    EmployeeReportingLine,
    Group,
    RegisteredDevice,
    Zone,
)
from fw.modules.settings import SettingsService

DEFAULT_PASSWORD = "ChangeMe123!"


async def seed_data(session: AsyncSession) -> None:
    now = datetime.now(UTC)

    # 1. Company settings
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

    # 2. Accommodations
    acc1 = Accommodation(
        accommodation_code="ACC-ALQUOZ",
        name="Al Quoz Camp A",
        address="Al Quoz Industrial Area 3, Dubai",
        rep_latitude=Decimal("25.132500"),
        rep_longitude=Decimal("55.234100"),
    )
    acc2 = Accommodation(
        accommodation_code="ACC-SONAPUR",
        name="Sonapur Staff Camp",
        address="Muhaisnah 2, Dubai",
        rep_latitude=Decimal("25.271100"),
        rep_longitude=Decimal("55.405200"),
    )
    session.add_all([acc1, acc2])
    await session.flush()

    # 3. Groups and Zones
    g1 = Group(code="GRP-DXB-PARKS", name="Dubai Parks & Resorts")
    g2 = Group(code="GRP-MINA", name="Mina Rashid")
    z1 = Zone(code="ZN-NORTH", name="Zone North (Main Grounds)")
    z2 = Zone(code="ZN-SOUTH", name="Zone South (Waterfront)")
    session.add_all([g1, g2, z1, z2])
    await session.flush()

    # 4. Employees & Linked Users
    async def create_person(
        tally_id: str,
        name: str,
        role: str,
        sgd: str | None = None,
        grade_code: str | None = None,
        accommodation_id: str | None = None,
        weekly_off_day: str = "SUNDAY",
        is_driver: bool = False,
        must_change_password: bool = False,
    ) -> Employee:
        existing = await session.execute(select(Employee).where(Employee.tally_id == tally_id))
        emp = existing.scalar_one_or_none()
        if emp:
            return emp

        emp = Employee(
            tally_id=tally_id,
            name=name,
            email=f"{tally_id.lower()}@fieldworkertracker.local",
            role=role,
            grade_code=grade_code,
            staff_grade_description=sgd,
            accommodation_id=acc1.id if accommodation_id == "ACC-ALQUOZ" else None,
            weekly_off_day=weekly_off_day,
            is_driver=is_driver,
            country="AE",
            join_date=date(2025, 1, 1),
        )
        session.add(emp)
        await session.flush()

        usr = User(
            employee_id=emp.id,
            username=tally_id,
            credential_hash=hash_password(DEFAULT_PASSWORD),
            role=role,
            must_change_password=must_change_password,
            password_changed_at=now if not must_change_password else None,
        )
        session.add(usr)
        await session.flush()
        return emp

    # Personas:
    await create_person("ADMIN001", "System Administrator", "ADMIN", grade_code="G7A")
    engineer = await create_person("ENG001", "Ahmed Al-Mansoor", "ENGINEER", grade_code="G5A")
    supt1 = await create_person("SUPT001", "Rashid Tariq", "SUPERINTENDENT", grade_code="G4B")
    supt2 = await create_person("SUPT002", "Faisal Khan", "SUPERINTENDENT", grade_code="G4B")
    supervisor1 = await create_person(
        "SUP001", "Zaid Mahmoud", "SUPERVISOR", sgd="Senior Supervisor", grade_code="G3A"
    )
    supervisor2 = await create_person(
        "SUP002", "Bilal Hassan", "SUPERVISOR", sgd="Field Supervisor", grade_code="G3A"
    )

    worker1 = await create_person(
        "WRK001",
        "Ali Hassan",
        "WORKER",
        sgd="Gardener",
        grade_code="G2B26",
        accommodation_id="ACC-ALQUOZ",
        must_change_password=True,
    )
    worker2 = await create_person(
        "WRK002",
        "Mohammed Qasim",
        "WORKER",
        sgd="Irrigation Helper",
        grade_code="G1A10",
        accommodation_id="ACC-ALQUOZ",
        is_driver=True,
        must_change_password=True,
    )
    worker3 = await create_person(
        "WRK003",
        "Suresh Kumar",
        "WORKER",
        sgd="Driver",
        grade_code="G2A15",
        weekly_off_day="FRIDAY",
        is_driver=True,
        must_change_password=True,
    )

    # 5. Reporting Links:
    # Supervisor SUP001 reports to Engineer ENG001 and Superintendent SUPT001
    # Worker WRK001 has 1 Supervisor (SUP001) and TWO Superintendents (SUPT001, SUPT002) - DEC-10 demo!
    # Worker WRK002 reports to Supervisor SUP001
    # Worker WRK003 reports to Supervisor SUP002
    reporting_links = [
        (supervisor1.id, engineer.id, "ENGINEER"),
        (supervisor1.id, supt1.id, "SUPERINTENDENT"),
        (worker1.id, supervisor1.id, "SUPERVISOR"),
        (worker1.id, supt1.id, "SUPERINTENDENT"),
        (worker1.id, supt2.id, "SUPERINTENDENT"),
        (worker2.id, supervisor1.id, "SUPERVISOR"),
        (worker3.id, supervisor2.id, "SUPERVISOR"),
    ]

    for emp_id, mgr_id, rel in reporting_links:
        existing_link = await session.execute(
            select(EmployeeReportingLine).where(
                EmployeeReportingLine.employee_id == emp_id,
                EmployeeReportingLine.manager_id == mgr_id,
                EmployeeReportingLine.relationship == rel,
            )
        )
        if not existing_link.scalar_one_or_none():
            link = EmployeeReportingLine(employee_id=emp_id, manager_id=mgr_id, relationship=rel)
            session.add(link)
    await session.flush()

    # 6. Documents for workers
    doc1 = EmployeeDocument(
        employee_id=worker1.id,
        document_type="EMIRATES_ID",
        expiry_date=date.today() + timedelta(days=120),
    )
    doc2 = EmployeeDocument(
        employee_id=worker1.id,
        document_type="VISA",
        expiry_date=date.today() + timedelta(days=25),  # Expiring soon (<30 days)
    )
    doc3 = EmployeeDocument(
        employee_id=worker2.id,
        document_type="DRIVING_LICENCE",
        expiry_date=date.today() + timedelta(days=300),
    )
    session.add_all([doc1, doc2, doc3])
    await session.flush()

    # 7. Device binding for WRK001
    dev1 = RegisteredDevice(
        employee_id=worker1.id,
        device_identifier="android-install-uuid-001",
        platform="ANDROID",
        device_model="Samsung Galaxy A14",
        app_version="1.0.0",
        os_version="Android 14",
        registered_at=now,
        last_seen_at=now,
    )
    session.add(dev1)
    await session.commit()
    print("Phase 01 seed data loaded successfully!")


async def main() -> None:
    async with async_session_factory() as session:
        await seed_data(session)


if __name__ == "__main__":
    asyncio.run(main())
