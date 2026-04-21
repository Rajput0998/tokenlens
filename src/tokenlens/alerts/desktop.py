"""Desktop notifications via plyer (cross-platform)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_desktop_notification(
    title: str,
    message: str,
    timeout: int = 10,
    enabled: bool = True,
) -> bool:
    """Send a desktop notification via plyer.

    Args:
        title: Notification title.
        message: Notification body.
        timeout: Display duration in seconds.
        enabled: If False, skip notification (configurable).

    Returns:
        True if notification was sent, False otherwise.
    """
    if not enabled:
        return False

    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name="TokenLens",
            timeout=timeout,
        )
        return True
    except ImportError:
        logger.warning("plyer not installed — desktop notifications unavailable.")
        return False
    except Exception as e:
        logger.warning("Desktop notification failed: %s", e)
        return False


def dispatch_desktop_alert(alert: dict[str, Any], enabled: bool = True) -> bool:
    """Dispatch an alert dict as a desktop notification.

    Args:
        alert: Alert dict with 'title' and 'message' keys.
        enabled: Whether desktop notifications are enabled.

    Returns:
        True if sent successfully.
    """
    title = alert.get("title", "TokenLens Alert")
    message = alert.get("message", "")
    return send_desktop_notification(title=title, message=message, enabled=enabled)
