"""The committed demo workbook (mock people only) must preview against the current template with 0 errors."""

from collections import Counter
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from fw.core.db import async_session_factory
from fw.main import create_app
from tests.test_batch6_features import db_required, get_admin_user_and_token

DEMO = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "demo_data"
    / "FieldWorkerTracker_Demo_Import.xlsx"
)

pytestmark = [db_required, pytest.mark.asyncio]


async def test_demo_workbook_previews_without_errors() -> None:
    assert DEMO.exists(), f"missing {DEMO}"
    async with async_session_factory() as session:
        _, token = await get_admin_user_and_token(session)
    headers = {"Authorization": f"Bearer {token}"}
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {
            "file": (
                DEMO.name,
                DEMO.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        resp = await client.post("/api/v1/imports", headers=headers, files=files)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        if body["summary"]["counts"].get("ERROR", 0):
            preview = await client.get(
                f"/api/v1/imports/{body['batch_id']}/preview?status=ERROR&limit=500",
                headers=headers,
            )
            codes = Counter(
                (r["sheet"], code)
                for r in preview.json()["rows"]
                if r["status"] == "ERROR"
                for code in r["codes"]
            )
            pytest.fail(f"demo workbook has import errors: {dict(codes)}")
        assert body["can_commit"] is True
        # Every data sheet in the demo is recognised (nothing silently skipped as unknown).
        per_sheet = body["summary"].get("sheet_counts", {})
        assert per_sheet.get("Worksite_Supervisors", {}).get("total", 0) > 0
