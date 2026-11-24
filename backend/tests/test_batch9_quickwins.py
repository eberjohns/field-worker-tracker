"""Batch 9 step 2 (performance quick wins): behaviour that must hold after the changes.

- Approvals: a count-only endpoint that matches the inbox and writes nothing; a paged inbox.
- Occurrences: not loaded with worksites; date-range endpoints with scope (DEC-57).
- Planners: scoped to the user's worksites (DEC-57); reassignment destinations stay unscoped.
- Settings read once per request; staffing gaps with a constant number of queries.
- GZip for responses of 1 KB or more, never for the SSE stream or xlsx/pdf files.
"""

import contextlib
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response, StreamingResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from starlette.middleware.gzip import GZipMiddleware

from fw.core.clock import site_today
from fw.core.db import async_session_factory, engine
from fw.main import GZIP_EXCLUDED_CONTENT_TYPES, GZIP_MINIMUM_SIZE, create_app
from fw.modules.identity import User
from fw.modules.jobs.models import JobOccurrence, Worksite
from fw.modules.scheduling.models import (
    BaseRosterEntry,
    BaseRosterTemplate,
    LeaveRequest,
    ReassignmentRequest,
    ScheduledWork,
)
from tests.test_batch6_features import db_required
from tests.test_dec57_scope import _build, _h


@pytest.fixture
async def ctx():
    scenario = await _build()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, scenario


@contextlib.contextmanager
def captured_sql() -> Iterator[list[str]]:
    """Every SQL statement the app runs inside the block."""
    statements: list[str] = []

    def _record(_conn, _cursor, statement, _params, _context, _many) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)


async def _user_id(employee_id: UUID) -> UUID:
    async with async_session_factory() as session:
        return (
            await session.execute(select(User.id).where(User.employee_id == employee_id))
        ).scalar_one()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


# --------------------------------------------------------------------------- approvals
@db_required
async def test_approval_counts_match_the_inbox_and_write_nothing(ctx) -> None:
    client, s = ctx
    today = site_today("AE")
    sup_user = await _user_id(s.sup_a.id)
    async with async_session_factory() as session:
        session.add(
            LeaveRequest(
                employee_id=s.wa.id,
                leave_type="ANNUAL",
                from_date=today + timedelta(days=10),
                to_date=today + timedelta(days=12),
                reason="Family trip",
                recorded_by_user_id=sup_user,
            )
        )
        future = ReassignmentRequest(
            reassignment_type="ADD",
            date_from=today + timedelta(days=3),
            date_to=today + timedelta(days=4),
            new_employee_id=s.wa.id,
            reason_category="CAPACITY",
            reason="Extra hands",
            requested_by_user_id=sup_user,
        )
        expired = ReassignmentRequest(
            reassignment_type="ADD",
            date_from=today - timedelta(days=2),
            date_to=today + timedelta(days=1),
            new_employee_id=s.wa.id,
            reason_category="CAPACITY",
            reason="Too late",
            requested_by_user_id=sup_user,
        )
        session.add_all([future, expired])
        await session.commit()
        expired_id = expired.id

    for token in (s.eng_token, s.admin_token):
        counts = await client.get("/api/v1/approvals/counts", headers=_h(token))
        assert counts.status_code == 200, counts.text
        inbox = await client.get("/api/v1/approvals?status=PENDING", headers=_h(token))
        assert inbox.status_code == 200, inbox.text
        assert counts.json() == inbox.json()["counts"]

    eng = (await client.get("/api/v1/approvals/counts", headers=_h(s.eng_token))).json()
    # One pending leave; one open reassignment (the expired one is not pending any more).
    assert eng["leave"] == 1 and eng["reassignments"] == 1
    assert eng["total"] == eng["leave"] + eng["reassignments"] + eng["attendance"]

    eng_inbox = (
        await client.get("/api/v1/approvals?type=reassignments", headers=_h(s.eng_token))
    ).json()
    assert str(expired_id) not in {r["id"] for r in eng_inbox["reassignment_requests"]}

    async with async_session_factory() as session:
        status = (
            await session.execute(
                select(ReassignmentRequest.status).where(ReassignmentRequest.id == expired_id)
            )
        ).scalar_one()
    assert status == "PENDING"  # counting did not write

    assert (
        await client.get("/api/v1/approvals/counts", headers=_h(s.sup_a_token))
    ).status_code == 403


