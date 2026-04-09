"""
Notification helper service for org-level event fan-out.

Provides a single async function `create_org_notification()` that creates
one Notification row per active user in the target org.

Design decisions (per Phase 10 D-01, D-02):
- Fan-out per user: each active org member gets their own notification row.
- Session-per-operation: opens its own DB session; never accepts a caller session.
- Bulk insert via INSERT ... VALUES for efficiency (typically <20 users per org).
- Returns the count of rows inserted (0 if org has no active users).
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.base import get_session_factory
from app.models.user import Notification, User

logger = logging.getLogger(__name__)


async def create_org_notification(
    org_id: str,
    type: str,
    title: str,
    message: str,
    data: Optional[dict] = None,
) -> int:
    """Create one Notification row per active user in org_id.

    Opens its own DB session (session-per-operation pattern).
    Does NOT accept or reuse a caller session.

    Args:
        org_id:  UUID string of the target organization.
        type:    Notification type string (e.g. "SYNC_COMPLETE", "SYNC_FAILED").
        title:   Short notification title (max 255 chars).
        message: Full notification message body.
        data:    Optional dict stored in the JSONB data column.

    Returns:
        Number of Notification rows inserted (0 if org has no active users).
    """
    async with get_session_factory()() as db:
        result = await db.execute(
            select(User.id).where(
                User.organization_id == org_id,
                User.is_active == True,  # noqa: E712
            )
        )
        user_ids = result.scalars().all()

        if not user_ids:
            logger.debug(
                "create_org_notification: org_id=%s has no active users, skipping type=%s",
                org_id,
                type,
            )
            return 0

        rows = [
            {
                "user_id": uid,
                "type": type,
                "title": title,
                "message": message,
                "data": data or {},
            }
            for uid in user_ids
        ]

        await db.execute(insert(Notification).values(rows))
        await db.commit()

        logger.info(
            "create_org_notification: created %d notification(s) for org_id=%s type=%s",
            len(rows),
            org_id,
            type,
        )
        return len(rows)
