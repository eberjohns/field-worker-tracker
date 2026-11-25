"""Background jobs: long operations run in the API process, with progress (Batch 9 step 4).

The request that starts a job gets it back at once (202) and the page polls
``GET /api/v1/background-jobs/{id}``. The work runs as an asyncio task in the same process: the
hosting may have no separate worker (docs/13-architecture.md), and the jobs we have take seconds,
not hours.

- The job's function gets its own session; the job commits it only when the function returns.
  A failure rolls everything back, as the old in-request call did.
- Progress goes through ``fw.core.progress``. It is written in a separate short session, at most
  every PROGRESS_WRITE_EVERY seconds, so the page sees it while the work's transaction is open.
- A heartbeat is written every HEARTBEAT_EVERY seconds. If the process stops (deploy, crash), the
  heartbeat stops too: a QUEUED or RUNNING job silent for HEARTBEAT_STALE_AFTER is stored as
  INTERRUPTED, and a new job with the same key may start.
"""

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import async_session_factory
from fw.core.errors import AppError, ProblemDetailsException
from fw.core.progress import reset_progress_reporter, set_progress_reporter
from fw.modules.tasks.models import (
    ACTIVE_STATUSES,
    JOB_FAILED,
    JOB_INTERRUPTED,
    JOB_QUEUED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    BackgroundJob,
)

logger = structlog.get_logger(__name__)

JobFunction = Callable[[AsyncSession], Awaitable[dict[str, Any]]]

HEARTBEAT_EVERY = 10.0  # seconds
HEARTBEAT_STALE_AFTER = timedelta(minutes=2)
PROGRESS_WRITE_EVERY = 0.5  # seconds
INTERRUPTED_MESSAGE = "The server stopped while this job was running. Start it again."

# Tasks running in this process, so they are not garbage-collected and tests can wait for them.
_tasks: dict[UUID, "asyncio.Task[None]"] = {}


def _now() -> datetime:
    return datetime.now(UTC)


async def _set(job_id: UUID, **values: Any) -> None:
    async with async_session_factory() as s:
        await s.execute(update(BackgroundJob).where(BackgroundJob.id == job_id).values(**values))
        await s.commit()


class BackgroundJobService:
    @staticmethod
    async def mark_stale_interrupted(session: AsyncSession) -> None:
        """Store INTERRUPTED on active jobs whose process stopped (no recent heartbeat)."""
        now = _now()
        cutoff = now - HEARTBEAT_STALE_AFTER
        await session.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.status.in_(ACTIVE_STATUSES),
                or_(
                    BackgroundJob.heartbeat_at < cutoff,
                    and_(BackgroundJob.heartbeat_at.is_(None), BackgroundJob.created_at < cutoff),
                ),
            )
            .values(
                status=JOB_INTERRUPTED,
                finished_at=now,
                error_code="JOB_INTERRUPTED",
                error_message=INTERRUPTED_MESSAGE,
            )
        )

    @staticmethod
    async def start(
        *,
        kind: str,
        params: dict[str, Any],
        fn: JobFunction,
        dedupe_key: str | None = None,
        user_id: UUID | None = None,
    ) -> BackgroundJob:
        """Record the job and start it in this process. 409 while a job with the same
        ``dedupe_key`` is still active."""
        async with async_session_factory() as s:
            await BackgroundJobService.mark_stale_interrupted(s)
            await s.commit()
            job = BackgroundJob(
                kind=kind,
                dedupe_key=dedupe_key,
                status=JOB_QUEUED,
                params=params,
                created_by_user_id=user_id,
                heartbeat_at=_now(),
            )
            s.add(job)
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                running = (
                    await s.execute(
                        select(BackgroundJob.id).where(
                            BackgroundJob.dedupe_key == dedupe_key,
                            BackgroundJob.status.in_(ACTIVE_STATUSES),
                        )
                    )
                ).scalar_one_or_none()
                raise AppError(
                    code="JOB_ALREADY_RUNNING",
                    message="The same job is already running. Wait for it to finish.",
                    status_code=409,
                    extra={"job_id": str(running) if running else None},
                ) from None
        task = asyncio.create_task(_run(job.id, fn), name=f"background-job-{kind}-{job.id}")
        _tasks[job.id] = task
        return job

    @staticmethod
    async def get(session: AsyncSession, job_id: UUID) -> BackgroundJob | None:
        await BackgroundJobService.mark_stale_interrupted(session)
        return await session.get(BackgroundJob, job_id, populate_existing=True)

    @staticmethod
    async def list_recent(
        session: AsyncSession,
        *,
        kind: str | None = None,
        active_only: bool = False,
        user_id: UUID | None = None,
        limit: int = 20,
    ) -> list[BackgroundJob]:
        await BackgroundJobService.mark_stale_interrupted(session)
        stmt = select(BackgroundJob).order_by(BackgroundJob.created_at.desc()).limit(limit)
        if kind:
            stmt = stmt.where(BackgroundJob.kind == kind)
        if active_only:
            stmt = stmt.where(BackgroundJob.status.in_(ACTIVE_STATUSES))
        if user_id is not None:
            stmt = stmt.where(BackgroundJob.created_by_user_id == user_id)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def wait(job_id: UUID | str) -> None:
        """Wait for a job started in this process (tests)."""
        task = _tasks.get(UUID(str(job_id)))
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.shield(task)


