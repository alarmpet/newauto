from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT_DIR / "storage" / "agent_memory" / "tool_catalog.json"

FIXTURES: list[dict[str, object]] = [
    {"task": "temp_prompts prompt_001 prompt_002 prompt_003 txt files generate 3 standalone images", "expected": ["generate_prompt_file_images"]},
    {"task": "Naver News URL http://n.news.naver.com/mnews/article/011/0004620376 HPSL shorts Flow TTS render workflow start", "expected": ["start_video_workflow"]},
    {"task": "Use Playwright to extract Naver article body with #dic_area and document.querySelector", "expected": ["browser_evaluate"]},
    {"task": "browser_extract_content failed Tool not found; choose valid Playwright DOM extraction tool", "expected": ["browser_evaluate", "browser_snapshot"]},
    {"task": "비트코인 쇼츠 새 워크플로우 시작", "expected": ["start_video_workflow"]},
    {"task": "진행해 다음 단계로 넘어가", "expected": ["continue_video_workflow"]},
    {"task": "방금 timeout난 이유를 진단해", "expected": ["diagnose_runtime", "forensic_diagnose"]},
    {"task": "Flow 2번 문장 이미지를 다운로드하고 첨부해", "expected": ["attach_latest_flow_downloads"]},
    {"task": "Playwright 공식 문서 웹검색해", "expected": ["search_web"]},
    {"task": "포트 9001 어떤 프로세스인지 PowerShell로 확인해", "expected": ["run_powershell"]},
    {"task": "FastAPI 공식 문서 기준으로 사용법 확인", "expected": ["get-library-docs"]},
    {"task": "복잡한 업그레이드 계획을 단계로 나눠", "expected": ["sequentialthinking"]},
    {"task": "저장된 선호나 절차 기억을 확인해", "expected": ["read_graph"]},
    {"task": "로컬 설정 파일 내용을 읽어봐", "expected": ["read_file"]},
]


def _load_catalog() -> list[dict[str, Any]]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [item for item in payload if isinstance(item, dict)]


def _score(task: str, item: dict[str, Any]) -> int:
    task_lower = task.casefold()
    fields: list[str] = [
        str(item.get("name") or ""),
        str(item.get("server") or ""),
        str(item.get("purpose") or ""),
    ]
    fields.extend(str(value) for value in item.get("when_to_use", []) if isinstance(value, str))
    score = 0
    for field in fields:
        for token in field.casefold().replace("_", " ").split():
            if len(token) >= 3 and token in task_lower:
                score += 2
        if field.casefold() in task_lower:
            score += 5
    for keyword in item.get("when_to_use", []):
        if isinstance(keyword, str) and keyword.casefold() in task_lower:
            score += 10
    return score


def rank_tools(task: str, catalog: list[dict[str, Any]], top_k: int) -> list[str]:
    ranked = sorted(
        catalog,
        key=lambda item: (_score(task, item), str(item.get("name") or "")),
        reverse=True,
    )
    return [str(item.get("name") or "") for item in ranked[:top_k]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate keyword-based tool catalog ranking.")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    catalog = _load_catalog()
    rows: list[dict[str, object]] = []
    hits = 0
    for fixture in FIXTURES:
        task = str(fixture["task"])
        expected = [str(item) for item in fixture["expected"]]
        predicted = rank_tools(task, catalog, args.top_k)
        hit = any(item in predicted for item in expected)
        hits += int(hit)
        rows.append({"task": task, "expected": expected, "predicted": predicted, "hit": hit})
    result = {
        "top_k": args.top_k,
        "total": len(rows),
        "hits": hits,
        "hit_rate": hits / max(1, len(rows)),
        "rows": rows,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"top_k={args.top_k} hits={hits}/{len(rows)} hit_rate={result['hit_rate']:.2%}")
        for row in rows:
            print(f"- {'OK' if row['hit'] else 'MISS'} {row['task']} -> {row['predicted']}")
    return 0 if result["hit_rate"] >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
