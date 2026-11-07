"""Public interface for notifications module."""

from fw.modules.notifications.handlers import register_notification_handlers
from fw.modules.notifications.models import Alert
from fw.modules.notifications.router import router as alert_router
from fw.modules.notifications.schemas import AlertResolveRequest, AlertResponse
from fw.modules.notifications.service import NotificationService

register_notification_handlers()

__all__ = [
    "Alert",
    "AlertResolveRequest",
    "AlertResponse",
    "NotificationService",
    "alert_router",
    "register_notification_handlers",
]
