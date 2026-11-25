"""Push notifications: not used in v1 (owner, 19 and 25 Nov 2026; DEC-64).

The app syncs on its own schedule and when it opens; no push is sent. The port stays so a real
provider can be added later without touching the callers, and `registered_devices.push_token`
is still stored if a phone sends one.
"""

from typing import Any, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)


@runtime_checkable
class PushProvider(Protocol):
    """Port for sending push notifications."""

    async def send_silent(self, token: str, data: dict[str, Any]) -> bool:
        """Send a silent data push. Returns whether a push was actually sent."""
        ...


class NullPushProvider:
    """Sends nothing (push is not used in v1)."""

    async def send_silent(self, token: str, data: dict[str, Any]) -> bool:
        logger.debug("push_not_sent_disabled_in_v1", data_type=data.get("type"))
        return False


def get_push_provider() -> PushProvider:
    return NullPushProvider()
