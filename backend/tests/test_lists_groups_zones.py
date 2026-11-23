"""Owner decision 23 Nov 2026 (DEC-60 amendment): groups and zones added on screen, 3-digit group
codes, and tests that never touch the working database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.db import async_session_factory, engine
from fw.main import create_app
from fw.modules.imports import ImportRow, ImportService
from fw.modules.org.models import Group, Zone
from fw.rules.groups import is_group_code, next_group_code
from tests.ids import unique_job_number
from tests.test_batch6_features import db_required, get_admin_user_and_token
from tests.test_batch51c_lookups import _workbook
from tests.test_dec57_scope import _person


def _name(prefix: str) -> str:
    """A name no test has used: letters only."""
    letters = "".join(chr(ord("a") + int(c, 16)) for c in uuid4().hex[:8])
    return f"{prefix} {letters.title()}"


# --- Pure rules ---------------------------------------------------------------------------------


def test_group_codes_are_three_digits_and_generated_in_order() -> None:
    assert is_group_code("152") and is_group_code(" 007 ")
    assert not is_group_code("15") and not is_group_code("1520") and not is_group_code("G15")
    assert next_group_code([]) == "100"
    assert next_group_code(["102", "151", "DUBAI_PARKS", "104"]) == "152"
    assert next_group_code(["999", "100"]) == "101"
    assert next_group_code([f"{n:03d}" for n in range(100, 1000)]) is None


# --- Tests use a separate database --------------------------------------------------------------


def test_tests_use_a_separate_test_database() -> None:
    assert (engine.url.database or "").endswith("_test")
    env = {**os.environ, "FW_TEST_DATABASE": "fw_db"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_errors.py"],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 4, result.stdout + result.stderr
    assert "Refusing to run tests" in result.stdout + result.stderr


# --- Groups and zones added on screen ----------------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_add_group_and_zone_on_screen() -> None:
    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        _, eng_token = await _person(session, "ENGINEER", "EngGz")
        _, sup_token = await _person(session, "SUPERVISOR", "SupGz")
        await session.commit()
    admin = {"Authorization": f"Bearer {admin_token}"}
    eng = {"Authorization": f"Bearer {eng_token}"}
    sup = {"Authorization": f"Bearer {sup_token}"}
    name = _name("Marina Parks")

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # Adding a group or zone is Admin-only (DEC-61).
        assert (await c.post("/api/v1/groups", headers=sup, json={"name": name})).status_code == 403
        assert (await c.post("/api/v1/groups", headers=eng, json={"name": name})).status_code == 403

        # Only the name: the next free 3-digit code is generated.
        async with async_session_factory() as session:
            expected = next_group_code((await session.execute(select(Group.code))).scalars())
        r = await c.post("/api/v1/groups", headers=admin, json={"name": f"  {name}  "})
        assert r.status_code == 201, r.text
        assert r.json()["name"] == name and r.json()["code"] == expected

        # Duplicate names are refused ignoring case and spaces.
        r = await c.post("/api/v1/groups", headers=admin, json={"name": name.upper()})
        assert r.status_code == 409 and r.json()["code"] == "DUPLICATE_NAME"
        assert r.json()["existing"] == name and r.json()["existing_code"] == expected

        # A near name asks "Did you mean ...?" until confirmed.
        near = name[:-1] + ("x" if name[-1] != "x" else "y")
        r = await c.post("/api/v1/groups", headers=admin, json={"name": near})
        assert r.status_code == 422 and r.json()["code"] == "NEAR_MATCH"
        assert r.json()["suggestions"] == [name]
        r = await c.post(
            "/api/v1/groups", headers=admin, json={"name": near, "confirm_near_match": True}
        )
        assert r.status_code == 201 and is_group_code(r.json()["code"])

        # A code given for a new group must be 3 digits and free.
        r = await c.post("/api/v1/groups", headers=admin, json={"name": _name("A"), "code": "15"})
        assert r.status_code == 422 and r.json()["code"] == "INVALID_GROUP_CODE"
        r = await c.post(
            "/api/v1/groups", headers=admin, json={"name": _name("B"), "code": expected}
        )
        assert r.status_code == 409 and r.json()["code"] == "DUPLICATE_CODE"

        # Zones: code and name; duplicates and near names checked the same way.
        zone_name = _name("Jebel Ali")
        zone_code = f"Z{uuid4().hex[:5].upper()}"
        r = await c.post("/api/v1/zones", headers=eng, json={"code": zone_code, "name": zone_name})
        assert r.status_code == 403
        r = await c.post(
            "/api/v1/zones", headers=admin, json={"code": zone_code, "name": zone_name}
        )
        assert r.status_code == 201, r.text
        r = await c.post(
            "/api/v1/zones",
            headers=admin,
            json={"code": zone_code.lower(), "name": _name("Other")},
        )
        assert r.status_code == 409 and r.json()["code"] == "DUPLICATE_CODE"
        r = await c.post(
            "/api/v1/zones", headers=admin, json={"code": "ZX1", "name": zone_name.lower()}
        )
        assert r.status_code == 409 and r.json()["code"] == "DUPLICATE_NAME"
        r = await c.post(
            "/api/v1/zones",
            headers=admin,
            json={"code": f"Z{uuid4().hex[:5]}", "name": zone_name[:-1] + "q"},
        )
        assert r.status_code == 422 and r.json()["code"] == "NEAR_MATCH"
        assert (
            await c.post("/api/v1/zones", headers=sup, json={"code": "ZS", "name": _name("S")})
        ).status_code == 403


@db_required
@pytest.mark.asyncio
async def test_groups_sheet_new_codes_must_be_three_digits() -> None:
    legacy_code = f"LEG{uuid4().hex[:6].upper()}"
    async with async_session_factory() as session:
        admin_user, _ = await get_admin_user_and_token(session)
        session.add(Group(code=legacy_code, name=_name("Legacy")))
        used = set((await session.execute(select(Group.code))).scalars())
        await session.commit()
    free = next(f"{n}" for n in range(500, 1000) if f"{n}" not in used)
    content = _workbook(
        {
            "Groups": [
                {"group_code": "AB1", "group_name": _name("Bad")},
                {"group_code": free, "group_name": _name("Good")},
                # Existing groups with older codes still update.
                {"group_code": legacy_code, "group_name": _name("Renamed")},
            ]
        }
    )
    async with async_session_factory() as session:
        prev = await ImportService.parse_and_preview(
            session, content, "g.xlsx", admin_user.id, selected_sheets=["Groups"]
        )
        await session.commit()
        rows = (
            (await session.execute(select(ImportRow).where(ImportRow.batch_id == prev.batch_id)))
            .scalars()
            .all()
        )
        by_code = {r.normalized.get("group_code"): r for r in rows}
        assert by_code["AB1"].status == "ERROR"
        assert "INVALID_GROUP_CODE" in by_code["AB1"].codes
        assert by_code[free].status != "ERROR", by_code[free].messages
        assert by_code[legacy_code].status != "ERROR", by_code[legacy_code].messages
        assert by_code[legacy_code].action == "UPDATED"


@db_required
@pytest.mark.asyncio
async def test_zone_needs_code_and_name() -> None:
    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        await session.commit()
    admin = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        r = await c.post("/api/v1/zones", headers=admin, json={"name": _name("No Code")})
        assert r.status_code == 422
        r = await c.post("/api/v1/zones", headers=admin, json={"code": "  ", "name": _name("C")})
        assert r.status_code == 422
    async with async_session_factory() as session:
        assert (await session.execute(select(Zone).where(Zone.code == ""))).first() is None


@db_required
@pytest.mark.asyncio
async def test_worksite_edit_changes_group_and_zone() -> None:
    from datetime import date

    from fw.modules.jobs.models import Worksite

    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        old_g = Group(code=f"O{uuid4().hex[:6]}", name=_name("Old Group"))
        new_g = Group(code=f"N{uuid4().hex[:6]}", name=_name("New Group"))
        off_g = Group(code=f"X{uuid4().hex[:6]}", name=_name("Off Group"), is_active=False)
        zn = Zone(code=f"Z{uuid4().hex[:6]}", name=_name("Zone"))
        session.add_all([old_g, new_g, off_g, zn])
        await session.flush()
        ws = Worksite(
            job_number=unique_job_number("12A"),
            job_name="Edit site",
            group_id=old_g.id,
            zone_id=zn.id,
            country="AE",
            start_date=date(2026, 1, 1),
        )
        session.add(ws)
        await session.commit()
        ws_id, new_id, off_id = ws.id, new_g.id, off_g.id
    admin = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        r = await c.patch(
            f"/api/v1/worksites/{ws_id}",
            headers=admin,
            json={"group_id": str(off_id), "version": 1},
        )
        assert r.status_code == 422 and r.json()["code"] == "GROUP_NOT_FOUND"
        r = await c.patch(
            f"/api/v1/worksites/{ws_id}",
            headers=admin,
            json={"group_id": str(new_id), "version": 1},
        )
        assert r.status_code == 200, r.text
    async with async_session_factory() as session:
        assert (await session.get(Worksite, ws_id)).group_id == new_id  # type: ignore[union-attr]
