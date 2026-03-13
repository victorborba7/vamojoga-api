import json
import logging
from uuid import UUID

from pywebpush import webpush, WebPushException
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.repositories.push_repository import PushRepository

logger = logging.getLogger(__name__)


class PushService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PushRepository(session)

    async def send_to_user(
        self, user_id: UUID, title: str, body: str, url: str = "/"
    ) -> None:
        """Send a push notification to all subscriptions of a user."""
        if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
            return

        subscriptions = await self.repo.get_by_user(user_id)
        payload = json.dumps({"title": title, "body": body, "url": url})

        expired_endpoints: list[str] = []
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={
                        "sub": settings.VAPID_CLAIMS_EMAIL,
                    },
                )
            except WebPushException as e:
                status = e.response.status_code if e.response is not None else None
                if status in (404, 410):
                    # Subscription expired — remove it
                    expired_endpoints.append(sub.endpoint)
                else:
                    logger.warning("Push failed for user %s: %s", user_id, e)
            except Exception:
                logger.exception("Unexpected push error for user %s", user_id)

        for endpoint in expired_endpoints:
            try:
                await self.repo.delete_by_endpoint(endpoint)
            except Exception:
                pass
