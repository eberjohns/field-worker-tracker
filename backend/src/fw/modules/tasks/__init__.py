"""Public interface for the background jobs module (Batch 9 step 4)."""

from fw.modules.tasks.models import (
    JOB_FAILED,
    JOB_INTERRUPTED,
    JOB_QUEUED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    BackgroundJob,
)
from fw.modules.tasks.schemas import BackgroundJobRead
from fw.modules.tasks.service import BackgroundJobService, shutdown_background_jobs

__all__ = [
    "JOB_FAILED",
    "JOB_INTERRUPTED",
    "JOB_QUEUED",
    "JOB_RUNNING",
    "JOB_SUCCEEDED",
    "BackgroundJob",
    "BackgroundJobRead",
    "BackgroundJobService",
    "shutdown_background_jobs",
]
