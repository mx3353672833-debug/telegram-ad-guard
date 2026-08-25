from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class PhotoModerationDecision:
    should_ban: bool
    result: Any
    source: str


async def evaluate_photo_moderation(
    *,
    ai_client,
    user_info: str,
    image_base64: str,
    score_threshold: int,
    message_text: Optional[str] = None,
    logger=None,
    user_id: Optional[int] = None,
) -> PhotoModerationDecision:
    """Evaluate photo moderation with text pre-check that fails open into image scan."""
    if message_text:
        try:
            text_result = await ai_client.check_text(user_info, message_text)
            if text_result.is_spam and text_result.score >= score_threshold:
                return PhotoModerationDecision(True, text_result, "text")
        except Exception as exc:  # pragma: no cover
            if logger:
                logger.warning(
                    "Photo text pre-check failed, continue with image scan (user %s): %s",
                    user_id,
                    exc,
                )

    image_result = await ai_client.check_image(user_info, image_base64)
    return PhotoModerationDecision(
        image_result.is_spam and image_result.score >= score_threshold,
        image_result,
        "image",
    )
