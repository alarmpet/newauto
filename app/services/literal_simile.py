import re

_MACHEO_PATTERN = re.compile(
    r"\ub9c8\uce58\s+(.+?)(?:\uac83\s+\uac19|\ucc98\ub7fc|\uac19\uc774|\ub4ef)",
    re.IGNORECASE,
)
_BISUT_PATTERN = re.compile(
    r"(.+?)(?:\uacfc|\uc640)\s*\ube44\uc2b7",
    re.IGNORECASE,
)
_GATEUN_PATTERN = re.compile(
    r"(.+?)\s*\uac19(?:\uc740|\uc774)",
    re.IGNORECASE,
)
_CHEOREOM_PATTERN = re.compile(r"(.+?)\s*\ucc98\ub7fc", re.IGNORECASE)
_DEUT_PATTERN = re.compile(r"(.+?)\s*\ub4ef", re.IGNORECASE)
_PATTERNS = (
    _MACHEO_PATTERN,
    _BISUT_PATTERN,
    _GATEUN_PATTERN,
    _CHEOREOM_PATTERN,
    _DEUT_PATTERN,
)


def extract_literal_simile(sentence: str) -> str:
    compact = re.sub(r"\s+", " ", sentence).strip()
    if not compact:
        return ""
    for pattern in _PATTERNS:
        match = pattern.search(compact)
        if match is None:
            continue
        phrase = re.sub(r"\s+", " ", match.group(1)).strip(" ,.")
        if 2 <= len(phrase) <= 30:
            return phrase
    return ""
