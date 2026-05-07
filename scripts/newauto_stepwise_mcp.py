from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server.fastmcp import FastMCP
from scripts import newauto_mcp as core


STEPWISE_INSTRUCTIONS = """
You are the minimal newauto-stepwise MCP server for LM Studio + Gemma4.

Available tools are only:
- diagnose_runtime(project_id="")
- start_video_workflow(keyword_or_url, title="", target_minutes=1, tone="설명형")
- continue_video_workflow(project_id="")
- check_assets(project_id="")
- generate_one_image(project_id="", sentence_number=0)

Rules:
- After reconnect or any confusing state, call diagnose_runtime first.
- For a new video workflow, call start_video_workflow exactly once.
- When the user says 진행, ok, 다음, or continue, call continue_video_workflow exactly once.
- Never call more than one workflow-advancing tool for one user approval.
- Never mention or invent legacy tool names such as start_hpsl_flow_workflow,
  finish_hpsl_flow_workflow, make_hpsl_flow_short_video, open_flow, or
  continue_stepwise_hpsl_video_workflow. They are intentionally not available here.
- If a tool call appears to fail or timeout, call diagnose_runtime next and compare
  the saved project state before explaining anything.
- Never explain a timeout as image generation overload, network overload, or server
  overload unless the tool output explicitly says that.
- Reply in concise Korean. After a successful step, report the completed step and
  ask the user to answer 진행, ok, or 다음 before continuing.
"""


mcp = FastMCP(
    name="newauto-stepwise",
    log_level="ERROR",
    instructions=STEPWISE_INSTRUCTIONS,
)


def _latest_project_id() -> str:
    try:
        state = core._load_stepwise_state("")
    except Exception:
        return ""
    return str(state.get("project_id") or "").strip()


def _resolve_project_id(project_id: str) -> str:
    pid = project_id.strip()
    if pid:
        return pid
    return _latest_project_id()


def _first_missing_sentence(project_id: str) -> int:
    project = core._json_request("GET", f"/api/projects/{project_id}", timeout=30)
    _, _, missing = core._project_sentence_asset_status(project)
    if missing:
        return int(missing[0])
    return 1


def _wrapper_header(resolved_project_id: str) -> str:
    visible_tools = (
        "diagnose_runtime, start_video_workflow, continue_video_workflow, "
        "check_assets, generate_one_image"
    )
    return (
        "=== newauto-stepwise wrapper ===\n"
        f"wrapper_script: {Path(__file__).resolve()}\n"
        f"visible_tools: {visible_tools}\n"
        f"resolved_project_id: {resolved_project_id or 'none'}"
    )


@mcp.tool()
def diagnose_runtime(project_id: str = "") -> str:
    """Check MCP identity, API health, latest workflow state, and asset coverage."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    diagnosis = core.diagnose_newauto_runtime(pid)
    return f"{_wrapper_header(pid)}\n\n{diagnosis}"


@mcp.tool()
def start_video_workflow(
    keyword_or_url: str,
    title: str = "",
    target_minutes: int = 1,
    tone: str = "설명형",
) -> str:
    """Start one approval-gated HPSL video workflow from a keyword or URL."""
    core._configure_stdout()
    message = core.start_stepwise_hpsl_video_workflow(
        keyword_or_url=keyword_or_url,
        title=title,
        target_minutes=target_minutes,
        tone=tone,
    )
    pid = _latest_project_id()
    return f"{_wrapper_header(pid)}\n\n{message}"


@mcp.tool()
def continue_video_workflow(project_id: str = "") -> str:
    """Run exactly one next workflow step, then stop for user approval."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    if not pid:
        return (
            f"{_wrapper_header(pid)}\n\n"
            "진행할 프로젝트를 찾지 못했어. 먼저 diagnose_runtime으로 상태를 확인하거나 "
            "start_video_workflow로 새 워크플로우를 시작해."
        )
    message = core.continue_stepwise_hpsl_video_workflow(pid)
    return f"{_wrapper_header(pid)}\n\n{message}"


@mcp.tool()
def check_assets(project_id: str = "") -> str:
    """Check Flow sentence image coverage without advancing the workflow."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    if not pid:
        return (
            f"{_wrapper_header(pid)}\n\n"
            "확인할 프로젝트를 찾지 못했어. 먼저 diagnose_runtime으로 상태를 확인해."
        )
    message = core.flow_asset_coverage(pid)
    return f"{_wrapper_header(pid)}\n\n{message}"


@mcp.tool()
def generate_one_image(project_id: str = "", sentence_number: int = 0) -> str:
    """Diagnostic tool: click Generate for one missing Flow sentence only."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    if not pid:
        return (
            f"{_wrapper_header(pid)}\n\n"
            "이미지를 생성할 프로젝트를 찾지 못했어. 먼저 diagnose_runtime으로 상태를 확인해."
        )
    target_sentence = sentence_number if sentence_number > 0 else _first_missing_sentence(pid)
    message = core.flow_generate_one_sentence(pid, target_sentence)
    return f"{_wrapper_header(pid)}\n\n{message}"


def main() -> None:
    core._configure_stdout()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
