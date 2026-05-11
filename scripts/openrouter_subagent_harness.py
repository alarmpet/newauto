from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast


ROOT_DIR = Path(__file__).resolve().parents[1]
OPENROUTER_KEY_FILE = ROOT_DIR / "openrouter.txt"
BUDGET_PATH = ROOT_DIR / "storage" / "agent_memory" / "openrouter_budget.json"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_FREE_MODEL = "qwen/qwen3-32b:free"
DEFAULT_FALLBACK_FREE_MODEL = "deepseek/deepseek-chat-v3-0324:free"

SECRET_RE = re.compile(
    r"(?i)(token|password|passwd|secret|api[_-]?key|authorization|bearer|cookie)\s*[:=]\s*[^,\s\"']+"
)
RAW_KEY_RE = re.compile(r"sk-or-[A-Za-z0-9_-]+")
DENY_PATH_PARTS = {
    ".env",
    "openrouter.txt",
    "credentials",
    "browser_profiles",
    "appdata",
    "cookies",
    "token",
    "secret",
}
MODE_BUDGETS = {
    "review": 600,
    "plan": 200,
    "debug": 100,
    "code_patch": 100,
}
MODE_ENV = {
    "review": "OPENROUTER_MODEL_REVIEWER",
    "plan": "OPENROUTER_MODEL_PLANNER",
    "debug": "OPENROUTER_MODEL_DEBUGGER",
    "code_patch": "OPENROUTER_MODEL_CODER",
}
MODE_MAX_TOKENS = {
    "review": 1500,
    "plan": 2000,
    "debug": 1500,
    "code_patch": 2500,
}
SYSTEM_PROMPT = """You are an external OpenRouter subagent for a local coding assistant.
You are advisory only. Do not request secrets. Do not tell the operator to bypass safety.
Return only compact JSON matching the requested schema. Do not include markdown."""


@dataclass(frozen=True)
class HarnessResult:
    ok: bool
    mode: str
    model: str
    model_chain: list[str] | None = None
    skipped: bool = False
    error: str = ""
    packed_context: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] | None = None


class OpenRouterCallError(RuntimeError):
    def __init__(self, message: str, *, error_class: str, fallback_allowed: bool) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.fallback_allowed = fallback_allowed


class OpenRouterAllModelsFailed(RuntimeError):
    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        super().__init__("all_models_failed")
        self.attempts = attempts


def _today() -> str:
    return str(date.today())


def _now_epoch() -> float:
    return time.time()


def _redact_text(value: str) -> str:
    value = SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return RAW_KEY_RE.sub("sk-or-[REDACTED]", value)


def redact(value: object) -> object:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items()}
    return value


def load_api_key() -> tuple[str, str]:
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip().lstrip("\ufeff")
    if env_key:
        return env_key, "env"
    if OPENROUTER_KEY_FILE.exists():
        for raw_line in OPENROUTER_KEY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip().lstrip("\ufeff")
            if line and not line.startswith("#"):
                return line, "openrouter.txt:first-line"
    return "", "missing"


def _empty_budget() -> dict[str, Any]:
    return {
        "date": _today(),
        "requests_today": 0,
        "mode_usage": {mode: 0 for mode in MODE_BUDGETS},
        "recent_request_times": [],
        "last_attempts": [],
    }


