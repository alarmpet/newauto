import json
import unittest
from pathlib import Path


class EssayVocabTests(unittest.TestCase):
    def test_essay_vocab_has_global_avoid(self) -> None:
        payload = json.loads(Path("storage/visual_vocab/essay.json").read_text(encoding="utf-8"))
        global_avoid = payload.get("global_avoid", [])
        self.assertIn("car", global_avoid)
        self.assertIn("vehicle", global_avoid)
        self.assertIn("traffic", global_avoid)

    def test_no_vehicle_terms_in_essay_metaphor_examples(self) -> None:
        payload = json.loads(Path("storage/visual_vocab/essay.json").read_text(encoding="utf-8"))
        terms = payload.get("terms", [])
        examples: list[str] = []
        for item in terms:
            if isinstance(item, dict):
                examples.extend(example for example in item.get("metaphor_examples", []) if isinstance(example, str))
        lowered = " | ".join(example.lower() for example in examples)
        self.assertNotIn("busy street", lowered)
        self.assertNotIn("city morning", lowered)
        self.assertNotIn("road fork", lowered)


if __name__ == "__main__":
    unittest.main()
