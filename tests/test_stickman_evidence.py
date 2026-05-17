import json
import unittest
from typing import cast

from app import db
from app.services.stickman_evidence import build_stickman_evidence_bundle, create_stickman_business_project
from app.services.stickman_layout_sketch import build_stickman_layout_sketches


class StickmanEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project_ids: list[str] = []

    def tearDown(self) -> None:
        for project_id in self.project_ids:
            db.delete_project(project_id)

    def test_build_stickman_evidence_bundle_writes_lora_on_off_manifests(self) -> None:
        project = create_stickman_business_project(
            title="stickman evidence test",
            sentences=[
                "Nvidia strategy turns GPU sales into a developer ecosystem engine.",
                "Power grid infrastructure becomes a bottleneck for AI data center growth.",
            ],
        )
        self.project_ids.append(project["id"])

        paths = build_stickman_evidence_bundle(project)

        self.assertTrue(paths["evidence_dir"].exists())
        self.assertTrue(paths["prompts_on"].exists())
        self.assertTrue(paths["prompts_off"].exists())
        self.assertTrue(paths["review"].exists())

        prompts_on = json.loads(paths["prompts_on"].read_text(encoding="utf-8"))
        prompts_off = json.loads(paths["prompts_off"].read_text(encoding="utf-8"))
        self.assertEqual(prompts_on["source"], "stickman_business_evidence_lora_on")
        self.assertEqual(prompts_off["source"], "stickman_business_evidence_lora_off")
        on_items = cast(list[dict[str, object]], prompts_on["prompts"])
        off_items = cast(list[dict[str, object]], prompts_off["prompts"])
        self.assertEqual(len(on_items), 2)
        self.assertEqual(len(off_items), 2)
        self.assertEqual(on_items[0]["template_id"], "txt2img_sdxl_stickman_lora")
        self.assertGreater(float(on_items[0]["lora_strength"]), 0.0)
        self.assertEqual(off_items[0]["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(off_items[0]["lora_strength"], 0.0)
        self.assertNotIn("Stick figure", str(off_items[0]["positive_prompt"]))
        self.assertNotIn("Flipchartvisu", str(off_items[0]["positive_prompt"]))

        review = json.loads(paths["review"].read_text(encoding="utf-8"))
        self.assertEqual(review["status"], "pending_generation")
        self.assertIn("fake_or_gibberish_text", review["failure_categories"])
        self.assertEqual(len(review["items"]), 2)

    def test_build_stickman_layout_sketches_writes_nonblank_guides(self) -> None:
        project = create_stickman_business_project(
            title="stickman layout sketch test",
            sentences=["Power grid infrastructure becomes a bottleneck for AI data center growth."],
        )
        self.project_ids.append(project["id"])

        sketches = build_stickman_layout_sketches(
            project,
            template_keys=["infrastructure_bottleneck"],
            width=384,
            height=216,
        )

        self.assertEqual(len(sketches), 1)
        path = sketches[0]["path"]
        self.assertTrue(path.endswith("infrastructure_bottleneck_layout_sketch.png"))

        from PIL import Image

        with Image.open(path) as image:
            self.assertEqual(image.size, (384, 216))
            colors = image.convert("RGB").getcolors(maxcolors=1000000)
        self.assertIsNotNone(colors)
        self.assertGreater(len(colors or []), 3)


if __name__ == "__main__":
    unittest.main()
