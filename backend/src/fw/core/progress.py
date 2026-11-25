"""Progress reporting for long operations (Batch 9 step 4).

A background job sets a reporter for the code it runs; that code calls ``report_progress``
without knowing whether it runs in a job. Outside a job the calls do nothing.

    await report_progress("employees", done=120, total=580)

``yield_to_loop`` lets other requests run during long CPU-bound loops in the API process.
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from sqlalchemy import Executable
from sqlalchemy.ext.asyncio import AsyncSession

ProgressReporter = Callable[[str, int, int], Awaitable[None]]

_reporter: ContextVar[ProgressReporter | None] = ContextVar("fw_progress_reporter", default=None)


def set_progress_reporter(reporter: ProgressReporter | None) -> object:
    """Install a reporter for the current task; returns a token for ``reset_progress_reporter``."""
    return _reporter.set(reporter)


def reset_progress_reporter(token: object) -> None:
    _reporter.reset(token)  # type: ignore[arg-type]


async def report_progress(phase: str, done: int, total: int) -> None:
    """Tell the running job how far it is (a no-op outside a job)."""
    reporter = _reporter.get()
    if reporter is not None:
        await reporter(phase, done, total)


async def yield_to_loop() -> None:
    """Give the event loop a turn, so other requests are not held up by a long loop."""
    await asyncio.sleep(0)


async def fetch_rows_in_parts(
    session: AsyncSession, stmt: Executable, part_size: int = 1000
) -> list[Any]:
    """``(await session.execute(stmt)).all()`` read through a server-side cursor in parts of
    ``part_size`` rows, with a turn for other requests after each part.

    Turning 14,000 rows (or ORM objects) into Python holds the event loop for 0.3-1 s in one
    block; in parts, for a few tens of milliseconds at a time. Same rows, same order.
    """
    result = await session.stream(stmt.execution_options(yield_per=part_size))
    rows: list[Any] = []
    async for part in result.partitions(part_size):
        rows.extend(part)
        await asyncio.sleep(0)
    return rows


async def yield_every(i: int, every: int = 1000, skip_first: int = 1) -> None:
    """Yield on every ``every``-th pass of a loop (``i`` counts from 0; pass 0 is skipped).

    A report builds about 1,000 rows in 30-50 ms, so other requests wait at most that long.
    """
    if i >= skip_first and i % every == 0:
        await asyncio.sleep(0)
