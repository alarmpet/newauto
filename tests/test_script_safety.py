import unittest

from app.services.script_safety import copy_risk_score, detect_long_quotes


class ScriptSafetyTests(unittest.TestCase):
    def test_copy_risk_score_high_for_verbatim_copy(self) -> None:
        source = "이 문장은 기사 원문 그대로입니다. 그대로 길게 이어집니다."
        self.assertGreater(copy_risk_score(source, source), 0.5)

    def test_copy_risk_score_low_for_paraphrase(self) -> None:
        source = "정부는 오늘 새로운 정책 초안을 공개하고 세부 추진 일정을 설명했습니다."
        draft = "오늘 공개된 정책 초안과 향후 일정이 함께 소개됐다는 점을 중심으로 정리한 대본입니다."
        self.assertLess(copy_risk_score(source, draft), 0.5)

    def test_detect_long_quotes_returns_matching_run(self) -> None:
        source = "이 구절은 기사 본문에서 길게 이어지는 문장으로 사용됩니다."
        draft = "도입 뒤에 이 구절은 기사 본문에서 길게 이어지는 문장으로 사용됩니다. 를 그대로 썼습니다."
        matches = detect_long_quotes(source, draft, min_run=15)
        self.assertTrue(matches)