@db_required
async def test_inbox_pages_one_type_at_a_time(ctx) -> None:
    client, s = ctx
    today = site_today("AE")
    sup_user = await _user_id(s.sup_a.id)
    async with async_session_factory() as session:
        for i in range(3):
            session.add(
                LeaveRequest(
                    employee_id=s.wa.id,
                    leave_type="ANNUAL",
                    from_date=today + timedelta(days=20 + 5 * i),
                    to_date=today + timedelta(days=21 + 5 * i),
                    reason=f"Leave {i}",
                    recorded_by_user_id=sup_user,
                )
            )
        await session.commit()

    url = "/api/v1/approvals?status=PENDING&type=leave&limit=2"
    first = (await client.get(f"{url}&offset=0", headers=_h(s.eng_token))).json()
    second = (await client.get(f"{url}&offset=2", headers=_h(s.eng_token))).json()
    assert first["totals"]["leave"] == 3
    assert first["limit"] == 2 and first["offset"] == 0
    assert len(first["leave_requests"]) == 2 and len(second["leave_requests"]) == 1
    ids = {r["id"] for r in first["leave_requests"]} | {r["id"] for r in second["leave_requests"]}
    assert len(ids) == 3
    # Only the requested type is listed; the badge counts are still all there.
    assert first["reassignment_requests"] == [] and first["attendance_rows"] == []
    assert first["counts"]["leave"] == 3

    everything = (await client.get("/api/v1/approvals", headers=_h(s.eng_token))).json()
    assert {"leave_requests", "reassignment_requests", "attendance_rows"} <= set(everything)
    assert len(everything["leave_requests"]) == 3

    bad = await client.get("/api/v1/approvals?type=bogus", headers=_h(s.eng_token))
    assert bad.status_code == 422


# ------------------------------------------------------------------------- occurrences
async def _add_occurrences(item_id: UUID) -> None:
    windows = [
        (date(2027, 1, 26), date(2027, 2, 1)),  # crosses into February
        (date(2027, 2, 2), date(2027, 2, 8)),
        (date(2027, 3, 1), date(2027, 3, 7)),
    ]
    async with async_session_factory() as session:
        for start, end in windows:
            session.add(
                JobOccurrence(
                    job_item_id=item_id,
                    window_start=start,
                    window_end=end,
                    slot_index=1,
                    required_staff_count=2,
                    required_hours_per_staff=Decimal("8.0"),
                )
            )
        await session.commit()


