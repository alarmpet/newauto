from pathlib import Path

from app.services.text_health import looks_mojibake


def test_static_ui_exposes_operator_console_controls():
    index = Path("app/static/index.html").read_text(encoding="utf-8")
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")

    for marker in (
        "stage-manifest-panel",
        "prompt-preview-panel",
        "image-qa-panel",
        "tts-consistency-panel",
        "render-preflight-panel",
        "retry-stage",
        "resume-autopilot",
        "cancel-autopilot",
    ):
        assert marker in index or marker in app_js


def test_static_ui_fetches_and_renders_workflow_status():
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")

    assert "workflow-stage-cards" in app_js
    assert "refreshWorkflowStatus" in app_js
    assert "fetch(`/api/projects/${currentProject.id}/workflow-status`)" in app_js


def test_static_ui_contains_render_blocker_controls():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    app_js = Path("app/static/app.js").read_text(encoding="utf-8")

    assert "render-blockers-panel" in html
    assert "renderBlockers" in app_js
    assert "blocking_checks" in app_js
    assert "Render blocked" in html


def test_static_ui_has_no_mojibake_strings():
    for path in (Path("app/static/index.html"), Path("app/static/app.js"), Path("app/static/style.css")):
        assert not looks_mojibake(path.read_text(encoding="utf-8"))
