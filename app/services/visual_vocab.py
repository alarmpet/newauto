import json
from pathlib import Path


def load_domain_vocab(domain: str) -> dict[str, object]:
    target = Path("storage/visual_vocab") / f"{domain}.json"
    if not target.exists():
        return {"domain": domain, "terms": []}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"domain": domain, "terms": []}
    if not isinstance(payload, dict):
        return {"domain": domain, "terms": []}
    return payload


def domain_global_avoid(vocab: dict[str, object]) -> list[str]:
    raw_values = vocab.get("global_avoid")
    if not isinstance(raw_values, list):
        return []
    values: list[str] = []
    for item in raw_values:
        if isinstance(item, str):
            normalized = item.strip()
            if normalized and normalized not in values:
                values.append(normalized)
    return values
