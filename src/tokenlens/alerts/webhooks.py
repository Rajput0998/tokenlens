"""Webhook dispatchers for Slack, Discord, and Teams via httpx async."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def post_slack(webhook_url: str, alert: dict[str, Any]) -> bool:
    """Post alert to Slack webhook.

    Args:
        webhook_url: Slack incoming webhook URL.
        alert: Alert dict with title, message, severity.

    Returns:
        True if POST succeeded (2xx).
    """
    payload = {
        "text": f"*{alert.get('title', 'Alert')}*\n{alert.get('message', '')}",
        "attachments": [
            {
                "color": "#ff0000" if alert.get("severity") == "critical" else "#ffaa00",
                "fields": [
                    {"title": "Severity", "value": alert.get("severity", "warning"), "short": True},
                    {"title": "Category", "value": alert.get("category", "unknown"), "short": True},
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.is_success
    except Exception as e:
        logger.warning("Slack webhook failed: %s", e)
        return False


async def post_discord(webhook_url: str, alert: dict[str, Any]) -> bool:
    """Post alert to Discord webhook.

    Args:
        webhook_url: Discord webhook URL.
        alert: Alert dict with title, message, severity.

    Returns:
        True if POST succeeded (2xx).
    """
    color = 0xFF0000 if alert.get("severity") == "critical" else 0xFFAA00
    payload = {
        "embeds": [
            {
                "title": alert.get("title", "TokenLens Alert"),
                "description": alert.get("message", ""),
                "color": color,
                "fields": [
                    {"name": "Severity", "value": alert.get("severity", "warning"), "inline": True},
                    {"name": "Category", "value": alert.get("category", "unknown"), "inline": True},
                ],
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.is_success
    except Exception as e:
        logger.warning("Discord webhook failed: %s", e)
        return False


async def post_teams(webhook_url: str, alert: dict[str, Any]) -> bool:
    """Post alert to Microsoft Teams webhook.

    Args:
        webhook_url: Teams incoming webhook URL.
        alert: Alert dict with title, message, severity.

    Returns:
        True if POST succeeded (2xx).
    """
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "FF0000" if alert.get("severity") == "critical" else "FFAA00",
        "summary": alert.get("title", "TokenLens Alert"),
        "sections": [
            {
                "activityTitle": alert.get("title", "TokenLens Alert"),
                "facts": [
                    {"name": "Severity", "value": alert.get("severity", "warning")},
                    {"name": "Category", "value": alert.get("category", "unknown")},
                ],
                "text": alert.get("message", ""),
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.is_success
    except Exception as e:
        logger.warning("Teams webhook failed: %s", e)
        return False


async def dispatch_webhooks(alert: dict[str, Any]) -> dict[str, bool]:
    """Dispatch alert to all configured webhooks.

    Reads webhook URLs from config and posts to each.

    Returns:
        Dict mapping service name to success boolean.
    """
    from tokenlens.core.config import settings

    results: dict[str, bool] = {}

    slack_url = settings.get("alerts.webhooks.slack_url", None)
    if slack_url:
        results["slack"] = await post_slack(slack_url, alert)

    discord_url = settings.get("alerts.webhooks.discord_url", None)
    if discord_url:
        results["discord"] = await post_discord(discord_url, alert)

    teams_url = settings.get("alerts.webhooks.teams_url", None)
    if teams_url:
        results["teams"] = await post_teams(teams_url, alert)

    return results