class _ProgressWriter:
    """Writes the latest progress at most every PROGRESS_WRITE_EVERY seconds (always the first
    report of a phase and the last one)."""

    def __init__(self, job_id: UUID) -> None:
        self.job_id = job_id
        self.last_write = 0.0
        self.phase: str | None = None

    async def __call__(self, phase: str, done: int, total: int) -> None:
        now = time.monotonic()
        if phase == self.phase and done < total and now - self.last_write < PROGRESS_WRITE_EVERY:
            return
        self.phase, self.last_write = phase, now
        await _set(
            self.job_id, phase=phase, progress_done=done, progress_total=total, heartbeat_at=_now()
        )


async def _heartbeat(job_id: UUID) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_EVERY)
        try:
            await _set(job_id, heartbeat_at=_now())
        except Exception as e:  # a missed beat is not worth failing the job
            logger.warning("background_job_heartbeat_failed", job_id=str(job_id), error=str(e))


async def _run(job_id: UUID, fn: JobFunction) -> None:
    token = set_progress_reporter(_ProgressWriter(job_id))
    beat = asyncio.create_task(_heartbeat(job_id))
    try:
        await _set(job_id, status=JOB_RUNNING, started_at=_now(), heartbeat_at=_now())
        async with async_session_factory() as session:
            try:
                result = await fn(session)
                await session.commit()
            except BaseException:
                await session.rollback()
                raise
        await _set(job_id, status=JOB_SUCCEEDED, result=result, finished_at=_now())
        logger.info("background_job_succeeded", job_id=str(job_id))
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await _set(
                job_id,
                status=JOB_INTERRUPTED,
                finished_at=_now(),
                error_code="JOB_INTERRUPTED",
                error_message=INTERRUPTED_MESSAGE,
            )
        raise
    except ProblemDetailsException as e:
        await _set(
            job_id,
            status=JOB_FAILED,
            finished_at=_now(),
            error_code=e.code,
            error_message=str(e.detail),
        )
        logger.info("background_job_failed", job_id=str(job_id), code=e.code)
    except Exception as e:
        logger.exception("background_job_crashed", job_id=str(job_id), error=str(e))
        with contextlib.suppress(Exception):
            await _set(
                job_id,
                status=JOB_FAILED,
                finished_at=_now(),
                error_code="INTERNAL_ERROR",
                error_message="The job failed unexpectedly. The error is in the server log.",
            )
    finally:
        beat.cancel()
        reset_progress_reporter(token)
        _tasks.pop(job_id, None)


async def shutdown_background_jobs() -> None:
    """Cancel the jobs running in this process at shutdown; each stores INTERRUPTED."""
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(BaseException):
            await task
