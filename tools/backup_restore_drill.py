"""Backup and Restore Drill Tool for Field Worker Tracker (FWT).

Verifies quarterly disaster recovery preparedness per:
- docs/14-nonfunctional.md (Section 5: RTO <= 4h, RPO <= 15min)
- docs/phases/PHASE-13-hardening-and-go-live.md (Checklist: Restore drill completed and recorded)
- ADR-022

Procedure:
1. Dumps the primary database (fw_db) using pg_dump.
2. Creates an isolated scratch database (fw_scratch).
3. Restores the backup image into fw_scratch.
4. Performs comprehensive integrity and parity checks:
   - Row count parity across key domain tables.
   - PostGIS geometry validity checks (ST_IsValid on boundaries).
   - Alembic migration version parity.
5. Measures and evaluates Recovery Time Objective (RTO) against the 4-hour SLA.
6. Cleans up the scratch database and logs results.
"""

import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def compute_file_sha256(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def main():
    print("=" * 70)
    print("FWT DISASTER RECOVERY & BACKUP RESTORE DRILL")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print("=" * 70)

    container_name = "field-worker-tracker-db-1"
    dump_filename = "/tmp/fw_db_drill_backup.sql"
    scratch_db = "fw_scratch"
    source_db = "fw_db"

    # Verify docker container is running
    rc, out, err = run_cmd(["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"])
    if rc != 0 or container_name not in out:
        print(f"ERROR: Database container '{container_name}' is not running.")
        sys.exit(1)

    print(f"[1/5] Creating full logical backup of '{source_db}'...")
    start_backup_time = time.time()
    rc, out, err = run_cmd([
        "docker", "exec", container_name,
        "pg_dump", "-U", "postgres", "-d", source_db,
        "--clean", "--if-exists", "-f", dump_filename
    ])
    backup_duration = time.time() - start_backup_time
    if rc != 0:
        print(f"ERROR: pg_dump failed: {err}")
        sys.exit(1)

    # Inspect backup size
    rc, out, _ = run_cmd(["docker", "exec", container_name, "stat", "-c", "%s", dump_filename])
    backup_size_bytes = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0
    print(f"  Backup created successfully in {backup_duration:.2f}s (size: {backup_size_bytes / 1024:.1f} KB).")

    print(f"[2/5] Initializing scratch recovery database '{scratch_db}'...")
    # Drop existing scratch if present
    run_cmd(["docker", "exec", container_name, "psql", "-U", "postgres", "-c", f"DROP DATABASE IF EXISTS {scratch_db};"])
    # Create new scratch DB
    rc, out, err = run_cmd(["docker", "exec", container_name, "psql", "-U", "postgres", "-c", f"CREATE DATABASE {scratch_db} OWNER postgres;"])
    if rc != 0:
        print(f"ERROR: Failed to create scratch database: {err}")
        sys.exit(1)

    print(f"[3/5] Restoring backup into '{scratch_db}' (Testing RTO)...")
    start_restore_time = time.time()
    rc, out, err = run_cmd([
        "docker", "exec", container_name,
        "psql", "-U", "postgres", "-d", scratch_db, "-f", dump_filename
    ])
    restore_duration = time.time() - start_restore_time
    print(f"  Restore operation completed in {restore_duration:.2f} seconds.")

    print("[4/5] Running database parity & integrity verification checks...")
    tables_to_verify = [
        "employees",
        "worksites",
        "accommodations",
        "mobile_event_logs",
        "attendance_records",
        "payroll_runs",
        "audit_logs",
        "archive_records",
        "users",
    ]

    parity_results = {}
    all_passed = True

    for tbl in tables_to_verify:
        # Check source count
        rc_src, out_src, _ = run_cmd([
            "docker", "exec", container_name,
            "psql", "-U", "postgres", "-d", source_db, "-tAc", f"SELECT count(*) FROM {tbl};"
        ])
        # Check restored count
        rc_dst, out_dst, _ = run_cmd([
            "docker", "exec", container_name,
            "psql", "-U", "postgres", "-d", scratch_db, "-tAc", f"SELECT count(*) FROM {tbl};"
        ])

        if rc_src == 0 and rc_dst == 0:
            src_cnt = int(out_src.strip())
            dst_cnt = int(out_dst.strip())
            match = (src_cnt == dst_cnt)
            parity_results[tbl] = {"source": src_cnt, "restored": dst_cnt, "match": match}
            if not match:
                all_passed = False
            status_str = "MATCH" if match else "MISMATCH"
            print(f"  - Table '{tbl}': Source={src_cnt}, Restored={dst_cnt} -> [{status_str}]")
        else:
            print(f"  - Table '{tbl}': query failed (src_rc={rc_src}, dst_rc={rc_dst})")
            all_passed = False

    # Check PostGIS spatial geometries validity
    rc_geom, out_geom, _ = run_cmd([
        "docker", "exec", container_name,
        "psql", "-U", "postgres", "-d", scratch_db, "-tAc",
        "SELECT count(*) FROM worksites WHERE boundary IS NOT NULL AND NOT ST_IsValid(boundary);"
    ])
    invalid_geoms = int(out_geom.strip()) if rc_geom == 0 and out_geom.strip().isdigit() else -1
    geom_passed = (invalid_geoms == 0)
    print(f"  - PostGIS Geometry Validation (Invalid boundaries): {invalid_geoms} -> [{'PASS' if geom_passed else 'FAIL'}]")

    # Check Alembic version parity
    rc_v_src, out_v_src, _ = run_cmd([
        "docker", "exec", container_name,
        "psql", "-U", "postgres", "-d", source_db, "-tAc", "SELECT version_num FROM alembic_version;"
    ])
    rc_v_dst, out_v_dst, _ = run_cmd([
        "docker", "exec", container_name,
        "psql", "-U", "postgres", "-d", scratch_db, "-tAc", "SELECT version_num FROM alembic_version;"
    ])
    alembic_passed = (out_v_src.strip() == out_v_dst.strip())
    print(f"  - Alembic Schema Version: Source={out_v_src.strip()}, Restored={out_v_dst.strip()} -> [{'PASS' if alembic_passed else 'FAIL'}]")

    print(f"[5/5] Cleaning up scratch database '{scratch_db}' and dump artifacts...")
    run_cmd(["docker", "exec", container_name, "psql", "-U", "postgres", "-c", f"DROP DATABASE {scratch_db};"])
    run_cmd(["docker", "exec", container_name, "rm", "-f", dump_filename])
    print("  Scratch database and dump files cleaned up.")

    rto_target_seconds = 4 * 3600  # 4 hours per docs/14-nonfunctional.md
    rto_passed = restore_duration <= rto_target_seconds

    overall_success = all_passed and geom_passed and alembic_passed and rto_passed

    print("\n" + "=" * 70)
    print("RESTORE DRILL VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Backup Duration:        {backup_duration:.2f} seconds")
    print(f"Restore Duration (RTO): {restore_duration:.2f} seconds (SLA Target: < 14400.0s / 4 hours) -> [{'PASS' if rto_passed else 'FAIL'}]")
    print(f"Data Parity Status:     {'PASS (100% matched)' if all_passed else 'FAIL'}")
    print(f"Spatial Integrity:      {'PASS' if geom_passed else 'FAIL'}")
    print(f"Schema Parity:          {'PASS' if alembic_passed else 'FAIL'}")
    print(f"Overall Result:         {'SUCCESSFUL' if overall_success else 'FAILED'}")
    print("=" * 70)

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "backup_duration_seconds": round(backup_duration, 2),
        "restore_duration_seconds": round(restore_duration, 2),
        "rto_target_seconds": rto_target_seconds,
        "rto_met": rto_passed,
        "backup_size_bytes": backup_size_bytes,
        "tables_verified": parity_results,
        "invalid_geometries": invalid_geoms,
        "alembic_version": out_v_dst.strip(),
        "overall_status": "PASSED" if overall_success else "FAILED",
    }

    with open("docs/runbooks/restore_drill_record.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if not overall_success:
        sys.exit(1)


if __name__ == "__main__":
    main()

