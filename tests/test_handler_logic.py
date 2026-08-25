import asyncio
from types import SimpleNamespace

from handler_logic import evaluate_photo_moderation


class FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message, *args):
        self.warnings.append(message % args if args else message)


class FakeAIClient:
    def __init__(self, *, text_result=None, image_result=None, text_error=None):
        self.text_result = text_result
        self.image_result = image_result
        self.text_error = text_error
        self.calls = []

    async def check_text(self, user_info, message_text):
        self.calls.append(("text", user_info, message_text))
        if self.text_error:
            raise self.text_error
        return self.text_result

    async def check_image(self, user_info, image_base64):
        self.calls.append(("image", user_info, image_base64))
        return self.image_result


def test_evaluate_photo_moderation_bans_on_text_precheck():
    client = FakeAIClient(
        text_result=SimpleNamespace(is_spam=True, score=95),
        image_result=SimpleNamespace(is_spam=False, score=10),
    )

    decision = asyncio.run(
        evaluate_photo_moderation(
            ai_client=client,
            user_info="user-info",
            image_base64="image-data",
            score_threshold=80,
            message_text="caption text",
        )
    )

    assert decision.should_ban is True
    assert decision.source == "text"
    assert client.calls == [("text", "user-info", "caption text")]


def test_evaluate_photo_moderation_falls_back_to_image_when_text_check_fails():
    logger = FakeLogger()
    image_result = SimpleNamespace(is_spam=True, score=88)
    client = FakeAIClient(
        image_result=image_result,
        text_error=RuntimeError("provider unstable"),
    )

    decision = asyncio.run(
        evaluate_photo_moderation(
            ai_client=client,
            user_info="user-info",
            image_base64="image-data",
            score_threshold=80,
            message_text="caption text",
            logger=logger,
            user_id=123,
        )
    )

    assert decision.should_ban is True
    assert decision.source == "image"
    assert decision.result is image_result
    assert client.calls == [
        ("text", "user-info", "caption text"),
        ("image", "user-info", "image-data"),
    ]
    assert logger.warnings


def test_evaluate_photo_moderation_uses_image_when_text_is_clean():
    image_result = SimpleNamespace(is_spam=False, score=12)
    client = FakeAIClient(
        text_result=SimpleNamespace(is_spam=False, score=0),
        image_result=image_result,
    )

    decision = asyncio.run(
        evaluate_photo_moderation(
            ai_client=client,
            user_info="user-info",
            image_base64="image-data",
            score_threshold=80,
            message_text="caption text",
        )
    )

    assert decision.should_ban is False
    assert decision.source == "image"
    assert decision.result is image_result
