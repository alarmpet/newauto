import unittest

from app.services.literal_simile import extract_literal_simile


class LiteralSimileTests(unittest.TestCase):
    def test_extract_bisut_pattern(self) -> None:
        sentence = "그 감각은 모래 위를 달리는 일과 비슷합니다."
        extracted = extract_literal_simile(sentence)
        self.assertTrue(extracted)

    def test_extract_cheoreom_pattern(self) -> None:
        sentence = "오늘의 피로는 젖은 옷을 입고 걷는 것처럼 느껴집니다."
        extracted = extract_literal_simile(sentence)
        self.assertTrue(extracted)

    def test_extract_macheo_pattern(self) -> None:
        sentence = "마치 작은 방 안에 시계가 여러 개 울리는 것 같았습니다."
        extracted = extract_literal_simile(sentence)
        self.assertTrue(extracted)

    def test_skip_unrelated_sentence(self) -> None:
        self.assertEqual(extract_literal_simile("우리는 오늘 조금 더 천천히 생각합니다."), "")


if __name__ == "__main__":
    unittest.main()
