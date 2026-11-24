"""The measuring tools (tools/perf, Batch 9 step 1): safety rules, safe output, mock dataset.

No browser and no network: the scripts' pure helpers and an httpx MockTransport.
"""

import importlib.util
import json
import sys
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

import fw.main  # noqa: F401  (registers every model; conftest's autouse fixtures use the ORM)

TOOLS = Path(__file__).resolve().parents[2] / "tools" / "perf"


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = _load("perf_common")
dataset = _load("perf_dataset")
perf_db = _load("perf_db")


def test_read_only_sends_only_reads_and_the_login() -> None:
    for method in ("GET", "HEAD", "OPTIONS"):
        assert common.allowed(method, "/api/v1/worksites", read_only=True)
    assert common.allowed("POST", "/api/v1/auth/login", read_only=True)
    for method in ("POST", "PATCH", "PUT", "DELETE"):
        assert not common.allowed(method, "/api/v1/worksites", read_only=True)
    assert not common.allowed("POST", "/api/v1/live/stream-ticket", read_only=True)
    assert common.allowed("POST", "/api/v1/worksites", read_only=False)


def test_non_local_url_needs_read_only() -> None:
    with pytest.raises(common.Refused):
        common.check_target(["https://example.onrender.com"], read_only=False)
    common.check_target(["https://example.onrender.com"], read_only=True)
    common.check_target(["http://localhost:4173", "http://127.0.0.1:8000"], read_only=False)


def test_client_blocks_writes_before_sending_and_lists_them() -> None:
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(f"{request.method} {request.url.path}")
        return httpx.Response(200, json={"ok": True})

    client = common.ReadOnlyClient(
        "https://example.invalid", read_only=True, transport=httpx.MockTransport(handler)
    )
    assert client.request("GET", "/api/v1/worksites") is not None
    assert (
        client.request("DELETE", "/api/v1/worksites/0b5c1f8e-1d2a-4c3b-9e8f-7a6b5c4d3e2f") is None
    )
    assert client.request("POST", "/api/v1/reports/x/export") is None
    assert sent == ["GET /api/v1/worksites"]
    assert client.skipped == [
        {"method": "DELETE", "path": "/api/v1/worksites/{id}", "reason": "read-only"},
        {"method": "POST", "path": "/api/v1/reports/x/export", "reason": "read-only"},
    ]


def test_credentials_only_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FW_PERF_USER", raising=False)
    monkeypatch.delenv("FW_PERF_PASSWORD", raising=False)
    with pytest.raises(common.Refused):
        common.credentials()
    monkeypatch.setenv("FW_PERF_USER", "u")
    monkeypatch.setenv("FW_PERF_PASSWORD", "p")
    assert common.credentials() == ("u", "p")


