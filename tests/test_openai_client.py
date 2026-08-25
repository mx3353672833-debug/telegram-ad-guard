import asyncio
import importlib
import sys
from types import ModuleType
from types import SimpleNamespace


def load_openai_client_module(monkeypatch):
    fake_config_module = ModuleType("config")
    fake_config_module.config = SimpleNamespace(get=lambda key, default=None: default)
    fake_openai_module = ModuleType("openai")
    fake_openai_module.AsyncOpenAI = object

    monkeypatch.setitem(sys.modules, "config", fake_config_module)
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)
    for name in ["ai", "ai.openai_client"]:
        sys.modules.pop(name, None)

    return importlib.import_module("ai.openai_client")


def test_call_with_retry_retries_before_success(monkeypatch):
    module = load_openai_client_module(monkeypatch)
    attempts = []
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    class FakeCompletions:
        async def create(self, **kwargs):
            attempts.append(kwargs)
            if len(attempts) < 3:
                raise RuntimeError(f"fail-{len(attempts)}")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"state": 0, "spam_score": 0, "spam_reason": "", "spam_mock_text": ""}'))]
            )

    class FakeAsyncOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    client = module.OpenAIClient("k", "https://example.com/v1", "gpt-test")

    content = asyncio.run(client._call_with_retry([{"role": "user", "content": "hello"}]))

    assert '"state": 0' in content
    assert len(attempts) == 3
    assert sleeps == [1, 2]


def test_parse_result_extracts_json_from_wrapped_response(monkeypatch):
    module = load_openai_client_module(monkeypatch)

    class FakeAsyncOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=None)

    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    client = module.OpenAIClient("k", "https://example.com/v1", "gpt-test")

    result = client._parse_result(
        "```json\n"
        '{"state": 1, "spam_score": 91, "spam_reason": "ad", "spam_mock_text": "mock"}\n'
        "```"
    )

    assert result.is_spam is True
    assert result.score == 91
    assert result.reason == "ad"
    assert result.mock_text == "mock"


def test_parse_result_returns_safe_fallback_on_invalid_json(monkeypatch):
    module = load_openai_client_module(monkeypatch)

    class FakeAsyncOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=None)

    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    client = module.OpenAIClient("k", "https://example.com/v1", "gpt-test")

    result = client._parse_result("not json at all")

    assert result.is_spam is False
    assert result.score == 0


def test_check_image_uses_multimodal_payload(monkeypatch):
    module = load_openai_client_module(monkeypatch)
    seen_messages = []

    async def fake_call_with_retry(messages):
        seen_messages.extend(messages)
        return '{"state": 0, "spam_score": 0, "spam_reason": "", "spam_mock_text": ""}'

    class FakeAsyncOpenAI:
        def __init__(self, api_key, base_url):
            self.chat = SimpleNamespace(completions=None)

    monkeypatch.setattr(module, "AsyncOpenAI", FakeAsyncOpenAI)
    client = module.OpenAIClient("k", "https://example.com/v1", "gpt-test")
    monkeypatch.setattr(client, "_call_with_retry", fake_call_with_retry)

    result = asyncio.run(client.check_image("user-info", "data:image/jpeg;base64,AAA"))

    assert result.is_spam is False
    assert seen_messages[0]["role"] == "user"
    assert seen_messages[0]["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,AAA"
