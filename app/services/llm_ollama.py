import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from fastapi import HTTPException

from ..config import LLM_PROVIDER, LMSTUDIO_BASE_URL, OLLAMA_BASE_URL

_LOGGER = logging.getLogger(__name__)


def _normalize_provider(raw: str | None) -> str:
    normalized = (raw or "").strip().lower()
    if normalized in {"", "ollama"}:
        return "ollama"
    if normalized == "lmstudio":
        return "lmstudio"
    _LOGGER.warning("Unsupported provider=%r in OllamaClient; falling back to 'ollama'.", raw)
    return "ollama"


@dataclass(frozen=True)
class OllamaGenerateResponse:
    model: str
    response: str


class OllamaClient:
    def __init__(
        self,
        *,
        model: str,
        base_url: str | None = None,
        provider: str | None = None,
    ) -> None:
        self.model = model
        self.provider = _normalize_provider(provider or LLM_PROVIDER)
        if base_url is None:
            base_url = OLLAMA_BASE_URL if self.provider == "ollama" else LMSTUDIO_BASE_URL
        self.base_url = base_url.rstrip("/") + "/"

    def warm(self) -> None:
        if self.provider == "lmstudio":
            _LOGGER.debug("LM Studio provider: warm is a no-op.")
            return
        self._generate(prompt="", keep_alive=-1, num_predict=1)

    def unload(self) -> None:
        if self.provider == "lmstudio":
            _LOGGER.debug("LM Studio provider: unload is a no-op.")
            return
        self._generate(prompt="", keep_alive=0, num_predict=0)

    def generate(
        self,
        *,
        prompt: str,
        system: str = "",
        keep_alive: int = -1,
        num_predict: int = 500,
        temperature: float = 0.3,
    ) -> OllamaGenerateResponse:
        return self._generate(
            prompt=prompt,
            system=system,
            keep_alive=keep_alive,
            num_predict=num_predict,
            temperature=temperature,
        )

    def _generate(
        self,
        *,
        prompt: str,
        system: str = "",
        keep_alive: int = -1,
        num_predict: int = 500,
        temperature: float = 0.3,
    ) -> OllamaGenerateResponse:
        if self.provider == "lmstudio":
            endpoint = "v1/chat/completions"
            messages = [{"role": "user", "content": prompt}]
            if system:
                messages.insert(0, {"role": "system", "content": system})
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "temperature": temperature,
                "max_tokens": num_predict,
            }
        else:
            endpoint = "api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "think": False,
                "keep_alive": keep_alive,
                "options": {
                    "num_ctx": 2048,
                    "num_predict": num_predict,
                    "temperature": temperature,
                },
            }

        request = Request(
            urljoin(self.base_url, endpoint),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=180) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(502, f"{self.provider} request failed: HTTP {exc.code} {detail}".strip()) from exc
        except URLError as exc:
            raise HTTPException(502, f"{self.provider} 서비스에 접근할 수 없습니다.") from exc

        try:
            payload_obj = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(502, f"{self.provider} 응답 파싱에 실패했습니다.") from exc

        if self.provider == "lmstudio":
            choices = payload_obj.get("choices")
            message_content = None
            if isinstance(choices, list) and choices:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    message = first_choice.get("message")
                    if isinstance(message, dict):
                        message_content = message.get("content")
            model = payload_obj.get("model")
            if not isinstance(message_content, str) or not isinstance(model, str):
                raise HTTPException(502, "LM Studio 응답 형식이 비정상적입니다.")
            content = message_content
        else:
            model = payload_obj.get("model")
            content = payload_obj.get("response")
            if not isinstance(content, str) or not isinstance(model, str):
                raise HTTPException(502, "Ollama 응답 형식이 비정상적입니다.")

        if not isinstance(content, str) or not isinstance(model, str):
            raise HTTPException(502, f"{self.provider} 응답 형식이 비정상적입니다.")
        return OllamaGenerateResponse(model=model, response=content.strip())
