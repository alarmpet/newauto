import json
from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from fastapi import HTTPException

from ..config import COMFYUI_BASE_URL

WorkflowPayload = dict[str, object]


@dataclass(frozen=True)
class ComfyPromptSubmission:
    prompt_id: str
    number: int
    node_errors: dict[str, object]


@dataclass(frozen=True)
class ComfyImageResult:
    filename: str
    subfolder: str
    type: str


class ComfyUIClient:
    def __init__(self, *, base_url: str = COMFYUI_BASE_URL, timeout_sec: int = 30) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout_sec = max(1, timeout_sec)

    def submit_workflow(self, workflow: WorkflowPayload, *, client_id: str = "newauto") -> ComfyPromptSubmission:
        payload: dict[str, object] = {
            "prompt": workflow,
            "client_id": client_id,
        }
        response = self._request_json("prompt", payload)
        prompt_id = response.get("prompt_id")
        number = response.get("number")
        node_errors = response.get("node_errors")
        if not isinstance(prompt_id, str) or not isinstance(number, int) or not isinstance(node_errors, dict):
            raise HTTPException(502, "ComfyUI prompt response format is invalid.")
        return ComfyPromptSubmission(prompt_id=prompt_id, number=number, node_errors=node_errors)

    def get_history(self, prompt_id: str) -> dict[str, object]:
        response = self._request_json(f"history/{prompt_id}")
        if not isinstance(response, dict):
            raise HTTPException(502, "ComfyUI history response format is invalid.")
        return response

    def extract_image_results(self, history: Mapping[str, object], prompt_id: str) -> list[ComfyImageResult]:
        prompt_entry = history.get(prompt_id)
        if not isinstance(prompt_entry, dict):
            return []
        outputs = prompt_entry.get("outputs")
        if not isinstance(outputs, dict):
            return []
        results: list[ComfyImageResult] = []
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images")
            if not isinstance(images, list):
                continue
            for item in images:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename")
                subfolder = item.get("subfolder")
                file_type = item.get("type")
                if isinstance(filename, str) and isinstance(subfolder, str) and isinstance(file_type, str):
                    results.append(
                        ComfyImageResult(
                            filename=filename,
                            subfolder=subfolder,
                            type=file_type,
                        )
                    )
        return results

    def extract_execution_error(self, history: Mapping[str, object], prompt_id: str) -> str:
        prompt_entry = history.get(prompt_id)
        if not isinstance(prompt_entry, dict):
            return ""
        status = prompt_entry.get("status")
        if not isinstance(status, dict):
            return ""
        if status.get("status_str") != "error":
            return ""
        messages = status.get("messages")
        if not isinstance(messages, list):
            return "ComfyUI workflow execution failed."
        for item in reversed(messages):
            if not isinstance(item, list) or len(item) != 2:
                continue
            event_name, payload = item
            if event_name != "execution_error" or not isinstance(payload, dict):
                continue
            node_type = payload.get("node_type")
            exception_message = payload.get("exception_message")
            if isinstance(node_type, str) and isinstance(exception_message, str):
                return f"ComfyUI {node_type} failed: {exception_message.strip() or 'unknown error'}"
        return "ComfyUI workflow execution failed."

    def _request_json(self, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        method = "POST" if payload is not None else "GET"
        request = Request(
            urljoin(self.base_url, path),
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_sec) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(502, f"ComfyUI request failed: HTTP {exc.code} {detail}".strip()) from exc
        except URLError as exc:
            raise HTTPException(502, "ComfyUI 서버에 연결하지 못했습니다.") from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(502, "ComfyUI 응답을 해석하지 못했습니다.") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(502, "ComfyUI 응답 형식이 올바르지 않습니다.")
        return parsed
