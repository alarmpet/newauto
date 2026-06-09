import re


MOJIBAKE_MARKERS = (
    "\ufffd",
    "\uFFFD",
    "\u00c3",
    "\u00ec",
    "\u00ed",
    "\u00eb",
    "\u00ea",
    "\ucc59",
    "\ucc58",
    "\ucc60",
    "\uf9e7",
    "\uf9e8",
    "\u5360",
)


def looks_mojibake(text: str) -> bool:
    if not text:
        return False
    marker_hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    if marker_hits >= 2:
        return True
    suspicious_question_runs = len(re.findall(r"\?{2,}", text))
    if suspicious_question_runs >= 2:
        return True
    if suspicious_question_runs >= 1 and re.search(r"[\u3130-\u318f\uac00-\ud7a3\uf900-\ufaff]", text):
        return True
    hangul_count = len(re.findall(r"[\uac00-\ud7a3]", text))
    cjk_compat_count = len(re.findall(r"[\uf900-\ufaff]", text))
    if cjk_compat_count >= 3 and cjk_compat_count > hangul_count:
        return True
    if cjk_compat_count >= 1 and suspicious_question_runs >= 1:
        return True
    return False


def any_mojibake(values: list[str]) -> bool:
    return any(looks_mojibake(value) for value in values)
