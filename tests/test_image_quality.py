import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from app.services.image_quality import analyze_image_quality


class ImageQualityTests(unittest.TestCase):
    def test_simple_diagram_flags_tiny_icon_grid(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "grid.png"
            image = Image.new("RGB", (768, 432), "white")
            draw = ImageDraw.Draw(image)
            for y in range(20, 420, 40):
                for x in range(20, 740, 40):
                    draw.rectangle([x, y, x + 18, y + 12], outline="black", fill="white")
                    draw.line([x + 4, y + 4, x + 14, y + 8], fill="black")
            image.save(path)

            result = analyze_image_quality(path, style_mode="simple_diagram")

        self.assertIn("TINY_ICON_GRID", result["issue_codes"])
        self.assertIn("GENERIC_DASHBOARD_LAYOUT", result["issue_codes"])

    def test_simple_diagram_rewards_large_subject(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "subject.png"
            image = Image.new("RGB", (768, 432), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse([250, 90, 520, 360], outline="black", width=10, fill=(230, 245, 255))
            draw.line([384, 110, 384, 340], fill="black", width=8)
            image.save(path)

            result = analyze_image_quality(path, style_mode="simple_diagram")

        self.assertNotIn("DOMINANT_SUBJECT_TOO_SMALL", result["issue_codes"])
        self.assertGreater(result["components"]["diagram_subject_area"], 0.0)

    def test_editorial_science_flags_tiny_subject(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "small_subject.png"
            image = Image.new("RGB", (1024, 576), (210, 210, 200))
            draw = ImageDraw.Draw(image)
            draw.rectangle([500, 280, 520, 292], fill=(60, 60, 60))
            image.save(path)

            result = analyze_image_quality(path, style_mode="editorial_science")

        self.assertIn("EDITORIAL_SUBJECT_TOO_SMALL", result["issue_codes"])
        self.assertIn("editorial_subject_area", result["components"])

    def test_food_trend_editorial_rewards_purple_product_subject(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ube.png"
            image = Image.new("RGB", (1024, 576), (248, 241, 232))
            draw = ImageDraw.Draw(image)
            draw.rectangle([120, 320, 900, 500], fill=(214, 192, 168), outline=(110, 90, 74), width=4)
            draw.rectangle([290, 180, 720, 420], fill=(142, 92, 188), outline="black", width=6)
            draw.ellipse([350, 210, 660, 360], fill=(173, 120, 222), outline="black", width=5)
            image.save(path)

            result = analyze_image_quality(path, style_mode="food_trend_editorial")

        self.assertNotIn("FOOD_TREND_PURPLE_ACCENT_WEAK", result["issue_codes"])
        self.assertNotIn("FOOD_TREND_SUBJECT_TOO_SMALL", result["issue_codes"])
        self.assertGreater(result["components"]["food_purple_accent"], 0.0)
        self.assertGreater(result["components"]["food_subject_area"], 0.0)

    def test_food_trend_editorial_flags_empty_neutral_interior(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty_room.png"
            image = Image.new("RGB", (1024, 576), (233, 228, 220))
            draw = ImageDraw.Draw(image)
            draw.rectangle([0, 360, 1024, 576], fill=(220, 214, 205))
            draw.rectangle([440, 250, 590, 360], fill=(226, 221, 214), outline=(210, 205, 198), width=2)
            image.save(path)

            result = analyze_image_quality(path, style_mode="food_trend_editorial")

        self.assertIn("FOOD_TREND_PURPLE_ACCENT_WEAK", result["issue_codes"])
        self.assertIn("FOOD_TREND_EMPTY_INTERIOR", result["issue_codes"])

    def test_editorial_symbolic_flags_flat_shape_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "flat_shape.png"
            image = Image.new("RGB", (1024, 576), (238, 238, 235))
            draw = ImageDraw.Draw(image)
            draw.rectangle([450, 230, 575, 350], fill=(225, 225, 225), outline=(210, 210, 210), width=2)
            image.save(path)

            result = analyze_image_quality(path, style_mode="editorial_symbolic")

        self.assertIn("EDITORIAL_FLAT_SHAPE_ONLY", result["issue_codes"])
        self.assertIn("editorial_flat_shape_penalty", result["components"])

    def test_editorial_symbolic_rewards_scene_with_clear_subject(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "editorial_scene.png"
            image = Image.new("RGB", (1024, 576), (218, 224, 224))
            draw = ImageDraw.Draw(image)
            draw.rectangle([0, 390, 1024, 576], fill=(172, 160, 145))
            draw.rectangle([90, 80, 930, 390], fill=(199, 205, 207), outline=(90, 94, 96), width=5)
            draw.ellipse([390, 150, 650, 385], fill=(90, 180, 220), outline=(20, 50, 70), width=8)
            draw.rectangle([250, 275, 760, 330], fill=(190, 42, 36), outline=(70, 25, 20), width=5)
            for x in range(120, 900, 90):
                draw.line([x, 90, x + 35, 380], fill=(110, 118, 120), width=2)
            for y in range(110, 360, 42):
                draw.line([110, y, 910, y + 16], fill=(126, 132, 134), width=2)
            for x in range(140, 860, 80):
                draw.rectangle([x, 420, x + 42, 480], fill=(126, 118, 105), outline=(80, 74, 66), width=2)
            image.save(path)

            result = analyze_image_quality(path, style_mode="editorial_symbolic")

        self.assertNotIn("EDITORIAL_SUBJECT_TOO_SMALL", result["issue_codes"])
        self.assertGreater(result["components"]["editorial_subject_area"], 0.0)
        self.assertGreater(result["components"]["editorial_scene_detail"], 0.0)


if __name__ == "__main__":
    unittest.main()
