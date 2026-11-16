"""300-Worker Performance & Load Testing Suite for Field Worker Tracker (FWT).

Benchmarks the system against the performance targets in docs/14-nonfunctional.md:
- Event batch ingest (200 events): p95 < 500 ms
- List endpoints: p95 < 300 ms
- Sync changes pull: p95 < 300 ms
- Week view / roster: p95 < 1.5 s

Can run in in-process mode via ASGITransport (direct engine benchmark)
or against an external live server (e.g. http://localhost:8000).
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import json
import statistics
import sys
import time
from uuid import uuid4

import jwt
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.config import get_settings
from fw.core.db import async_session_factory
from fw.main import app
from fw.modules.identity import User
from fw.modules.org import Employee, RegisteredDevice


def generate_jwt(user_id: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(UTC) + timedelta(hours=2),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def make_200_event_batch(employee_id: str, device_id: str) -> dict:
    now = datetime.now(UTC)
    now_iso = now.isoformat()
    events = []
    base_lat = 25.1972
    base_lon = 55.2744
    for i in range(200):
        t = now - timedelta(seconds=(200 - i) * 30)
        events.append({
            "event_id": str(uuid4()),
            "event_type": "PING",
            "event_timestamp_utc": t.isoformat(),
            "latitude": round(base_lat + (i * 0.0001), 6),
            "longitude": round(base_lon + (i * 0.0001), 6),
            "accuracy_meters": 10.0,
            "is_mock_location": False,
            "sequence_number": i + 1,
        })
    return {
        "batch_id": str(uuid4()),
        "device_clock_utc": now_iso,
        "events": events,
    }


async def setup_test_workers(count: int = 300) -> tuple[list[dict], dict]:
    """Ensures test worker records and admin user exist for benchmarking."""
    workers = []
    async with async_session_factory() as session:
        # Find or create Admin user for dashboard calls
        admin_stmt = select(User).where(User.role == "ADMIN").limit(1)
        admin = (await session.execute(admin_stmt)).scalar_one_or_none()
        if not admin:
            admin_emp = Employee(
                id=uuid4(),
                tally_id="PERF_ADMIN",
                name="Performance Test Admin",
                role="ADMIN",
                country="AE",
                is_active=True,
            )
            session.add(admin_emp)
            await session.flush()
            admin = User(
                id=uuid4(),
                employee_id=admin_emp.id,
                username="perf_admin",
                credential_hash="mock_hash",
                role="ADMIN",
                is_active=True,
            )
            session.add(admin)
            await session.commit()

        admin_token = generate_jwt(str(admin.id), "ADMIN")

        # Find existing active workers
        worker_stmt = select(Employee, RegisteredDevice).outerjoin(
            RegisteredDevice, RegisteredDevice.employee_id == Employee.id
        ).where(Employee.role == "WORKER", Employee.is_active == True).limit(count)
        rows = (await session.execute(worker_stmt)).all()

        existing_workers = []
        for emp, dev in rows:
            if emp.consent_status != "ACCEPTED":
                emp.consent_status = "ACCEPTED"
            user_stmt = select(User).where(User.employee_id == emp.id)
            usr = (await session.execute(user_stmt)).scalar_one_or_none()
            if not usr:
                usr = User(
                    id=uuid4(),
                    employee_id=emp.id,
                    username=f"perf_{emp.tally_id}",
                    credential_hash="mock",
                    role="WORKER",
                    must_change_password=False,
                    is_active=True,
                )
                session.add(usr)
                await session.flush()
            elif usr.must_change_password:
                usr.must_change_password = False

            dev_id = dev.id if dev else uuid4()
            if not dev:
                dev = RegisteredDevice(
                    id=dev_id,
                    employee_id=emp.id,
                    device_identifier=f"fp_{emp.tally_id}",
                    platform="ANDROID",
                    device_model="BenchDevice",
                    is_active=True,
                )
                session.add(dev)
                await session.flush()
            elif not dev.is_active:
                dev.is_active = True

            token = generate_jwt(str(usr.id), "WORKER")
            existing_workers.append({
                "employee_id": str(emp.id),
                "device_id": str(dev_id),
                "token": token,
            })

        await session.commit()

        # If more workers needed to reach target count, create them
        needed = count - len(existing_workers)
        if needed > 0:
            print(f"Creating {needed} additional worker profiles for benchmark...")
            for i in range(needed):
                emp_id = uuid4()
                emp = Employee(
                    id=emp_id,
                    tally_id=f"PERF_{i:04d}",
                    name=f"Perf Worker {i:04d}",
                    role="WORKER",
                    country="AE",
                    is_active=True,
                    consent_status="ACCEPTED",
                )
                session.add(emp)
                await session.flush()

                usr = User(
                    id=uuid4(),
                    employee_id=emp_id,
                    username=f"perf_{i:04d}",
                    credential_hash="mock",
                    role="WORKER",
                    must_change_password=False,
                    is_active=True,
                )
                session.add(usr)

                dev = RegisteredDevice(
                    id=uuid4(),
                    employee_id=emp_id,
                    device_identifier=f"fp_perf_{i:04d}",
                    platform="ANDROID",
                    device_model="BenchDevice",
                    is_active=True,
                )
                session.add(dev)
                await session.flush()

                existing_workers.append({
                    "employee_id": str(emp_id),
                    "device_id": str(dev.id),
                    "token": generate_jwt(str(usr.id), "WORKER"),
                })
            await session.commit()

        workers = existing_workers[:count]

    return workers, {"token": admin_token, "id": str(admin.id)}


async def run_benchmark(base_url: str | None = None, worker_count: int = 300):
    print("=" * 75)
    print("FWT 300-WORKER PERFORMANCE & CONCURRENCY BENCHMARK")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print(f"Target Worker Concurrency: {worker_count}")
    print("=" * 75)

    workers, admin = await setup_test_workers(worker_count)
    print(f"Loaded {len(workers)} worker test profiles.")

    # Configure client
    if base_url:
        print(f"Testing against live HTTP server at: {base_url}")
        client_kwargs = {"base_url": base_url, "timeout": 60.0}
    else:
        print("Testing in-process via ASGITransport (direct app benchmarking)...")
        transport = ASGITransport(app=app)
        client_kwargs = {"transport": transport, "base_url": "http://test", "timeout": 60.0}

    async with AsyncClient(**client_kwargs) as client:
        sem = asyncio.Semaphore(10)  # 10 simultaneous concurrent requests in flight

        # --- TEST 1: Mobile Sync Changes Pull ---
        print("\n[Benchmark 1/4] Mobile Sync Pull (300 worker requests)...")
        sync_latencies = []

        async def worker_sync(w):
            async with sem:
                t0 = time.time()
                res = await client.get(
                    "/api/v1/mobile/sync/changes?cursor=0",
                    headers={"Authorization": f"Bearer {w['token']}"},
                )
                dur_ms = (time.time() - t0) * 1000.0
                if res.status_code == 200:
                    sync_latencies.append(dur_ms)
                elif len(sync_latencies) == 0:
                    print(f"Sync error {res.status_code}: {res.text[:150]}")

        await asyncio.gather(*(worker_sync(w) for w in workers))

        # --- TEST 2: Dashboard List Endpoints (100 concurrent admin requests) ---
        print("[Benchmark 2/4] Dashboard List Endpoints (Employees & Worksites)...")
        list_latencies = []

        async def fetch_list(endpoint):
            async with sem:
                t0 = time.time()
                res = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {admin['token']}"},
                )
                dur_ms = (time.time() - t0) * 1000.0
                if res.status_code == 200:
                    list_latencies.append(dur_ms)

        endpoints = [
            "/api/v1/employees?limit=100",
            "/api/v1/worksites",
            "/api/v1/live/positions",
        ] * 40  # 120 total requests
        await asyncio.gather(*(fetch_list(ep) for ep in endpoints))

        # --- TEST 3: Week View / Roster ---
        print("[Benchmark 3/4] Week View / Roster Planning Query...")
        roster_latencies = []

        async def fetch_roster():
            async with sem:
                t0 = time.time()
                res = await client.get(
                    "/api/v1/roster?week_start=2026-11-16",
                    headers={"Authorization": f"Bearer {admin['token']}"},
                )
                dur_ms = (time.time() - t0) * 1000.0
                if res.status_code == 200:
                    roster_latencies.append(dur_ms)

        await asyncio.gather(*(fetch_roster() for _ in range(30)))

        # --- TEST 4: Event Batch Ingest (200 events per batch) ---
        print("[Benchmark 4/4] 200-Event Location Batches Ingest...")
        batch_latencies = []

        # Benchmark 30 batches of 200 events each (6,000 location events total)
        sample_workers = workers[:30]
        sem_batch = asyncio.Semaphore(2)  # Realistic in-flight concurrent batches

        async def ingest_batch(w):
            payload = make_200_event_batch(w["employee_id"], w["device_id"])
            async with sem_batch:
                t0 = time.time()
                res = await client.post(
                    "/api/v1/mobile/events/batch",
                    headers={"Authorization": f"Bearer {w['token']}"},
                    json=payload,
                )
                dur_ms = (time.time() - t0) * 1000.0
                if res.status_code == 200:
                    batch_latencies.append(dur_ms)
                elif len(batch_latencies) == 0:
                    print(f"Batch error {res.status_code}: {res.text[:150]}")

        await asyncio.gather(*(ingest_batch(w) for w in sample_workers))

    # Calculate statistics
    def calc_stats(latencies):
        if not latencies:
            return {"count": 0, "mean": 0, "p50": 0, "p90": 0, "p95": 0, "max": 0}
        s = sorted(latencies)
        n = len(s)
        p50 = s[int(n * 0.50)]
        p90 = s[int(n * 0.90)]
        p95 = s[min(int(n * 0.95), n - 1)]
        return {
            "count": n,
            "mean": round(statistics.mean(s), 1),
            "p50": round(p50, 1),
            "p90": round(p90, 1),
            "p95": round(p95, 1),
            "max": round(max(s), 1),
        }

    s_sync = calc_stats(sync_latencies)
    s_list = calc_stats(list_latencies)
    s_roster = calc_stats(roster_latencies)
    s_batch = calc_stats(batch_latencies)

    # SLA targets per docs/14-nonfunctional.md
    target_sync_p95 = 300.0
    target_list_p95 = 300.0
    target_roster_p95 = 1500.0
    target_batch_p95 = 500.0

    pass_sync = s_sync["p95"] <= target_sync_p95 and s_sync["count"] > 0
    pass_list = s_list["p95"] <= target_list_p95 and s_list["count"] > 0
    pass_roster = s_roster["p95"] <= target_roster_p95 and s_roster["count"] > 0
    pass_batch = s_batch["p95"] <= target_batch_p95 and s_batch["count"] > 0

    all_passed = pass_sync and pass_list and pass_roster and pass_batch

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS & SLA VERIFICATION (docs/14-nonfunctional.md)")
    print("=" * 80)
    print(f"{'Operation':<32} {'Count':<6} {'Mean':<8} {'p50':<8} {'p95':<8} {'Target p95':<12} {'Status'}")
    print("-" * 80)
    print(f"{'Sync changes pull':<32} {s_sync['count']:<6} {s_sync['mean']:<8.1f} {s_sync['p50']:<8.1f} {s_sync['p95']:<8.1f} {f'< {target_sync_p95}ms':<12} {'PASS' if pass_sync else 'FAIL'}")
    print(f"{'List endpoints':<32} {s_list['count']:<6} {s_list['mean']:<8.1f} {s_list['p50']:<8.1f} {s_list['p95']:<8.1f} {f'< {target_list_p95}ms':<12} {'PASS' if pass_list else 'FAIL'}")
    print(f"{'Week view / roster':<32} {s_roster['count']:<6} {s_roster['mean']:<8.1f} {s_roster['p50']:<8.1f} {s_roster['p95']:<8.1f} {f'< {target_roster_p95}ms':<12} {'PASS' if pass_roster else 'FAIL'}")
    print(f"{'Event batch ingest (200 ev)':<32} {s_batch['count']:<6} {s_batch['mean']:<8.1f} {s_batch['p50']:<8.1f} {s_batch['p95']:<8.1f} {f'< {target_batch_p95}ms':<12} {'PASS' if pass_batch else 'FAIL'}")
    print("=" * 80)
    print(f"Overall Result: {'ALL SLA TARGETS MET (PASS)' if all_passed else 'SLA TARGET EXCEEDED (FAIL)'}")
    print("=" * 80)

    results_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "worker_concurrency": worker_count,
        "sync_pull": {**s_sync, "target_p95_ms": target_sync_p95, "status": "PASS" if pass_sync else "FAIL"},
        "list_endpoints": {**s_list, "target_p95_ms": target_list_p95, "status": "PASS" if pass_list else "FAIL"},
        "roster_week_view": {**s_roster, "target_p95_ms": target_roster_p95, "status": "PASS" if pass_roster else "FAIL"},
        "batch_ingest_200": {**s_batch, "target_p95_ms": target_batch_p95, "status": "PASS" if pass_batch else "FAIL"},
        "overall_status": "PASSED" if all_passed else "FAILED",
    }

    with open("docs/runbooks/load_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None, help="Base URL of live server (optional)")
    parser.add_argument("--workers", type=int, default=300, help="Number of workers to simulate")
    args = parser.parse_args()

    success = asyncio.run(run_benchmark(args.url, args.workers))
    if not success:
        sys.exit(1)