def load_budget() -> dict[str, Any]:
    if BUDGET_PATH.exists():
        try:
            payload = json.loads(BUDGET_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("date") == _today():
                payload.setdefault("mode_usage", {})
                payload.setdefault("recent_request_times", [])
                payload.setdefault("last_attempts", [])
                for mode in MODE_BUDGETS:
                    payload["mode_usage"].setdefault(mode, 0)
                return payload
        except Exception:
            pass
    return _empty_budget()


def save_budget(payload: dict[str, Any]) -> None:
    BUDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_PATH.write_text(json.dumps(redact(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def budget_status() -> dict[str, Any]:
    payload = load_budget()
    used = int(payload.get("requests_today", 0))
    return {
        "date": payload.get("date", _today()),
        "requests_today": used,
        "remaining_today": max(0, 1000 - used),
        "mode_usage": payload.get("mode_usage", {}),
        "soft_limit_reached": used >= 800,
        "warning_limit_reached": used >= 900,
        "hard_limit_reached": used >= 950,
        "absolute_stop_reached": used >= 1000,
        "last_attempts": payload.get("last_attempts", []),
    }


def reserve_budget(mode: str, *, model: str, essential: bool) -> dict[str, Any]:
    payload = load_budget()
    now = _now_epoch()
    recent = [
        float(item) for item in payload.get("recent_request_times", [])
        if isinstance(item, (int, float)) and now - float(item) < 60
    ]
    used = int(payload.get("requests_today", 0))
    mode_usage = payload.setdefault("mode_usage", {})
    mode_used = int(mode_usage.get(mode, 0))
    mode_limit = MODE_BUDGETS[mode]
    if used >= 1000:
        raise RuntimeError("OpenRouter daily absolute stop reached: 1000/1000")
    if used >= 950 and not essential:
        raise RuntimeError("OpenRouter hard limit reached: non-essential calls blocked after 950/day")
    if used >= 800 and not essential:
        raise RuntimeError("OpenRouter soft limit reached: non-essential calls blocked after 800/day")
    if mode_used >= mode_limit and not essential:
        raise RuntimeError(f"OpenRouter mode budget reached for {mode}: {mode_used}/{mode_limit}")
    if len(recent) >= 20:
        raise RuntimeError("OpenRouter rate limit guard reached: 20 requests/minute")
    payload["requests_today"] = used + 1
    mode_usage[mode] = mode_used + 1
    recent.append(now)
    payload["recent_request_times"] = recent[-20:]
    payload["last_reserved_model"] = model
    save_budget(payload)
    return payload


def record_attempt(mode: str, *, model: str, ok: bool, error_class: str = "") -> None:
    payload = load_budget()
    attempts = payload.setdefault("last_attempts", [])
    if not isinstance(attempts, list):
        attempts = []
    attempts.append(
        {
            "ts": _now_epoch(),
            "mode": mode,
            "model": model,
            "ok": ok,
            "error_class": error_class,
        }
    )
    payload["last_attempts"] = attempts[-20:]
    save_budget(payload)


def _validate_free_model(model: str) -> str:
    cleaned = model.strip()
    if not cleaned:
        return ""
    if not cleaned.endswith(":free"):
        raise RuntimeError(f"Refusing non-free OpenRouter model: {cleaned}")
    return cleaned


def resolve_model_chain(mode: str, explicit_model: str = "") -> list[str]:
    primary_candidates = [
        explicit_model,
        os.environ.get(MODE_ENV[mode], ""),
        os.environ.get("OPENROUTER_MODEL", ""),
        DEFAULT_FREE_MODEL,
    ]
    primary = next((item for item in primary_candidates if item and item.strip()), "")
    candidates = [
        primary,
        os.environ.get("OPENROUTER_FALLBACK_MODEL", ""),
        DEFAULT_FALLBACK_FREE_MODEL,
    ]
    chain: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if not item or not item.strip():
            continue
        model = _validate_free_model(item)
        if model and model not in seen:
            chain.append(model)
            seen.add(model)
    if not chain:
        raise RuntimeError(
            f"No OpenRouter model configured for mode={mode}. Set {MODE_ENV[mode]} or pass --model."
        )
    return chain


def resolve_model(mode: str, explicit_model: str = "") -> str:
    return resolve_model_chain(mode, explicit_model)[0]


def is_denied_path(path: Path) -> bool:
    lowered_parts = [part.lower() for part in path.parts]
    text = str(path).lower()
    if "appdata" in lowered_parts:
        return True
    return any(part in lowered_parts or part in text for part in DENY_PATH_PARTS)


def _safe_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except Exception:
        return str(path)


def read_file_snippet(path: Path, max_chars: int) -> dict[str, Any]:
    resolved = path if path.is_absolute() else ROOT_DIR / path
    if is_denied_path(resolved):
        return {"path": str(resolved), "blocked": True, "reason": "denied_path"}
    if not resolved.exists() or not resolved.is_file():
        return {"path": str(resolved), "blocked": True, "reason": "missing_file"}
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"path": str(resolved), "blocked": True, "reason": f"read_error:{type(exc).__name__}"}
    if len(text) > max_chars:
        half = max(1, max_chars // 2)
        text = text[:half] + "\n...[truncated]...\n" + text[-half:]
    return {
        "path": _safe_relative(resolved),
        "blocked": False,
        "chars": len(text),
        "text": _redact_text(text),
    }


def read_log_tail(path: Path, max_lines: int = 200, max_chars: int = 12000) -> dict[str, Any]:
    resolved = path if path.is_absolute() else ROOT_DIR / path
    if is_denied_path(resolved):
        return {"path": str(resolved), "blocked": True, "reason": "denied_path"}
    if not resolved.exists() or not resolved.is_file():
        return {"path": str(resolved), "blocked": True, "reason": "missing_file"}
    try:
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return {"path": str(resolved), "blocked": True, "reason": f"read_error:{type(exc).__name__}"}
    text = "\n".join(lines[-max_lines:])
    if len(text) > max_chars:
        text = text[-max_chars:]
    return {
        "path": _safe_relative(resolved),
        "blocked": False,
        "lines": min(max_lines, len(lines)),
        "text": _redact_text(text),
    }


def pack_context(
    *,
    mode: str,
    task: str,
    task_file: str,
    files: list[str],
    log_file: str,
    max_input_chars: int,
) -> dict[str, Any]:
    task_text = task.strip()
    if task_file:
        task_payload = read_file_snippet(Path(task_file), min(max_input_chars, 12000))
        if not task_payload.get("blocked"):
            task_text = str(task_payload.get("text", "")).strip()
    snippets: list[dict[str, Any]] = []
    per_file = max(2000, min(12000, max_input_chars // max(1, len(files) + 2)))
    for item in files:
        snippets.append(read_file_snippet(Path(item), per_file))
    log_tail = read_log_tail(Path(log_file)) if log_file else {}
    payload: dict[str, Any] = {
        "mode": mode,
        "task": _redact_text(task_text),
        "files": snippets,
        "log_tail": log_tail,
        "requested_schema": {
            "diagnosis": "string",
            "confidence": "number 0..1",
            "recommended_actions": [
                {
                    "type": "edit|command|investigate|ask_user|no_action",
                    "file": "string optional",
                    "reason": "string",
                    "patch_intent": "string optional",
                }
            ],
            "verification": ["string"],
            "risks": ["string"],
        },
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(text) > max_input_chars:
        payload["truncated"] = True
        payload["files"] = payload["files"][:3]
        payload["task"] = str(payload["task"])[: max_input_chars // 3]
        if isinstance(payload.get("log_tail"), dict) and "text" in payload["log_tail"]:
            payload["log_tail"]["text"] = str(payload["log_tail"]["text"])[-max_input_chars // 3:]
    return payload


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        payload = json.loads(stripped)
        return payload if isinstance(payload, dict) else {"raw": payload}
    except Exception:
        pass
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        return {"raw": _redact_text(text)}
    try:
        payload = json.loads(match.group(0))
        return payload if isinstance(payload, dict) else {"raw": payload}
    except Exception:
        return {"raw": _redact_text(text)}


def _classify_http_error(status_code: int, detail: str = "") -> tuple[str, bool]:
    lowered_detail = detail.lower()
    if (
        "no endpoints found" in lowered_detail
        or "not a valid model id" in lowered_detail
        or "model unavailable" in lowered_detail
        or "provider unavailable" in lowered_detail
    ):
        return "model_unavailable", True
    if status_code in {408, 409}:
        return "transient_http", True
    if status_code == 429:
        return "rate_limit", True
    if status_code >= 500:
        return "server_error", True
    if status_code in {401, 403}:
        return "auth_error", False
    return "http_error", False


def _classify_error_message(message: str) -> tuple[str, bool]:
    lowered = message.lower()
    if "provider unavailable" in lowered or "model unavailable" in lowered:
        return "provider_unavailable", True
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout", True
    return "request_error", False


def call_openrouter(
    model: str,
    packed_context: dict[str, Any],
    api_key: str,
    timeout_sec: int,
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(packed_context, ensure_ascii=False, sort_keys=True)},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://local.newauto",
        "X-Title": "newauto-openrouter-subagent",
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        error_class, fallback_allowed = _classify_http_error(exc.code, detail)
        raise OpenRouterCallError(
            f"OpenRouter HTTP {exc.code}: {_redact_text(detail)}",
            error_class=error_class,
            fallback_allowed=fallback_allowed,
        ) from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        error_class, fallback_allowed = _classify_error_message(str(exc))
        raise OpenRouterCallError(
            _redact_text(f"{type(exc).__name__}: {exc}")[:1000],
            error_class=error_class,
            fallback_allowed=fallback_allowed,
        ) from exc
    except json.JSONDecodeError as exc:
        raise OpenRouterCallError(
            _redact_text(f"JSONDecodeError: {exc}")[:1000],
            error_class="parse_error",
            fallback_allowed=True,
        ) from exc
    choices = data.get("choices", [])
    content = ""
    if choices and isinstance(choices[0], dict):
        content = str(choices[0].get("message", {}).get("content") or "")
    if not content.strip():
        raise OpenRouterCallError("empty_response", error_class="empty_response", fallback_allowed=True)
    parsed = _extract_json_object(content)
    if "raw" in parsed:
        raise OpenRouterCallError("json_parse_failed", error_class="parse_error", fallback_allowed=True)
    return parsed, {
        "id": data.get("id", ""),
        "usage": data.get("usage", {}),
        "finish_reason": choices[0].get("finish_reason", "") if choices and isinstance(choices[0], dict) else "",
    }


def call_openrouter_with_fallback(
    *,
    mode: str,
    model_chain: list[str],
    packed_context: dict[str, Any],
    api_key: str,
    essential: bool,
    timeout_sec: int,
) -> tuple[str, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    max_tokens = MODE_MAX_TOKENS.get(mode, 1500)
    for index, model in enumerate(model_chain):
        model_timeout = timeout_sec if timeout_sec != 45 else (60 if index == 0 else 45)
        reserve_budget(mode, model=model, essential=essential)
        try:
            response, usage = call_openrouter(model, packed_context, api_key, model_timeout, max_tokens)
        except OpenRouterCallError as exc:
            attempt = {
                "mode": mode,
                "model": model,
                "ok": False,
                "error_class": exc.error_class,
                "error": _redact_text(str(exc))[:1000],
            }
            attempts.append(attempt)
            record_attempt(mode, model=model, ok=False, error_class=exc.error_class)
            if not exc.fallback_allowed or index >= len(model_chain) - 1:
                raise OpenRouterAllModelsFailed(attempts) from exc
            continue
        attempts.append({"mode": mode, "model": model, "ok": True, "error_class": ""})
        record_attempt(mode, model=model, ok=True)
        usage["attempts"] = attempts
        usage["max_tokens"] = max_tokens
        usage["timeout_sec"] = model_timeout
        return model, response, usage, attempts
    raise OpenRouterAllModelsFailed(attempts)


def run_harness(
    *,
    mode: str,
    task: str,
    task_file: str = "",
    files: list[str] | None = None,
    log_file: str = "",
    model: str = "",
    max_input_chars: int = 24000,
    dry_run: bool = False,
    skip_api: bool = False,
    essential: bool = False,
    timeout_sec: int = 45,
) -> HarnessResult:
    if mode not in MODE_BUDGETS:
        raise RuntimeError(f"Unsupported mode: {mode}")
    files = files or []
    model_chain = resolve_model_chain(mode, model)
    resolved_model = model_chain[0]
    packed = pack_context(
        mode=mode,
        task=task,
        task_file=task_file,
        files=files,
        log_file=log_file,
        max_input_chars=max_input_chars,
    )
    if dry_run or skip_api:
        return HarnessResult(
            ok=True,
            mode=mode,
            model=resolved_model,
            model_chain=model_chain,
            skipped=True,
            packed_context=packed,
            usage=budget_status(),
        )
    api_key, key_source = load_api_key()
    if not api_key:
        return HarnessResult(
            ok=True,
            mode=mode,
            model=resolved_model,
            model_chain=model_chain,
            skipped=True,
            error="missing_api_key",
            packed_context=packed,
            usage=budget_status(),
        )
    try:
        resolved_model, response, usage, attempts = call_openrouter_with_fallback(
            mode=mode,
            model_chain=model_chain,
            packed_context=packed,
            api_key=api_key,
            essential=essential,
            timeout_sec=timeout_sec,
        )
    except OpenRouterAllModelsFailed as exc:
        return HarnessResult(
            ok=False,
            mode=mode,
            model=resolved_model,
            model_chain=model_chain,
            error="all_models_failed",
            packed_context=packed,
            usage=budget_status(),
            attempts=exc.attempts,
        )
    usage["key_source"] = key_source
    usage["budget"] = budget_status()
    return HarnessResult(
        ok=True,
        mode=mode,
        model=resolved_model,
        model_chain=model_chain,
        response=response,
        usage=usage,
        attempts=attempts,
    )


def list_models(timeout_sec: int = 30) -> dict[str, Any]:
    api_key, key_source = load_api_key()
    if not api_key:
        return {"ok": False, "error": "missing_api_key", "key_source": key_source, "models": []}
    request = urllib.request.Request(MODELS_URL, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        return {"ok": False, "error": f"OpenRouter HTTP {exc.code}: {_redact_text(detail)}", "models": []}
    free_models: list[dict[str, Any]] = []
    for item in data.get("data", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "")
        if not model_id.endswith(":free"):
            continue
        supported = item.get("supported_parameters", [])
        free_models.append(
            {
                "id": model_id,
                "context_length": item.get("context_length", 0),
                "supports_tools": isinstance(supported, list) and "tools" in supported,
                "supported_parameters": supported,
            }
        )
    free_models.sort(key=lambda model: (not model["supports_tools"], str(model["id"])))
    return {"ok": True, "key_source": key_source, "models": free_models}


def _result_to_dict(result: HarnessResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "mode": result.mode,
        "model": result.model,
        "model_chain": result.model_chain,
        "skipped": result.skipped,
        "error": result.error,
        "attempts": result.attempts,
        "packed_context": result.packed_context,
        "response_boundary": {
            "begin": "=== openrouter subagent response begin ===",
            "response": result.response,
            "end": "=== openrouter subagent response end ===",
        } if result.response is not None else None,
        "usage": result.usage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenRouter subagent harness for newauto.")
    parser.add_argument("--mode", choices=sorted(MODE_BUDGETS), default="review")
    parser.add_argument("--task", default="")
    parser.add_argument("--task-file", default="")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--log-file", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--max-input-chars", type=int, default=24000)
    parser.add_argument("--timeout-sec", type=int, default=45)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--essential", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--budget-status", action="store_true")
    args = parser.parse_args()

    if args.budget_status:
        print(json.dumps(budget_status(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.list_models:
        payload = list_models(timeout_sec=args.timeout_sec)
        print(json.dumps(redact(payload), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 1
    if not args.task and not args.task_file:
        print("Either --task or --task-file is required.", file=sys.stderr)
        return 2
    try:
        result = run_harness(
            mode=args.mode,
            task=args.task,
            task_file=args.task_file,
            files=list(args.files),
            log_file=args.log_file,
            model=args.model,
            max_input_chars=args.max_input_chars,
            dry_run=args.dry_run,
            skip_api=args.skip_api,
            essential=args.essential,
            timeout_sec=args.timeout_sec,
        )
    except Exception as exc:
        payload = {"ok": False, "error": _redact_text(f"{type(exc).__name__}: {exc}")}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    payload = cast(dict[str, Any], redact(_result_to_dict(result)))
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ok={payload.get('ok')} mode={payload.get('mode')} model={payload.get('model')}")
        if payload.get("model_chain"):
            print(f"model_chain={payload.get('model_chain')}")
        if payload.get("error"):
            print(f"error={payload.get('error')}")
        if payload.get("attempts"):
            print(f"attempts={json.dumps(payload.get('attempts'), ensure_ascii=False)}")
        if payload.get("response_boundary"):
            print(json.dumps(payload.get("response_boundary"), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