@db_required
async def test_occurrence_range_endpoints_overlap_and_summary(ctx) -> None:
    client, s = ctx
    await _add_occurrences(s.item_u.id)
    feb = "from_date=2027-02-01&to_date=2027-02-28"
    for url in (
        f"/api/v1/worksites/{s.site_u.id}/occurrences?{feb}",
        f"/api/v1/job-items/{s.item_u.id}/occurrences?{feb}",
    ):
        resp = await client.get(url, headers=_h(s.admin_token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        starts = [o["window_start"] for o in body["occurrences"]]
        assert starts == ["2027-01-26", "2027-02-02"]  # overlap: the window from January counts
        summary = body["summary"]
        assert summary["total_count"] == 3
        assert Decimal(str(summary["planned_hours"])) == Decimal("48")
        assert summary["first_window_start"] == "2027-01-26"
        assert summary["last_window_end"] == "2027-03-07"
        assert summary["months"] == ["2027-01", "2027-02", "2027-03"]
        assert summary["roles"] == ["Helper"]

    base = f"/api/v1/worksites/{s.site_u.id}/occurrences"
    for query in (
        "from_date=2027-01-01&to_date=2028-01-02",  # 367 days
        "from_date=2027-02-01&to_date=2027-01-01",  # backwards
        "from_date=2027-02-01",  # missing the end
    ):
        resp = await client.get(f"{base}?{query}", headers=_h(s.admin_token))
        assert resp.status_code == 422, query


@db_required
async def test_occurrences_outside_scope_are_not_found(ctx) -> None:
    client, s = ctx
    await _add_occurrences(s.item_u.id)  # Site U has no supervisor: outside A's scope
    feb = "from_date=2027-02-01&to_date=2027-02-28"
    for url in (
        f"/api/v1/worksites/{s.site_u.id}/occurrences?{feb}",
        f"/api/v1/job-items/{s.item_u.id}/occurrences?{feb}",
        f"/api/v1/occurrences?worksite_id={s.site_u.id}",
        f"/api/v1/occurrences?job_item_id={s.item_u.id}",
    ):
        resp = await client.get(url, headers=_h(s.sup_a_token))
        assert resp.status_code == 404, url

    unfiltered = await client.get("/api/v1/occurrences?limit=1000", headers=_h(s.sup_a_token))
    assert unfiltered.status_code == 200
    assert str(s.item_u.id) not in {o["job_item_id"] for o in unfiltered.json()}

    admin = await client.get(
        f"/api/v1/occurrences?job_item_id={s.item_u.id}", headers=_h(s.admin_token)
    )
    assert admin.status_code == 200 and len(admin.json()) == 3


@db_required
async def test_worksite_list_loads_no_job_items_or_occurrences(ctx) -> None:
    client, s = ctx
    await _add_occurrences(s.item_u.id)
    with captured_sql() as statements:
        resp = await client.get("/api/v1/worksites?limit=500", headers=_h(s.admin_token))
    assert resp.status_code == 200
    assert not [q for q in statements if "job_occurrences" in q]
    assert not [q for q in statements if "FROM job_items" in q]


# ----------------------------------------------------------------------------- planners
@db_required
async def test_planners_show_only_my_worksites_but_destinations_show_all(ctx) -> None:
    client, s = ctx
    week = _monday(site_today("AE")).isoformat()

    def site_ids(body: dict) -> set[str]:
        return {w["worksite_id"] for w in body["worksites"]}

    for url in (
        "/api/v1/base-planner/worksites",
        f"/api/v1/operational-planner/coverage?week_start={week}",
        f"/api/v1/schedule/coverage?week_start={week}",
    ):
        mine = await client.get(url, headers=_h(s.sup_a_token))
        assert mine.status_code == 200, (url, mine.text)
        ids = site_ids(mine.json())
        assert str(s.site_a.id) in ids, url
        assert str(s.site_b.id) not in ids and str(s.site_u.id) not in ids, url

        admin = site_ids((await client.get(url, headers=_h(s.admin_token))).json())
        assert {str(s.site_a.id), str(s.site_b.id), str(s.site_u.id)} <= admin, url

    roster = await client.get(
        f"/api/v1/operational-planner/roster?week_start={week}", headers=_h(s.sup_a_token)
    )
    assert roster.status_code == 200
    workers = {w["employee_id"] for w in roster.json()["workers"]}
    assert str(s.wa.id) in workers  # own crew
    assert str(s.wb.id) in workers  # works on A's site
    assert str(s.sup_b.id) not in workers

    # DEC-57: reassignment destinations list every active worksite, whatever the scope.
    dest = await client.get("/api/v1/job-items/destinations", headers=_h(s.sup_a_token))
    assert dest.status_code == 200
    dest_sites = {r["worksite_id"] for r in dest.json()}
    assert {str(s.site_b.id), str(s.site_u.id)} <= dest_sites


@db_required
async def test_planners_read_settings_once_per_country(ctx) -> None:
    client, s = ctx
    week = _monday(site_today("AE")).isoformat()
    async with async_session_factory() as session:
        countries = set(
            (
                await session.execute(
                    select(Worksite.country).where(Worksite.is_active.is_(True)).distinct()
                )
            )
            .scalars()
            .all()
        )
        worksites = len(
            (await session.execute(select(Worksite.id).where(Worksite.is_active.is_(True))))
            .scalars()
            .all()
        )
    assert worksites > len(countries)  # otherwise the check below proves nothing
    for url in (
        "/api/v1/base-planner/worksites",
        f"/api/v1/operational-planner/coverage?week_start={week}",
    ):
        with captured_sql() as statements:
            resp = await client.get(url, headers=_h(s.admin_token))
        assert resp.status_code == 200
        reads = [q for q in statements if "company_setting_values" in q]
        assert len(reads) <= len(countries), url


# ------------------------------------------------------------------------ staffing gaps
@db_required
async def test_staffing_gaps_query_count_does_not_grow_with_leave_length(ctx) -> None:
    client, s = ctx
    start = date(2031, 3, 3)  # far from other tests' data
    sup_user = await _user_id(s.sup_a.id)
    async with async_session_factory() as session:
        tpl = BaseRosterTemplate(
            job_item_id=s.item_u.id, allocation_mode="DAY_OF_WEEK", start_date=start
        )
        session.add(tpl)
        await session.flush()
        session.add(
            BaseRosterEntry(
                template_id=tpl.id,
                employee_id=s.wa.id,
                weekday_mask="ALL",
                assigned_hours=Decimal("8.0"),
            )
        )
        session.add(
            LeaveRequest(
                employee_id=s.wa.id,
                leave_type="ANNUAL",
                from_date=start,
                to_date=start + timedelta(days=13),
                reason="Long leave",
                status="APPROVED",
                recorded_by_user_id=sup_user,
            )
        )
        # Day 2 is already covered.
        session.add(
            ScheduledWork(
                work_date=start + timedelta(days=1),
                employee_id=s.wb.id,
                original_employee_id=s.wa.id,
                job_item_id=s.item_u.id,
                worksite_id=s.site_u.id,
                assigned_hours=Decimal("8.0"),
                status="ACTIVE",
            )
        )
        await session.commit()

    async def gaps(days: int) -> tuple[list[dict], int]:
        url = (
            f"/api/v1/staffing-gaps?from_date={start.isoformat()}"
            f"&to_date={(start + timedelta(days=days - 1)).isoformat()}"
        )
        with captured_sql() as statements:
            resp = await client.get(url, headers=_h(s.admin_token))
        assert resp.status_code == 200, resp.text
        mine = [g for g in resp.json()["gaps"] if g["original_employee_id"] == str(s.wa.id)]
        return mine, len(statements)

    short, short_queries = await gaps(3)
    long, long_queries = await gaps(14)
    assert [g["work_date"] for g in short] == [
        start.isoformat(),
        (start + timedelta(days=2)).isoformat(),
    ]
    assert len(long) == 13  # 14 leave days, one covered
    assert short_queries == long_queries


# --------------------------------------------------------------------------------- gzip
def _gzip_app() -> FastAPI:
    """A tiny app with the production GZip settings, one route per kind of response."""
    app = FastAPI()
    app.add_middleware(
        GZipMiddleware,
        minimum_size=GZIP_MINIMUM_SIZE,
        compresslevel=6,
        exclude_content_types=GZIP_EXCLUDED_CONTENT_TYPES,
    )
    big = "x" * 5000

    @app.get("/big")
    async def big_json() -> JSONResponse:
        return JSONResponse({"data": big})

    @app.get("/small")
    async def small_json() -> JSONResponse:
        return JSONResponse({"data": "x" * 900})

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def events():
            yield f"data: {big}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/xlsx")
    async def xlsx() -> Response:
        return Response(
            big.encode(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    return app


async def test_gzip_only_for_large_compressible_responses() -> None:
    headers = {"Accept-Encoding": "gzip"}
    async with AsyncClient(
        transport=ASGITransport(app=_gzip_app()), base_url="http://test"
    ) as client:
        big = await client.get("/big", headers=headers)
        assert big.headers.get("content-encoding") == "gzip"
        assert big.json()["data"] == "x" * 5000  # still readable
        for path in ("/small", "/stream", "/xlsx"):
            resp = await client.get(path, headers=headers)
            assert "content-encoding" not in resp.headers, path


def test_the_app_installs_gzip_with_these_settings() -> None:
    app = create_app()
    gzip = [m for m in app.user_middleware if m.cls is GZipMiddleware]
    assert len(gzip) == 1
    assert gzip[0].kwargs["minimum_size"] == 1024
    excluded = gzip[0].kwargs["exclude_content_types"]
    assert isinstance(excluded, tuple) and "text/event-stream" in excluded
