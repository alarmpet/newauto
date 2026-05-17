import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from ..config import BRAVE_FREE_MONTHLY_LIMIT, BRAVE_USAGE_PATH, LLM_PROVIDER, PROVIDER_USAGE_PATH
from ..types import UsageRecord


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _empty_record(provider: str, *, day_limit: int | None, month_limit: int | None) -> UsageRecord:
    return {
        "provider": provider,
        "day_count": 0,
        "month_count": 0,
        "day_limit": day_limit,
        "month_limit": month_limit,
        "last_day_reset": _today_utc(),
        "last_month_reset": _month_utc(),
    }


def _read_provider_payload(path: Path | None = None) -> dict[str, object]:
    target = path or PROVIDER_USAGE_PATH
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_provider_payload(payload: dict[str, object], path: Path | None = None) -> None:
    target = path or PROVIDER_USAGE_PATH
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_legacy_brave_usage(path: Path | None = None) -> tuple[str, int]:
    target = path or BRAVE_USAGE_PATH
    if not target.exists():
        return _month_utc(), 0
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _month_utc(), 0
    month = payload.get("month")
    count = payload.get("count")
    if not isinstance(month, str) or not isinstance(count, int):
        return _month_utc(), 0
    if month != _month_utc():
        return _month_utc(), 0
    return month, count


def _write_legacy_brave_usage(month: str, count: int, path: Path | None = None) -> None:
    target = path or BRAVE_USAGE_PATH
    target.write_text(
        json.dumps({"month": month, "count": count}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalize_record(record: UsageRecord, *, day_limit: int | None, month_limit: int | None) -> UsageRecord:
    normalized: UsageRecord = {
        "provider": record["provider"],
        "day_count": int(record["day_count"]),
        "month_count": int(record["month_count"]),
        "day_limit": day_limit if day_limit is not None else record["day_limit"],
        "month_limit": month_limit if month_limit is not None else record["month_limit"],
        "last_day_reset": record["last_day_reset"],
        "last_month_reset": record["last_month_reset"],
    }
    if normalized["last_day_reset"] != _today_utc():
        normalized["day_count"] = 0
        normalized["last_day_reset"] = _today_utc()
    if normalized["last_month_reset"] != _month_utc():
        normalized["month_count"] = 0
        normalized["last_month_reset"] = _month_utc()
    return normalized


def _record_from_payload(
    provider: str,
    payload: object,
    *,
    day_limit: int | None,
    month_limit: int | None,
) -> UsageRecord:
    if not isinstance(payload, dict):
        return _empty_record(provider, day_limit=day_limit, month_limit=month_limit)
    day_count = payload.get("day_count")
    month_count = payload.get("month_count")
    last_day_reset = payload.get("last_day_reset")
    last_month_reset = payload.get("last_month_reset")
    if not isinstance(day_count, int) or not isinstance(month_count, int):
        return _empty_record(provider, day_limit=day_limit, month_limit=month_limit)
    if not isinstance(last_day_reset, str) or not isinstance(last_month_reset, str):
        return _empty_record(provider, day_limit=day_limit, month_limit=month_limit)
    raw_day_limit = payload.get("day_limit")
    raw_month_limit = payload.get("month_limit")
    record: UsageRecord = {
        "provider": provider,
        "day_count": day_count,
        "month_count": month_count,
        "day_limit": raw_day_limit if isinstance(raw_day_limit, int) else None,
        "month_limit": raw_month_limit if isinstance(raw_month_limit, int) else None,
        "last_day_reset": last_day_reset,
        "last_month_reset": last_month_reset,
    }
    return _normalize_record(record, day_limit=day_limit, month_limit=month_limit)


def get_provider_usage(
    provider: str,
    *,
    day_limit: int | None = None,
    month_limit: int | None = None,
    path: Path | None = None,
    legacy_path: Path | None = None,
) -> UsageRecord:
    payload = _read_provider_payload(path)
    if provider == "brave_search" and provider not in payload:
        legacy_month, legacy_count = _read_legacy_brave_usage(legacy_path)
        return _normalize_record(
            {
                "provider": provider,
                "day_count": 0,
                "month_count": legacy_count,
                "day_limit": day_limit,
                "month_limit": month_limit,
                "last_day_reset": _today_utc(),
                "last_month_reset": legacy_month,
            },
            day_limit=day_limit,
            month_limit=month_limit,
        )
    return _record_from_payload(provider, payload.get(provider), day_limit=day_limit, month_limit=month_limit)


def reserve_provider_usage(
    provider: str,
    *,
    amount: int = 1,
    day_limit: int | None = None,
    month_limit: int | None = None,
    path: Path | None = None,
    legacy_path: Path | None = None,
) -> UsageRecord:
    if amount < 1:
        raise HTTPException(400, "사용량 증분은 1 이상이어야 합니다.")
    record = get_provider_usage(
        provider,
        day_limit=day_limit,
        month_limit=month_limit,
        path=path,
        legacy_path=legacy_path,
    )
    new_day_count = record["day_count"] + amount
    new_month_count = record["month_count"] + amount
    if record["day_limit"] is not None and new_day_count > record["day_limit"]:
        raise HTTPException(429, f"{provider} 일일 사용량 한도를 초과했습니다.")
    if record["month_limit"] is not None and new_month_count > record["month_limit"]:
        raise HTTPException(429, f"{provider} 월간 사용량 한도를 초과했습니다.")
    updated: UsageRecord = {
        "provider": provider,
        "day_count": new_day_count,
        "month_count": new_month_count,
        "day_limit": record["day_limit"],
        "month_limit": record["month_limit"],
        "last_day_reset": record["last_day_reset"],
        "last_month_reset": record["last_month_reset"],
    }
    payload = _read_provider_payload(path)
    payload[provider] = updated
    _write_provider_payload(payload, path)
    if provider == "brave_search":
        _write_legacy_brave_usage(updated["last_month_reset"], updated["month_count"], legacy_path)
    return updated


def list_usage_records(path: Path | None = None) -> list[UsageRecord]:
    providers: list[tuple[str, int | None, int | None]] = [
        ("brave_search", None, BRAVE_FREE_MONTHLY_LIMIT),
        ("comfyui", 100, None),
        (LLM_PROVIDER, 200, None),
        ("external_download", 20, 200),
        ("youtube_upload", 10, 300),
    ]
    return [
        get_provider_usage(provider, day_limit=day_limit, month_limit=month_limit, path=path)
        for provider, day_limit, month_limit in providers
    ]