def test_output_never_holds_a_credential(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        common.write_json(tmp_path / "x.json", {"note": "pw=S3cret-value"}, ["S3cret-value"])
    assert not (tmp_path / "x.json").exists()


def test_run_details_record_host_region_network_and_zoned_time() -> None:
    d = common.run_details(
        "https://web.example.com",
        "https://api.example.com",
        "Singapore",
        "home broadband Kerala",
        True,
    )
    assert d["host"] == "web.example.com" and d["api_host"] == "api.example.com"
    assert d["region"] == "Singapore" and d["network"] == "home broadband Kerala"
    assert datetime.fromisoformat(d["started_at"]).tzinfo is not None
    assert d["read_only"] is True


def test_server_timing_and_safe_paths() -> None:
    t = common.parse_server_timing(
        'app;dur=123.4;desc="app", db;dur=45.6;desc="18 queries", dbrepeat;desc="6 max repeats"'
    )
    assert t == {"server_ms": 123.4, "db_ms": 45.6, "db_queries": 18, "repeated_max": 6}
    url = "https://h/api/v1/worksites/0b5c1f8e-1d2a-4c3b-9e8f-7a6b5c4d3e2f?search=x"
    assert common.safe_path(url) == "/api/v1/worksites/{id}"


def test_measure_api_read_only_runs_no_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measure_api = _load("measure_api")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "tok-123", "user": {}})
        return httpx.Response(200, json=[], headers={"server-timing": 'app;dur=5.0;desc="app"'})

    class MockClient(common.ReadOnlyClient):
        def __init__(self, api_url: str, read_only: bool, **_: Any) -> None:
            super().__init__(api_url, read_only, transport=httpx.MockTransport(handler))

    replay = tmp_path / "replay.json"
    replay.write_text(json.dumps({"worksites": ["/api/v1/worksites"]}), encoding="utf-8")
    out = tmp_path / "api.json"
    monkeypatch.setattr(measure_api, "ReadOnlyClient", MockClient)
    monkeypatch.setattr(measure_api, "REPLAY_DIR", tmp_path)  # its progress file
    monkeypatch.setattr(measure_api, "wait_until_awake", lambda *_a, **_k: 0.0)
    monkeypatch.setenv("FW_PERF_USER", "perf-user")
    monkeypatch.setenv("FW_PERF_PASSWORD", "perf-secret-pw")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "measure_api.py",
            "--api-url",
            "https://api.example.com",
            "--read-only",
            "--region",
            "Singapore",
            "--network",
            "home broadband Kerala",
            "--replay",
            str(replay),
            "--out",
            str(out),
            "--samples",
            "2",
        ],
    )
    measure_api.main()

    assert not any("/api/v1/reports" in s for s in seen)
    assert all(s.startswith("GET ") or s == "POST /api/v1/auth/login" for s in seen)
    text = out.read_text(encoding="utf-8")
    data = json.loads(text)
    assert "perf-secret-pw" not in text and "tok-123" not in text
    assert data["run"]["host"] == "api.example.com" and data["run"]["region"] == "Singapore"
    assert data["run"]["network"] == "home broadband Kerala" and data["run"]["read_only"] is True
    assert "heaviest_report" not in data and "reports_survey" not in data
    assert data["endpoints"][0]["path"] == "/api/v1/worksites"


def test_measure_api_refuses_remote_without_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    measure_api = _load("measure_api")
    monkeypatch.setenv("FW_PERF_USER", "u")
    monkeypatch.setenv("FW_PERF_PASSWORD", "p")
    monkeypatch.setattr(sys, "argv", ["measure_api.py", "--api-url", "https://api.example.com"])
    with pytest.raises(common.Refused):
        measure_api.main()


def test_perf_database_guard() -> None:
    local = {"DATABASE_URL": "postgresql+asyncpg://a:b@localhost:5432/fw_db"}
    assert perf_db.problems("fw_perf", local, "local") == []
    assert perf_db.problems("fw_db", local, "local")
    assert perf_db.problems("fw_test", local, "local")
    remote = {"DATABASE_URL": "postgresql+asyncpg://a:b@db.example.com:5432/fw_db"}
    assert perf_db.problems("fw_perf", remote, "local")
    assert perf_db.problems("fw_perf", local, "production")


def test_mock_dataset_is_deterministic_and_mock_only() -> None:
    scale = dataset.Scale().scaled(0.05)
    a = dataset.build_dataset(scale, seed=7, history_start=date(2026, 9, 1))
    b = dataset.build_dataset(scale, seed=7, history_start=date(2026, 9, 1))
    assert [(s.lon, s.lat, s.budget) for s in a.sites] == [
        (s.lon, s.lat, s.budget) for s in b.sites
    ]
    assert a.leave_weeks == b.leave_weeks
    assert len(a.sites) == scale.worksites and len(a.items) == scale.job_items
    assert len(a.employees) == scale.employees
    assert all(
        e.name.startswith(("Perf Worker", "Perf Supervisor", "Perf Engineer")) for e in a.employees
    )
    assert all(e.tally_id.startswith("PF") for e in a.employees)
    # Every worker has work on all six working days and never on the weekly off (Friday).
    for w in a.workers:
        days = [d for x in a.assignments if x.employee_index == w.index for d in x.weekdays]
        assert sorted(days) == sorted(dataset.SIX_DAYS)
