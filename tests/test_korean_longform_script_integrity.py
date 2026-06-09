import pytest

from app.services.script_compile import compile_script


def test_compiled_korean_segments_keep_original_normalized_hash_and_source_marker():
    compiled_script, regional_sentences = compile_script(
        "bible_longform",
        "<<intro>>\n안녕하세요.\n<<body>>\n창세기 이야기를 시작합니다.",
    )

    assert "안녕하세요." in compiled_script
    assert regional_sentences[0]["text"] == "안녕하세요."
    assert regional_sentences[0]["original_text"] == "안녕하세요."
    assert regional_sentences[0]["normalized_text"] == "안녕하세요."
    assert regional_sentences[0]["text_hash"]
    assert regional_sentences[0]["source_marker"] == "intro"


def test_compile_script_rejects_mojibake_input():
    with pytest.raises(ValueError, match="mojibake"):
        compile_script("standard", "?덈뀞?섏꽭??")
