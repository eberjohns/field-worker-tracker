"""Background worker entry point."""

import asyncio
import sys

from fw.core.logging import get_logger, setup_logging

logger = get_logger("fw.worker")


async def main() -> None:
    setup_logging()
    logger.info("worker_started", status="ready")
    stop_event = asyncio.Event()
    try:
        # In future phases, Procrastinate worker runs here
        await stop_event.wait()
    except asyncio.CancelledError:
        logger.info("worker_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
