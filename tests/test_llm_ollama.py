import json
import unittest
from typing import Literal
from unittest.mock import patch

from fastapi import HTTPException
from app.services.llm_ollama import OllamaClient
from app.services import llm_ollama


class _ResponseStub:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_ResponseStub":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class OllamaClientTests(unittest.TestCase):
    def test_generate_sends_think_false(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request: object, timeout: int) -> _ResponseStub:
            body = request.data.decode("utf-8")  # type: ignore[attr-defined]
            captured.update(json.loads(body))
            return _ResponseStub({"model": "gemma4:e4b", "response": "ok"})

        client = OllamaClient(model="gemma4:e4b", provider="ollama", base_url="http://127.0.0.1:11434")
        with patch("app.services.llm_ollama.urlopen", side_effect=fake_urlopen):
            response = client.generate(prompt="hello", system="world")

        self.assertEqual(response.response, "ok")
        self.assertIn("think", captured)
        self.assertFalse(captured["think"])

    def test_generate_for_lmstudio_uses_chat_completions_schema(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request: object, timeout: int) -> _ResponseStub:
            body = request.data.decode("utf-8")  # type: ignore[attr-defined]
            payload = json.loads(body)
            captured.update(payload)
            captured["url"] = request.full_url  # type: ignore[attr-defined]
            return _ResponseStub({"model": "gemma4:e4b", "choices": [{"message": {"content": "ok"}}]})

        client = OllamaClient(model="gemma4:e4b", provider="lmstudio", base_url="http://127.0.0.1:1234")
        with patch("app.services.llm_ollama.urlopen", side_effect=fake_urlopen):
            response = client.generate(prompt="hello", system="world", num_predict=10)

        self.assertEqual(response.response, "ok")
        self.assertEqual(captured["url"], "http://127.0.0.1:1234/v1/chat/completions")
        self.assertNotIn("keep_alive", captured)
        self.assertEqual(captured.get("max_tokens"), 10)
        self.assertEqual(captured["messages"], [{"role": "system", "content": "world"}, {"role": "user", "content": "hello"}])

    def test_lmstudio_warm_and_unload_do_not_hit_network(self) -> None:
        client = OllamaClient(model="gemma4:e4b", provider="lmstudio", base_url="http://127.0.0.1:1234")
        with patch.object(client, "_generate", side_effect=AssertionError("should be no-op")):
            client.warm()
            client.unload()

    def test_lmstudio_parse_raises_for_missing_choices(self) -> None:
        def fake_urlopen(request: object, timeout: int) -> _ResponseStub:
            return _ResponseStub({"model": "gemma4:e4b"})

        client = OllamaClient(model="gemma4:e4b", provider="lmstudio", base_url="http://127.0.0.1:1234")
        with patch("app.services.llm_ollama.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(HTTPException) as exc:
                client.generate(prompt="hello")
        self.assertEqual(exc.exception.status_code, 502)

    def test_unknown_provider_falls_back_to_ollama(self) -> None:
        captured: dict[str, object] = {}

        def fake_urlopen(request: object, timeout: int) -> _ResponseStub:
            body = request.data.decode("utf-8")  # type: ignore[attr-defined]
            captured.update(json.loads(body))
            captured["url"] = request.full_url  # type: ignore[attr-defined]
            return _ResponseStub({"model": "gemma4:e4b", "response": "ok"})

        with patch.object(llm_ollama._LOGGER, "warning") as warn:
            client = OllamaClient(model="gemma4:e4b", provider="invalid-provider", base_url="http://127.0.0.1:11434")
            with patch("app.services.llm_ollama.urlopen", side_effect=fake_urlopen):
                response = client.generate(prompt="hello")

        self.assertEqual(response.response, "ok")
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/generate")
        self.assertIn("think", captured)
        self.assertEqual(captured["think"], False)
        warn.assert_called_once()
