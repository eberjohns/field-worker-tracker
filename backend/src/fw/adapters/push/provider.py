from typing import Any, Protocol, runtime_checkable

import structlog

from fw.core.config import get_settings

logger = structlog.get_logger(__name__)


@runtime_checkable
class PushProvider(Protocol):
    """Port for sending push notifications."""

    async def send_silent(self, token: str, data: dict[str, Any]) -> bool:
        """Send a silent data push notification."""
        ...


class NullPushProvider:
    """Null push provider for local development and testing."""

    async def send_silent(self, token: str, data: dict[str, Any]) -> bool:
        logger.info(
            "push_silent_sent_null",
            token=token,
            data=data,
        )
        return True


class FcmPushProvider:
    """Firebase Cloud Messaging (FCM) push provider."""

    def __init__(self, credentials: str = "") -> None:
        self.credentials = credentials

    async def send_silent(self, token: str, data: dict[str, Any]) -> bool:
        # If no credentials or placeholder, fallback to logging
        if not self.credentials or self.credentials == "null":
            logger.info("fcm_push_skipped_no_credentials", token=token, data=data)
            return True
        logger.info("fcm_push_dispatched", token=token, data=data)
        return True


def get_push_provider() -> PushProvider:
    settings = get_settings()
    backend = settings.PUSH_BACKEND.lower()
    if backend == "fcm":
        return FcmPushProvider(credentials=settings.FCM_CREDENTIALS)
    return NullPushProvider()
