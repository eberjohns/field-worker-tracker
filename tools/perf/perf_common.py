"""Shared rules for the measuring scripts (Batch 9 step 1): safety, run details and safe output.

Owner's rules for measuring a deployed site (24 Nov 2026):
- A non-local URL needs ``--read-only``. In read-only mode only GET/HEAD/OPTIONS requests are sent,
  plus the login POST; anything else is blocked before it is sent and listed as skipped.
- Credentials come only from FW_PERF_USER / FW_PERF_PASSWORD and are never written anywhere.
- Every output records the host, region, network and start time (with time zone).
"""

from __future__ import annotations

import json
import os
import platform
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
LOGIN_PATH = "/api/v1/auth/login"
USER_ENV = "FW_PERF_USER"
PASSWORD_ENV = "FW_PERF_PASSWORD"
ROOT = Path(__file__).resolve().parents[2]
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_TIMING = re.compile(r"(\w+);dur=([\d.]+)(?:;desc=\"([^\"]*)\")?|(\w+);desc=\"([^\"]*)\"")


class Refused(SystemExit):
    """The run is not allowed (exits with the reason)."""


def is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in LOCAL_HOSTS


def check_target(urls: list[str], read_only: bool) -> None:
    """Refuse any non-local URL unless --read-only is given."""
    remote = [u for u in urls if u and not is_local(u)]
    if remote and not read_only:
        hosts = ", ".join(sorted({urlparse(u).hostname or u for u in remote}))
        raise Refused(f"Refused: {hosts} is not local; run with --read-only.")


def allowed(method: str, path: str, read_only: bool) -> bool:
    """Whether a request may be sent: everything locally, only reads (and the login) read-only."""
    if not read_only:
        return True
    method = method.upper()
    return method in READ_METHODS or (method == "POST" and path.rstrip("/") == LOGIN_PATH)


def credentials() -> tuple[str, str]:
    """From the environment only, never from flags or files."""
    user, password = os.environ.get(USER_ENV), os.environ.get(PASSWORD_ENV)
    if not user or not password:
        raise Refused(f"Set {USER_ENV} and {PASSWORD_ENV} (the login is read from them only).")
    return user, password


def safe_path(url: str) -> str:
    """The URL path without host and query, with ids replaced: safe to commit or paste."""
    path = urlparse(url).path or "/"
    return _UUID.sub("{id}", path)


def parse_server_timing(header: str | None) -> dict[str, float | int]:
    """``app;dur=12.3;desc="app", db;dur=4.5;desc="18 queries", dbrepeat;desc="6 max repeats"``."""
    out: dict[str, float | int] = {}
    if not header:
        return out
    for m in _TIMING.finditer(header):
        name, dur, desc = m.group(1) or m.group(4), m.group(2), m.group(3) or m.group(5) or ""
        if name == "app" and dur:
            out["server_ms"] = float(dur)
        elif name == "db":
            if dur:
                out["db_ms"] = float(dur)
            n = re.match(r"(\d+)", desc)
            if n:
                out["db_queries"] = int(n.group(1))
        elif name == "dbrepeat":
            n = re.match(r"(\d+)", desc)
            if n:
                out["repeated_max"] = int(n.group(1))
    return out


def app_version() -> str:
    try:
        return str(json.loads((ROOT / "version.json").read_text(encoding="utf-8")).get("version"))
    except (OSError, ValueError):
        return "unknown"


def run_details(base_url: str, api_url: str, region: str, network: str, read_only: bool) -> dict[str, Any]:
    """What every output file records about the run (no machine name, no user)."""
    return {
        "host": urlparse(base_url).hostname,
        "api_host": urlparse(api_url).hostname,
        "region": region,
        "network": network,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "read_only": read_only,
        "client": f"{platform.system()} {platform.release()}, {os.cpu_count()} CPUs, Python {platform.python_version()}",
        "app_version": app_version(),
    }


def assert_no_secrets(data: Any, secrets: list[str]) -> None:
    text = json.dumps(data, default=str)
    for secret in secrets:
        if secret and secret in text:
            raise RuntimeError("Refusing to write output that contains a credential or token.")


def write_json(path: Path, data: Any, secrets: list[str]) -> None:
    assert_no_secrets(data, secrets)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


class ReadOnlyClient:
    """httpx client that refuses non-read requests in read-only mode and lists them as skipped."""

    def __init__(self, api_url: str, read_only: bool, timeout: float = 120.0, transport: Any = None) -> None:
        self.read_only = read_only
        self.skipped: list[dict[str, str]] = []
        self._client = httpx.Client(base_url=api_url, timeout=timeout, transport=transport)
        self.token: str | None = None

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response | None:
        if not allowed(method, path, self.read_only):
            self.skipped.append({"method": method.upper(), "path": safe_path(path), "reason": "read-only"})
            return None
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self._client.request(method, path, headers=headers, **kwargs)

    def login(self, user: str, password: str) -> dict[str, Any]:
        r = self.request("POST", LOGIN_PATH, json={"username": user, "password": password})
        if r is None or r.status_code != 200:
            raise Refused(f"Login failed ({None if r is None else r.status_code}).")
        data = r.json()
        self.token = data["access_token"]
        return data

    def close(self) -> None:
        self._client.close()


def wait_until_awake(api_url: str, limit_s: float = 300.0, fast_s: float = 2.0) -> float:
    """Poll /health until it answers in under ``fast_s`` (Render sleeps when idle). Returns waited s."""
    started = time.monotonic()
    with httpx.Client(timeout=60.0) as client:
        while True:
            t0 = time.monotonic()
            try:
                ok = client.get(api_url.rstrip("/") + "/health").status_code == 200
            except httpx.HTTPError:
                ok = False
            if ok and time.monotonic() - t0 < fast_s:
                return time.monotonic() - started
            if time.monotonic() - started > limit_s:
                raise Refused(f"{api_url} did not answer /health in under {fast_s} s within {limit_s:.0f} s.")
            time.sleep(5)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)
