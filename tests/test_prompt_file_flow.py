from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.flow_browser_automation import _is_prompt_input_meta, _prompt_file_entries


def test_prompt_file_entries_use_exact_prompt_files_in_sorted_order() -> None:
    with TemporaryDirectory() as temp_dir:
        prompt_dir = Path(temp_dir)
        (prompt_dir / "prompt_002.txt").write_text("sunny beach", encoding="utf-8")
        (prompt_dir / "prompt_001.txt").write_text("walking cat", encoding="utf-8")
        (prompt_dir / "prompt_003.txt").write_text("big smiling dog", encoding="utf-8")
        (prompt_dir / "dog_positive.txt").write_text("not part of this batch", encoding="utf-8")

        entries = _prompt_file_entries(prompt_dir, "prompt_*.txt", limit=0)

    assert [entry["sentence_idx"] for entry in entries] == [0, 1, 2]
    assert [entry["prompt"] for entry in entries] == ["walking cat", "sunny beach", "big smiling dog"]
    assert all("dog_positive" not in str(entry["source"]) for entry in entries)


def test_prompt_file_entries_limit_is_exact_count() -> None:
    with TemporaryDirectory() as temp_dir:
        prompt_dir = Path(temp_dir)
        for index in range(1, 5):
            (prompt_dir / f"prompt_{index:03d}.txt").write_text(f"prompt {index}", encoding="utf-8")

        entries = _prompt_file_entries(prompt_dir, "prompt_*.txt", limit=3)

    assert len(entries) == 3
    assert [entry["prompt"] for entry in entries] == ["prompt 1", "prompt 2", "prompt 3"]


def test_prompt_input_meta_rejects_flow_search_fields() -> None:
    assert not _is_prompt_input_meta(
        {
            "tag": "input",
            "type": "text",
            "placeholder": "애셋 검색",
            "aria": "",
            "title": "",
            "role": "textbox",
            "width": 240,
            "height": 36,
        }
    )
    assert not _is_prompt_input_meta(
        {
            "tag": "input",
            "type": "text",
            "placeholder": "Search",
            "aria": "search",
            "title": "",
            "role": "textbox",
            "width": 240,
            "height": 36,
        }
    )


def test_prompt_input_meta_accepts_real_prompt_boxes() -> None:
    assert _is_prompt_input_meta(
        {
            "tag": "div",
            "type": "",
            "placeholder": "",
            "aria": "Prompt",
            "title": "",
            "role": "textbox",
            "contenteditable": "true",
            "width": 520,
            "height": 96,
        }
    )
