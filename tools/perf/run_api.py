"""Start the API on the local fw_perf database with request timing on (Batch 9 step 1).

    uv run --directory backend python ../tools/perf/run_api.py > backend/storage/perf/api-timing.log

One worker, no reload, port 8000 (where ``vite preview`` proxies /api), or ``FW_PERF_API_PORT``
when 8000 is busy with another API (then point the preview's proxy there). Every request writes a
``request_timing`` log line (route template, status, duration, queries, DB time, repeats, slow
SQL without values). Refuses to start when port 8000 is taken, so the preview can never reach a
server on another database.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import perf_db  # noqa: E402

PORT = int(os.environ.get("FW_PERF_API_PORT", "8000"))


def main() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            sys.exit(f"Port {PORT} is in use (another API?). Stop it first; the preview proxies /api there.")
    perf_db.point_at_perf_database()
    os.environ["PERF_TIMING_ENABLED"] = "true"
    os.environ.setdefault("LOG_LEVEL", "INFO")
    import uvicorn

    uvicorn.run("fw.main:app", host="127.0.0.1", port=PORT, workers=1, reload=False, access_log=False)


if __name__ == "__main__":
    main()
