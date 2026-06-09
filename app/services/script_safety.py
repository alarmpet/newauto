import difflib


def copy_risk_score(source: str, draft: str) -> float:
    if not source or not draft:
        return 0.0
    matcher = difflib.SequenceMatcher(None, source, draft, autojunk=False)
    longest = matcher.find_longest_match(0, len(source), 0, len(draft))
    return longest.size / max(len(draft), 1)


def detect_long_quotes(source: str, draft: str, *, min_run: int = 25) -> list[str]:
    if not source or not draft:
        return []
    matcher = difflib.SequenceMatcher(None, source, draft, autojunk=False)
    return [
        draft[match.b:match.b + match.size]
        for match in matcher.get_matching_blocks()
        if match.size >= min_run
    ]
