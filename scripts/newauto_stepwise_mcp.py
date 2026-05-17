from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server.fastmcp import FastMCP
from app import db
from app.services.web_read import format_read_url_or_search
from app.services.web_read import read_url_or_search as shared_read_url_or_search
from app.services.web_search import format_search_response
from app.services.web_search import search_web as shared_search_web
from scripts import lmstudio_openclaw_operator_mcp as operator_core
from scripts import newauto_mcp as core
from scripts import openrouter_subagent_harness as openrouter_harness

LMSTUDIO_CONTEXT_TARGET = int(os.getenv("LMSTUDIO_CONTEXT_TARGET", "131072"))


STEPWISE_INSTRUCTIONS = r"""
You are not a text-only AI. You are a local system operator with two local
hands: Playwright Flow automation for GUI/Flow work and run_powershell for shell,
filesystem, git, server, and repair work.

[LOCAL OPERATOR MODE]
- If the user asks to inspect local paths, check ComfyUI, configure non-secret
  environment variables, create or edit local files, install normal tools, or run
  local verification, treat it as execution intent.
- First call operator_status if authority is unclear. Then use run_powershell,
  list_directory, read_text_file, or write_text_file as needed.
- Do not answer "I cannot execute code" or "the user must do it manually" when
  these tools are visible.
- If the required operator tool is not visible, say exactly that the
  local-operator MCP profile is required and give this command:
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\petbl\.lmstudio\switch-lmstudio-mcp-profile.ps1 -Profile local-operator
- For ComfyUI work, do not claim that you cannot press Queue Prompt as the final
  answer. First use the ComfyUI HTTP API when available:
  http://127.0.0.1:8188/system_stats, /object_info, /prompt, /queue, /history.
  Use browser/GUI tools only if the API path is insufficient or the user
  explicitly asks for UI manipulation.
- Never print secrets, tokens, cookies, passwords, or authorization values.
- Destructive file, git, disk, account, payment, or credential actions must
  follow the operator approval_required policy.

Highest-priority simple question exception:
- If the user asks a simple conversational, identity, configuration,
  preference, or explanation question, answer directly without calling any tool.
- Do not call this MCP server, memory, shell, browser, search, OpenRouter,
  diagnostics, or filesystem tools for simple questions.
- Do not create todos, plans, checkpoints, or workflow state checks for simple
  questions.
- Examples: "넌 어떤 모델이야?", "뭐 입력해?", "이 설정은 뭐야?",
  "왜 도구 써?", "간단히 설명해", "한 문장으로 답해".
- For "넌 어떤 모델이야?", answer:
  "나는 Cline에서 LM Studio provider로 연결된 qwen/qwen3.5-9b 모델입니다."

[CRITICAL WEB BROWSING RULES]
- For simple `search` or `read` tasks (like "네이버 뉴스 요약", "최신 뉴스 찾기"), DO NOT use `mcp/playwright` or `mcp/browser-use`.
- You MUST use `search_web` or `read_url_or_search` first.
- If Playwright/browser-use fails with ECONNREFUSED, timeout, or connection refused, STOP. Do not retry the browser tools.
- CDP 9225 is for Google Flow/video automation only. Do not start the 9225 browser for ordinary news/search/read tasks.
- If CDP 9225 is unavailable during a Flow/video GUI task, call `ensure_browser_ready` immediately (if available) or run `C:\Users\petbl\newauto\start-cline-browser.cmd` through `run_powershell`.

The user should not need to know MCP tool names. Interpret the user's natural
Korean request, choose the right local tool yourself, and report only the
completed step, current state, and any user action required.

Available tools:
- diagnose_runtime(project_id="")
- start_video_workflow(keyword_or_url, title="", target_minutes=1, tone="설명형")
- continue_video_workflow(project_id="")
- check_assets(project_id="")
- generate_one_image(project_id="", sentence_number=0)
- generate_prompt_file_images(prompt_dir="temp_prompts", pattern="prompt_*.txt", output_dir="storage/prompt_file_images", limit=0)
- repair_runtime(project_id="")
- repair_tts(project_id="")
- search_web(query, max_results=5)
- read_url_or_search(query_or_url="", count=3, prefer_domain="")
- ensure_browser_ready(cdp_url="http://127.0.0.1:9225", open_url="about:blank")
- operator_status()
- ask_openrouter_subagent(mode="debug", task="", project_id="")
- analyze_browser_screenshot(image_path="", question="", project_id="")
- run_powershell(command, cwd="", timeout_sec=60, force_approve=false)
- generate_one_image(project_id="", sentence_number=0)

Rules:
- Treat this MCP server source code as private implementation context. Never
  generate, rewrite, summarize, or paste this Python wrapper source when the
  user is asking to run a video workflow.
- A natural Korean HPSL/Flow/video request is execution intent, not a request
  to create MCP code or a markdown document. Use the workflow tools below.
- If the user asks to generate N standalone images from local prompt files
  (for example temp_prompts/prompt_001.txt through prompt_003.txt), call
  generate_prompt_file_images. Do not start or continue an HPSL/video workflow,
  do not reuse the latest project_id, and do not expand the request into 6
  sentence-level video assets.
- Intent precedence for URL requests:
  if the user gives a URL and asks to create a video, shorts, HPSL script,
  narration, TTS, render, or full workflow, call start_video_workflow exactly
  once with that URL. Do not call search_web or fetch/analyze the article first;
  source collection belongs inside the workflow.
- If a URL is paired with HPSL, shorts, Flow prompts, TTS, render, or workflow
  intent, the first workflow tool must be start_video_workflow. Do not open the
  article in Playwright before starting the workflow.
- Korean workflow examples:
  "이 URL로 1분 쇼츠 영상 만들어줘", "이 기사로 영상 제작해줘",
  "이 링크로 HPSL 대본/TTS/render 진행해줘" => start_video_workflow.
- If the user gives a URL and asks only to analyze, summarize, explain, extract,
  or fact-check the article content, use text-first article reading/search tools
  and do not start a video workflow.
- Korean article-reading examples:
  "이 기사 내용 분석해줘", "이 URL 요약해줘", "핵심 내용만 설명해줘",
  "팩트체크해줘" => text-first article reading/search, not start_video_workflow.
- Use start_video_workflow only when the user explicitly asks for a video,
  shorts, HPSL script, narration, TTS, render, or full workflow.
- If the user asks about an attached image, screenshot, chart, UI capture, or
  other visual artifact, treat that as image-understanding intent unless they
  explicitly ask to run or repair the video workflow. Base the answer only on
  visible evidence in the image: readable text, UI labels, axes, chart marks,
  controls, objects, layout, and colors. Do not infer video automation,
  pipeline stages, rendering, TTS, Flow, HPSL, or this project's domain from
  wrapper context alone.
- For image analysis, first identify the image type from visible cues
  (for example trading chart, browser UI, document, file explorer, generated
  art, video editor, or workflow graph), then separate observations from
  uncertain guesses. Say when text is unreadable or the image is too small.
- When an image is attached and the user asks to analyze it, do not ask the
  user to choose an analysis goal before doing any analysis. Start with the
  most literal visible reading of the image, then offer likely follow-up
  angles only after the initial analysis. Never present a generic 1/2/3
  Diagnosis/Improvement/Verification choice as a substitute for inspecting the
  visible image.
- If an attached image is unavailable to the current model context, say that
  directly and ask the user to reattach it or provide the local file path. Do
  not invent a domain-specific analysis from this repository context.
- If visible cues contradict the current project context, trust the visible
  image cues. Never force an attached-image analysis into the newauto/video
  workflow domain unless the user explicitly connects it to that domain.
- For a new HPSL/Flow/video workflow, call start_video_workflow exactly once.
- When the user says 진행, ok, 다음, or continue, call continue_video_workflow
  exactly once. Never advance more than one workflow step for one approval.
- If a tool appears to fail or timeout, do not guess. Call diagnose_runtime and
  compare the saved project state before explaining anything.
- If continue_video_workflow reports context_target_met=false, treat it as an
  LM Studio context failure, not a Flow authentication failure. Do not press
  Retry in the same bloated Cline task; reload qwen/qwen3.5-9b with 131072
  context and resume from a fresh compact task.
- Track local recovery attempts for the current user request. A local recovery
  attempt includes a failed tool retry, alternate local tool, diagnosis command,
  repair command, browser/DOM/screenshot check, code edit intended to fix the
  blocker, or config change intended to fix the blocker.
- If the same blocker remains unresolved after 3 local recovery attempts, stop
  local trial-and-error and call ask_openrouter_subagent(mode="debug") before
  trying a 4th local fix. This applies to workflow, browser, Flow, shell,
  Python, server, dependency, test, configuration, and code/debug failures, not
  only image analysis.
- If /api/projects/<id>/output returns 404 after render appears complete, do not
  keep retrying the same URL or only searching for *.mp4. First request
  /api/projects/<id>/render-report and check outputs[].format/path/exists; if
  the only completed output is shorts, use /api/projects/<id>/output?format=shorts.
- Never parse /api/projects/<id>/output as JSON. It is a video FileResponse. For
  JSON metadata, call /api/projects/<id>/render-report; for binary/file
  existence, check status headers or save/probe the MP4.
- If the output 404 remains unexplained after the render-report check and one
  filesystem check, call ask_openrouter_subagent(mode="debug") before any
  further local workaround.
- The OpenRouter task must include the original user goal, current blocker,
  the 3 attempts already tried, concise relevant errors, and the next decision
  needed. Do not pass long Korean prompts through a shell --task argument.
- If diagnose_runtime shows stale state, locks, worker problems, or a mismatch,
  call repair_runtime once.
- If diagnose_runtime or forensic_diagnose shows TTS heartbeat expiry, missing
  TTS worker, missing run_tts_job subprocess, or missing TTS artifacts, call
  repair_tts once before asking the user what to do.
- If the user asks to search the web, look up information, find docs, or research
  a topic, call search_web first. Do not say real-time search is impossible.
- Universal web/browser tool policy:
  1. Classify web tasks as search, read, interact, inspect_ui, download, or workflow.
  2. For search/read tasks, prefer search_web, HTTP fetch, RSS, or public APIs before GUI clicking.
  3. Use Playwright MCP for DOM extraction, navigation, selector clicks, and page state.
  4. Use browser-use MCP only for multi-step exploratory browsing or after Playwright fails twice.
  5. Before blaming a website, check whether the local browser/CDP endpoint is alive.
  6. If Playwright or browser-use fails with ECONNREFUSED, timeout, or connection refused during ordinary search/read work, stop browser retries and use search_web, read_url_or_search, or direct HTTP fallback.
  7. Call ensure_browser_ready or start C:\\Users\\petbl\\newauto\\start-cline-browser.cmd only for Flow/video GUI work that intentionally needs the persistent 9225 CDP browser.
  8. If browser repair fails but the goal can be completed through search_web or HTTP fetch, continue through that fallback.
  9. Do not ask the user for an alternate source until local browser repair and text fallback both failed.
  10. Do not invent unavailable tool names. Use only visible tools.
  11. After 3 local recovery attempts against the same blocker, call ask_openrouter_subagent(mode="debug") with the goal, blocker, facts, attempts, and next decision needed.
  12. OpenRouter is advisory only. Verify its recommendation locally before acting.
  13. Never send secrets, cookies, tokens, full browser profiles, full logs, or full repo dumps to OpenRouter.
  14. Keep the user's goal primary. Browser navigation is a means, not the goal.
- Playwright MCP verified tool note: @playwright/mcp exposes browser_evaluate
  and browser_snapshot for text/DOM extraction. It does not expose
  browser_extract_content. Never call browser_extract_content; use
  browser_evaluate with article selectors, or report that the needed visible
  tool is unavailable.
- If the separate openclaw-operator plugin is not visible, use the operator
  fallback tools exposed by this newauto-stepwise server.
- If local diagnosis repeats or OpenRouter review is needed, use
  ask_openrouter_subagent. Do not pass long Korean prompts through a shell
  --task argument.
- Do not say browser clicking, GUI control, file work, or shell execution is
  impossible. Use Playwright Flow workflow tools or run_powershell.
- If run_powershell returns approval_required, ask the user for explicit
  approval. If the user approves, re-run the same command with force_approve=true.
- Use Playwright Flow workflow tools for Flow GUI work. If login, CAPTCHA, account
  permission, or desktop lock is required, tell the user exactly what to do.
- If browser/GUI work returns ok=false, exit_code!=0, or a
  [SCREENSHOT_ANALYSIS_NEEDED] marker, call analyze_browser_screenshot on the
  latest after screenshot before deciding the next action.
- Do not try to inspect screenshots with local Qwen. analyze_browser_screenshot
  sends a bounded screenshot payload to OpenRouter Gemma 4 Vision and returns
  text analysis for the next GUI action.
- Never pass data:image/base64 browser screenshots into local Qwen chat context.
  Use DOM/status/logs first; if visual state is required, pass only the screenshot
  file path to analyze_browser_screenshot and keep only the text result.
- When a repair tool succeeds, do not ask the user what to do next. Immediately
  call continue_video_workflow once.
- Scripts must be Korean. Flow image prompts must be English.
- HPSL means Hook-Point-Story-Lesson: 훅-포인트-스토리-교훈.
- Never print secrets, tokens, cookies, passwords, or authorization values.
- Reply in concise Korean after each successful step and ask the user to answer
  진행, ok, or 다음 before continuing.

Memory rules:
- At the start of a new conversation, call the memory MCP read_graph to load
  any previously saved knowledge, preferences, and failure patterns.
- When you discover a new verified failure cause, user preference, or workflow
  pattern, save it via memory MCP create_entities or add_relations.
- Do not store secrets, tokens, or passwords in memory.
- Keep memory entities concise: name, entityType, and short observations.
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


def _reset_wait_repeat_count(pid: str, actions: list[str] | None = None) -> None:
    if not pid.strip():
        return
    try:
        state = core._load_stepwise_state(pid)
        core._set_stepwise_fields(
            state,
            {
                "last_wait_step": "",
                "wait_repeat_count": 0,
                "last_wait_snapshot": {},
            },
        )
    except Exception as exc:
        if actions is not None:
            actions.append(f"wait_repeat_count reset skipped: {type(exc).__name__}: {exc}")
        return
    if actions is not None:
        actions.append("reset wait_repeat_count after repair attempt")


def _autonomous_next_action(tool_name: str) -> str:
    return (
        "\n\n[AUTONOMOUS_NEXT_ACTION]\n"
        f"{tool_name} completed a local recovery attempt. Do not ask the user what to do next.\n"
        "Immediately call continue_video_workflow exactly once for the same project_id."
    )


def _wrapper_header(resolved_project_id: str) -> str:
    visible_tools = (
        "diagnose_runtime, forensic_diagnose, start_video_workflow, continue_video_workflow, "
        "check_assets, generate_one_image, generate_prompt_file_images, repair_runtime, repair_tts, search_web, read_url_or_search, operator_status, "
        "ensure_browser_ready, ask_openrouter_subagent, analyze_browser_screenshot, run_powershell"
    )
    return (
        "=== newauto-stepwise wrapper ===\n"
        f"wrapper_script: {Path(__file__).resolve()}\n"
        f"visible_tools: {visible_tools}\n"
        f"resolved_project_id: {resolved_project_id or 'none'}"
    )


def _lmstudio_context_metadata() -> dict[str, object]:
    metadata: dict[str, object] = {
        "lmstudio_api_ok": False,
        "loaded_model": "",
        "loaded_context_length": 0,
        "context_target_met": False,
    }
    try:
        with urllib.request.urlopen("http://127.0.0.1:1234/api/v0/models", timeout=3) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except Exception as exc:
        metadata["lmstudio_error"] = f"{type(exc).__name__}: {exc}"
        return metadata

    models = payload.get("data", []) if isinstance(payload, dict) else []
    loaded_models = [
        item for item in models
        if isinstance(item, dict) and item.get("state") == "loaded"
    ]
    metadata["lmstudio_api_ok"] = True
    metadata["loaded_models"] = [
        {
            "id": str(item.get("id") or ""),
            "type": str(item.get("type") or ""),
            "quantization": str(item.get("quantization") or ""),
            "loaded_context_length": int(item.get("loaded_context_length") or 0),
            "max_context_length": int(item.get("max_context_length") or 0),
            "capabilities": item.get("capabilities") or [],
        }
        for item in loaded_models
    ]
    if loaded_models:
        primary = loaded_models[0]
        loaded_context = int(primary.get("loaded_context_length") or 0)
        metadata["loaded_model"] = str(primary.get("id") or "")
        metadata["loaded_context_length"] = loaded_context
        metadata["context_target_met"] = loaded_context >= LMSTUDIO_CONTEXT_TARGET
    return metadata


def _workflow_state_summary(project_id: str) -> dict[str, object]:
    summary: dict[str, object] = {
        "project_id": project_id,
        "next_step": "",
        "asset_coverage": "",
    }
    if not project_id.strip():
        return summary
    try:
        state = core._load_stepwise_state(project_id)
        summary["next_step"] = str(state.get("next_step") or "")
    except Exception as exc:
        summary["state_error"] = f"{type(exc).__name__}: {exc}"
    try:
        project = core._json_request("GET", f"/api/projects/{project_id}", timeout=10)
        sentence_count, attached_count, missing = core._project_sentence_asset_status(project)
        summary["asset_coverage"] = f"{attached_count}/{sentence_count} missing={missing}"
    except Exception as exc:
        summary["asset_coverage_error"] = f"{type(exc).__name__}: {exc}"
    return summary


def _flow_browser_state_summary(project_id: str) -> dict[str, object]:
    summary: dict[str, object] = {
        "flow_window_ready": "undetermined",
        "latest_flow_log": "",
    }
    try:
        flow_windows = core._flow_window_lines()
    except Exception as exc:
        summary["flow_windows_error"] = f"{type(exc).__name__}: {exc}"
    else:
        summary["flow_window_ready"] = "true" if flow_windows else "false"
        summary["flow_windows"] = flow_windows[:3]

    log_path = ROOT_DIR / "storage" / "logs" / f"flow_browser_{project_id}.log"
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            summary["latest_flow_log"] = "\n".join(lines[-6:])
        except Exception as exc:
            summary["latest_flow_log_error"] = f"{type(exc).__name__}: {exc}"
    return summary


def _runtime_state_sections(project_id: str) -> str:
    workflow = _workflow_state_summary(project_id)
    browser = _flow_browser_state_summary(project_id)
    llm = _lmstudio_context_metadata()
    return (
        "=== separated_state_summary ===\n"
        "[Workflow State]\n"
        f"{json.dumps(workflow, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
        "[Browser/Flow State]\n"
        f"{json.dumps(browser, ensure_ascii=False, indent=2, sort_keys=True)}\n\n"
        "[LLM Runtime State]\n"
        f"{json.dumps(llm, ensure_ascii=False, indent=2, sort_keys=True)}"
    )


def _lmstudio_continue_block_message(project_id: str) -> str:
    metadata = _lmstudio_context_metadata()
    if metadata.get("lmstudio_api_ok") is not True:
        error = str(metadata.get("lmstudio_error") or "unknown")
        return (
            f"{_wrapper_header(project_id)}\n\n"
            "Flow login is not the blocker.\n"
            "LM Studio API is unavailable, so continue_video_workflow was blocked before retrying Flow.\n"
            f"error: {error}\n\n"
            f"{_runtime_state_sections(project_id)}"
        )

    loaded_model = str(metadata.get("loaded_model") or "")
    loaded_context = int(metadata.get("loaded_context_length") or 0)
    if loaded_model and loaded_context >= LMSTUDIO_CONTEXT_TARGET:
        return ""

    loaded_display = loaded_model or "none"
    reload_commands = (
        r"C:\Users\petbl\.lmstudio\bin\lms.exe unload qwen/qwen3.5-9b" "\n"
        r"C:\Users\petbl\.lmstudio\bin\lms.exe load qwen/qwen3.5-9b --context-length 131072 --parallel 1 --gpu max --identifier qwen/qwen3.5-9b -y"
    )
    return (
        f"{_wrapper_header(project_id)}\n\n"
        "Flow login is not the blocker.\n"
        "LM Studio model context is insufficient, so continue_video_workflow was blocked before retrying Flow.\n"
        f"loaded_model: {loaded_display}\n"
        f"loaded_context_length: {loaded_context}\n"
        f"required_context_length: {LMSTUDIO_CONTEXT_TARGET}\n\n"
        "Do not press Retry in the failed Cline task. Reload the model, then resume from a fresh compact task.\n\n"
        f"```powershell\n{reload_commands}\n```\n\n"
        "Fresh task payload should include only project_id, next_step, and the concise latest error; call continue_video_workflow exactly once.\n\n"
        f"{_runtime_state_sections(project_id)}"
    )


def _agentic_metadata(project_id: str) -> dict[str, object]:
    next_step = ""
    if project_id.strip():
        try:
            state = core._load_stepwise_state(project_id)
            next_step = str(state.get("next_step") or "")
        except Exception:
            next_step = ""
    desktop_state = operator_core._desktop_state_payload()
    flow_windows: object = []
    try:
        flow_windows = core._flow_window_lines()
    except Exception as exc:
        flow_windows = [f"error: {type(exc).__name__}: {exc}"]
    flow_ready = "undetermined"
    if isinstance(flow_windows, list):
        flow_ready = "true" if len(flow_windows) > 0 else "false"
    recommended = "start_video_workflow"
    if next_step:
        recommended = "continue_video_workflow"
    if desktop_state.get("desktop_locked") is True:
        recommended = "ask_user"
    metadata: dict[str, object] = {
        "agentic_mode": "enabled",
        "context_target": LMSTUDIO_CONTEXT_TARGET,
        "powershell_access": "unrestricted_with_policy_interceptor",
        "filesystem_access": "read_write_via_operator",
        "browser_control": "flow_browser_automation",
        "operator_fallback": "available_in_newauto_stepwise",
        "visible_tools": [
            "get_operator_summary",
            "diagnose_runtime",
            "forensic_diagnose",
            "start_video_workflow",
            "continue_video_workflow",
            "check_assets",
            "generate_one_image",
            "generate_prompt_file_images",
            "repair_runtime",
            "repair_tts",
            "search_web",
            "operator_status",
            "ask_openrouter_subagent",
            "analyze_browser_screenshot",
            "run_powershell",
            "generate_one_image",
        ],
        "latest_project_id": project_id,
        "next_step": next_step,
        "flow_window_ready": flow_ready,
        "desktop_locked": desktop_state.get("desktop_locked", "undetermined"),
        "foreground_hwnd": desktop_state.get("foreground_hwnd", 0),
        "recommended_next_tool": recommended,
    }
    metadata.update(_lmstudio_context_metadata())
    return metadata


@mcp.tool()
def diagnose_runtime(project_id: str = "") -> str:
    """Check MCP identity, API health, latest workflow state, and asset coverage."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    diagnosis = core.diagnose_newauto_runtime(pid)
    metadata = json.dumps(_agentic_metadata(pid), ensure_ascii=False, indent=2, sort_keys=True)
    summary_section = ""
    if pid:
        try:
            summary = core._json_request("GET", f"/api/projects/{pid}/operator-summary", timeout=30)
            summary_json = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
            summary_section = f"\n\n=== operator_summary_json ===\n{summary_json}"
        except Exception as exc:
            summary_section = f"\n\n=== operator_summary_json ===\nerror: {type(exc).__name__}: {exc}"
    return (
        f"{_wrapper_header(pid)}\n\n{_runtime_state_sections(pid)}"
        f"{summary_section}\n\n=== agentic_metadata_json ===\n{metadata}\n\n{diagnosis}"
    )


@mcp.tool()
def get_operator_summary(project_id: str = "") -> str:
    """Return the single source of truth for video workflow state and next action."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    if not pid:
        return f"{_wrapper_header(pid)}\n\n확인할 프로젝트를 찾지 못했습니다. 먼저 diagnose_runtime으로 상태를 확인하세요."
    try:
        summary = core._json_request("GET", f"/api/projects/{pid}/operator-summary", timeout=30)
    except Exception as exc:
        return f"{_wrapper_header(pid)}\n\noperator_summary 조회 실패: {type(exc).__name__}: {exc}"
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    recommended = str(summary.get("recommended_next_tool") or "")
    next_action = str(summary.get("next_autonomous_action") or "")
    return (
        f"{_wrapper_header(pid)}\n\n"
        f"recommended_next_tool: {recommended or 'unknown'}\n"
        f"next_autonomous_action: {next_action or 'unknown'}\n\n"
        f"=== operator_summary_json ===\n{summary_json}"
    )


@mcp.tool()
def forensic_diagnose(project_id: str = "") -> str:
    """Deep forensic analysis when a tool times out or fails unexpectedly.

    Unlike diagnose_runtime which surveys workflow state, this performs
    deterministic system checks the LLM cannot do reliably from prose:
    - server health (newauto API :9002, LM Studio :1234, ComfyUI :8188)
      NOTE: This check is a deterministic diagnostic routine and does NOT
      mean the workflow has switched to ComfyUI.
    - venv interpreter health (which Python, which modules are missing)
    - Browser/process state relevant to Playwright Flow automation
    - recent operator log failures with stderr_chars and elapsed_sec
      (fast-fail < 2s with stderr means import/argument error, NOT timeout)
    - project state cross-checked: prompts vs media count vs asset_path

    Returns structured critical_findings + recommended_actions. ALWAYS call
    this BEFORE offering vague choices like "retry/skip/manual" to the user;
    it almost always identifies the real cause in one shot.
    """
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    forensic_script = ROOT_DIR / "scripts" / "forensic_doctor.py"
    if not forensic_script.exists():
        return f"{_wrapper_header(pid)}\n\nforensic_doctor.py not found at {forensic_script}"
    try:
        out = subprocess.run(
            [sys.executable, str(forensic_script),
             "--project-id", pid, "--json"],
            capture_output=True, text=True, timeout=45,
            encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
        )
    except Exception as exc:
        return f"{_wrapper_header(pid)}\n\nforensic_doctor execution failed: {type(exc).__name__}: {exc}"
    if out.returncode != 0:
        return (
            f"{_wrapper_header(pid)}\n\n"
            f"forensic_doctor exit={out.returncode}\n"
            f"stderr:\n{(out.stderr or '')[:800]}"
        )
    try:
        report = json.loads(out.stdout)
    except Exception as exc:
        return (
            f"{_wrapper_header(pid)}\n\n"
            f"forensic_doctor JSON parse failed: {exc}\n"
            f"stdout head:\n{(out.stdout or '')[:800]}"
        )
    findings = report.get("critical_findings", [])
    actions = report.get("recommended_actions", [])
    status = report.get("status", "unknown")
    parts = [
        _wrapper_header(pid),
        "",
        f"=== forensic_diagnose status={status} ===",
        "",
        "[Critical findings]",
    ]
    parts.extend(f"  - {f}" for f in findings)
    parts.append("")
    parts.append("[Recommended actions]")
    parts.extend(f"  {i}. {a}" for i, a in enumerate(actions, 1))
    parts.append("")
    parts.append("[Full JSON report]")
    parts.append(json.dumps(report, ensure_ascii=False, indent=2))
    return "\n".join(parts)


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
            "진행할 프로젝트를 찾지 못했습니다. 먼저 diagnose_runtime으로 상태를 확인하거나 "
            "start_video_workflow로 새 워크플로우를 시작하세요."
        )
    block_message = _lmstudio_continue_block_message(pid)
    if block_message:
        return block_message
    message = core.continue_stepwise_hpsl_video_workflow(pid)
    return f"{_wrapper_header(pid)}\n\n{message}"


@mcp.tool()
def check_assets(project_id: str = "") -> str:
    """Check Flow sentence image coverage without advancing the workflow."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    if not pid:
        return f"{_wrapper_header(pid)}\n\n확인할 프로젝트를 찾지 못했습니다. 먼저 diagnose_runtime으로 상태를 확인하세요."
    message = core.flow_asset_coverage(pid)
    project = core._json_request("GET", f"/api/projects/{pid}", timeout=10)
    if not project.get("sentences") and project.get("source_draft_state") == "done":
        message += "\n\n[WARNING] Source draft is done but NOT applied to the script. 'coverage 0/0' is because the script is empty. Call continue_video_workflow to apply it."
    return f"{_wrapper_header(pid)}\n\n{message}"


@mcp.tool()
def generate_one_image(project_id: str = "", sentence_number: int = 0) -> str:
    """Diagnostic tool: click Generate for one missing Flow sentence only."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    if not pid:
        return f"{_wrapper_header(pid)}\n\n이미지를 생성할 프로젝트를 찾지 못했습니다. 먼저 diagnose_runtime으로 상태를 확인하세요."
    target_sentence = sentence_number if sentence_number > 0 else _first_missing_sentence(pid)
    message = core.flow_generate_one_sentence(pid, target_sentence)
    return f"{_wrapper_header(pid)}\n\n{message}"


@mcp.tool()
def generate_prompt_file_images(
    prompt_dir: str = "temp_prompts",
    pattern: str = "prompt_*.txt",
    output_dir: str = "storage/prompt_file_images",
    limit: int = 0,
) -> str:
    """Generate standalone Flow images from local prompt text files; does not use video/HPSL projects."""
    core._configure_stdout()
    flow_script = ROOT_DIR / "scripts" / "flow_browser_automation.py"
    command = [
        sys.executable,
        str(flow_script),
        "prompt-files",
        "--prompt-dir",
        prompt_dir,
        "--pattern",
        pattern,
        "--output-dir",
        output_dir,
        "--limit",
        str(max(0, int(limit or 0))),
    ]
    env = os.environ.copy()
    env.setdefault("FLOW_AUTOMATION_BACKEND", "playwright")
    env.setdefault("FLOW_MODE", "playwright")
    env.setdefault("FLOW_BROWSER", "edge")
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return (
            f"{_wrapper_header('none')}\n\n"
            "Prompt-file image generation timed out before completion.\n\n"
            f"- prompt_dir: {prompt_dir}\n"
            f"- pattern: {pattern}\n"
            f"- output_dir: {output_dir}"
        )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        return (
            f"{_wrapper_header('none')}\n\n"
            "Prompt-file image generation failed before Flow returned a result.\n\n"
            f"- exit_code: {completed.returncode}\n"
            f"- stderr: {stderr[:1200]}"
        )
    try:
        payload = json.loads(stdout)
    except Exception:
        return (
            f"{_wrapper_header('none')}\n\n"
            "Prompt-file image generation returned non-JSON output.\n\n"
            f"- stdout: {stdout[:1200]}\n"
            f"- stderr: {stderr[:1200]}"
        )
    records = payload.get("records")
    ok_records = [
        item for item in records if isinstance(item, dict) and item.get("status") == "ok"
    ] if isinstance(records, list) else []
    failed_records = [
        item for item in records if isinstance(item, dict) and item.get("status") != "ok"
    ] if isinstance(records, list) else []
    paths = [str(item.get("path") or "") for item in ok_records if str(item.get("path") or "")]
    sources = payload.get("sources")
    source_count = len(sources) if isinstance(sources, list) else 0
    status_line = "completed" if payload.get("ok") is True else "incomplete"
    return (
        f"{_wrapper_header('none')}\n\n"
        f"Prompt-file image batch {status_line}.\n\n"
        f"- prompt_dir: {payload.get('prompt_dir') or prompt_dir}\n"
        f"- pattern: {payload.get('pattern') or pattern}\n"
        f"- requested_files: {source_count}\n"
        f"- generated: {len(ok_records)}/{source_count}\n"
        f"- output_dir: {payload.get('output_dir') or output_dir}\n"
        f"- images: {paths}\n"
        f"- failed: {failed_records if failed_records else 'none'}"
    )


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    completed = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        check=False,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return f'"{pid}"' in completed.stdout


def _cleanup_source_worker_lock(actions: list[str]) -> None:
    lock_path = core.SOURCE_DRAFT_WORKER_LOCK
    if not lock_path.exists():
        return
    try:
        worker_pid = int(lock_path.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        worker_pid = 0
    if worker_pid and _pid_exists(worker_pid):
        actions.append(f"source_draft_worker.lock is live: pid={worker_pid}")
        return
    lock_path.unlink(missing_ok=True)
    actions.append(f"removed stale source_draft_worker.lock: pid={worker_pid or 'invalid'}")


def _cleanup_worker_lock(lock_path: Path, label: str, actions: list[str]) -> None:
    if not lock_path.exists():
        return
    try:
        worker_pid = int(lock_path.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        worker_pid = 0
    if worker_pid and _pid_exists(worker_pid):
        actions.append(f"{label} lock is live: pid={worker_pid}")
        return
    lock_path.unlink(missing_ok=True)
    actions.append(f"removed stale {label} lock: pid={worker_pid or 'invalid'}")


def _tts_artifact_summary(pid: str) -> dict[str, object]:
    tts_dir = ROOT_DIR / "storage" / "projects" / pid / "tts"
    wav_files = sorted(tts_dir.glob("*.wav")) if tts_dir.exists() else []
    nonzero_wav = [path for path in wav_files if path.stat().st_size > 0]
    timings = tts_dir / "timings.json"
    manifest = tts_dir / "tts_run_manifest.json"
    latest_mtime = 0.0
    for path in [timings, manifest, *wav_files]:
        if path.exists():
            latest_mtime = max(latest_mtime, path.stat().st_mtime)
    return {
        "tts_dir": str(tts_dir),
        "timings_exists": timings.exists() and timings.stat().st_size > 0,
        "manifest_exists": manifest.exists() and manifest.stat().st_size > 0,
        "wav_count": len(wav_files),
        "nonzero_wav_count": len(nonzero_wav),
        "latest_mtime": latest_mtime,
        "complete": timings.exists() and manifest.exists() and bool(nonzero_wav),
    }


def _processes_matching(patterns: list[str], *, match_all: bool = False) -> list[dict[str, object]]:
    escaped_patterns = [pattern.replace("'", "''") for pattern in patterns]
    joiner = " -and " if match_all else " -or "
    clauses = joiner.join([f"$_.CommandLine -like '*{pattern}*'" for pattern in escaped_patterns])
    script = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -and ({clauses}) }} | "
        "Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress -Depth 3"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return []
    raw = (completed.stdout or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    return [
        {
            "pid": item.get("ProcessId"),
            "exe": item.get("ExecutablePath") or "",
            "cmd": item.get("CommandLine") or "",
        }
        for item in payload
        if isinstance(item, dict)
    ]


def _start_tts_worker(actions: list[str]) -> None:
    lock_path = ROOT_DIR / "storage" / "tts_worker.lock"
    if lock_path.exists():
        try:
            worker_pid = int(lock_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            worker_pid = 0
        if worker_pid and _pid_exists(worker_pid):
            actions.append(f"tts_worker already live: pid={worker_pid}")
            return
        lock_path.unlink(missing_ok=True)
        actions.append(f"removed stale tts_worker.lock before restart: pid={worker_pid or 'invalid'}")
    log_path = ROOT_DIR / "storage" / "logs" / "tts_worker.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    subprocess.Popen(
        [sys.executable, "-m", "app.workers.tts_worker"],
        cwd=str(ROOT_DIR),
        stdout=log_handle,
        stderr=log_handle,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=(
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform.startswith("win")
            else 0
        ),
    )
    log_handle.close()
    deadline = time.time() + 10
    while time.time() < deadline:
        if lock_path.exists():
            try:
                worker_pid = int(lock_path.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                worker_pid = 0
            if worker_pid and _pid_exists(worker_pid):
                actions.append(f"started tts_worker: pid={worker_pid}")
                return
        time.sleep(0.5)
    actions.append("tts_worker start requested, but lock did not appear within 10s")


def _heartbeat_fresh(value: str, *, max_age_sec: int = 60) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed).total_seconds() <= max_age_sec


def _repair_tts_impl(pid: str) -> tuple[list[str], dict[str, object]]:
    actions: list[str] = []
    db.init_db()
    project = db.get_project(pid)
    if project is None:
        return [f"project not found: {pid}"], {}

    artifacts = _tts_artifact_summary(pid)
    tts_state = str(project["tts_state"] or "")
    tts_progress = int(project["tts_progress"] or 0)
    actions.append(
        "initial: "
        f"tts_state={tts_state}, progress={tts_progress}, complete_artifacts={artifacts['complete']}"
    )
    requeued = False

    if tts_state == "done" and artifacts["complete"]:
        actions.append("already complete: kept existing TTS artifacts and DB state")
        return actions, artifacts

    run_tts_processes = _processes_matching(["run_tts_job.py", pid], match_all=True)
    tts_worker_processes = _processes_matching(["app.workers.tts_worker"])
    active_job = bool(run_tts_processes)
    heartbeat_live = tts_state == "running" and _heartbeat_fresh(str(project["tts_heartbeat_at"] or ""))

    if active_job and heartbeat_live:
        actions.append(
            "active TTS subprocess detected with heartbeat field present; "
            "not requeueing automatically"
        )
        _start_tts_worker(actions)
        return actions, artifacts

    if tts_state in {"running", "error"} and not artifacts["complete"]:
        for proc in run_tts_processes:
            raw_pid = proc.get("pid")
            try:
                proc_pid = int(raw_pid)
            except (TypeError, ValueError):
                continue
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"Stop-Process -Id {proc_pid} -Force -ErrorAction SilentlyContinue"],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            actions.append(f"stopped abandoned run_tts_job.py process: pid={proc_pid}")
        db.update_project(
            pid,
            tts_state="queued",
            tts_progress=0,
            tts_error="",
            tts_job_id="",
            tts_started_at="",
            tts_heartbeat_at="",
            render_last_log="TTS repair requeued an abandoned job.",
        )
        requeued = True
        actions.append("requeued TTS job in DB")
    elif tts_state == "queued":
        actions.append("TTS is already queued")
    elif tts_state == "idle":
        actions.append("TTS is idle; repair_tts did not enqueue a new job")
    elif artifacts["complete"]:
        actions.append("artifacts look complete but DB is not done; left DB unchanged for manual review")
    else:
        actions.append(f"no TTS requeue rule matched for state={tts_state}")

    if requeued:
        lock_path = ROOT_DIR / "storage" / "tts_worker.lock"
        try:
            worker_pid = int(lock_path.read_text(encoding="utf-8").strip() or "0") if lock_path.exists() else 0
        except ValueError:
            worker_pid = 0
        if worker_pid and _pid_exists(worker_pid):
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"Stop-Process -Id {worker_pid} -Force -ErrorAction SilentlyContinue"],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            actions.append(f"restarted tts_worker after requeue: stopped pid={worker_pid}")
        lock_path.unlink(missing_ok=True)
    elif not tts_worker_processes:
        _cleanup_worker_lock(ROOT_DIR / "storage" / "tts_worker.lock", "tts_worker", actions)
    _start_tts_worker(actions)
    refreshed = db.get_project(pid)
    if refreshed is not None:
        actions.append(
            "post: "
            f"tts_state={refreshed['tts_state']}, progress={refreshed['tts_progress']}, "
            f"heartbeat={refreshed['tts_heartbeat_at'] or '-'}"
        )
    return actions, _tts_artifact_summary(pid)


def _repair_stepwise_state(pid: str, actions: list[str]) -> None:
    state = core._load_stepwise_state(pid)
    next_step = str(state.get("next_step") or "")
    project = core._json_request("GET", f"/api/projects/{pid}", timeout=15)
    source_state = str(project.get("source_draft_state") or "")
    source_count, _, _ = core._project_counts(project)
    draft_count = core._draft_sentence_count(project)

    if next_step in {"source_collect", "source_collect_wait"} and source_state == "done" and source_count > 0:
        core._set_stepwise_fields(state, {"next_step": "script_generate"})
        actions.append(f"advanced stale source step to script_generate: sources={source_count}")
        return
    if next_step == "script_generate_wait" and source_state == "done" and draft_count > 0:
        core._set_stepwise_fields(state, {"next_step": "flow_prompts"})
        actions.append(f"advanced completed script step to flow_prompts: draft_sentences={draft_count}")
        return
    if next_step == "script_generate" and source_state in {"queued", "running"}:
        core._ensure_source_draft_worker(timeout_sec=5)
        actions.append(f"ensured source draft worker for state={source_state}")
        return
    if next_step == "script_generate_wait" and source_state in {"queued", "running"}:
        core._ensure_source_draft_worker(timeout_sec=5)
        actions.append(f"ensured source draft worker while waiting: state={source_state}")
        return
    actions.append(
        "no stepwise state repair needed: "
        f"next_step={next_step or '-'}, source_state={source_state or '-'}, "
        f"sources={source_count}, draft_sentences={draft_count}"
    )


@mcp.tool()
def repair_runtime(project_id: str = "") -> str:
    """Repair common local newauto/LM Studio workflow issues without arbitrary shell access."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    actions: list[str] = []
    if not pid:
        return f"{_wrapper_header(pid)}\n\n복구할 프로젝트를 찾지 못했습니다. 먼저 diagnose_runtime을 실행하세요."
    try:
        _cleanup_source_worker_lock(actions)
        _cleanup_worker_lock(ROOT_DIR / "storage" / "tts_worker.lock", "tts_worker", actions)
        _cleanup_worker_lock(ROOT_DIR / "storage" / "render_worker.lock", "render_worker", actions)
        _cleanup_worker_lock(ROOT_DIR / "storage" / "image_worker.lock", "image_worker", actions)
        _repair_stepwise_state(pid, actions)
        _reset_wait_repeat_count(pid, actions)
    except Exception as exc:
        actions.append(f"repair_error: {type(exc).__name__}: {exc}")
    diagnosis = str(core.diagnose_newauto_runtime(pid))
    result: str = (
        f"{_wrapper_header(pid)}\n\n"
        "=== repair_runtime actions ===\n"
        + "\n".join(f"- {action}" for action in actions)
        + "\n\n"
        + diagnosis
    )
    if not any(action.startswith("repair_error:") for action in actions):
        result += _autonomous_next_action("repair_runtime")
    return result


@mcp.tool()
def repair_tts(project_id: str = "") -> str:
    """Repair abandoned OmniVoice TTS jobs without touching completed outputs."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    if not pid:
        return f"{_wrapper_header(pid)}\n\n복구할 프로젝트를 찾지 못했습니다. 먼저 diagnose_runtime을 실행하세요."
    try:
        actions, artifacts = _repair_tts_impl(pid)
        _reset_wait_repeat_count(pid, actions)
    except Exception as exc:
        actions = [f"repair_tts_error: {type(exc).__name__}: {exc}"]
        artifacts = {}
    diagnosis = str(core.diagnose_newauto_runtime(pid))
    result = (
        f"{_wrapper_header(pid)}\n\n"
        "=== repair_tts actions ===\n"
        + "\n".join(f"- {action}" for action in actions)
        + "\n\n"
        "=== repair_tts artifacts ===\n"
        + json.dumps(artifacts, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n\n"
        + diagnosis
    )
    if not any(action.startswith("repair_tts_error:") for action in actions):
        result += _autonomous_next_action("repair_tts")
    return result


def _parse_openrouter_files(files: str) -> list[str]:
    items: list[str] = []
    for raw in files.replace("\r", "\n").replace(",", "\n").split("\n"):
        cleaned = raw.strip()
        if cleaned:
            items.append(cleaned)
    return items[:6]


ATTEMPT_COUNTER_PATH = ROOT_DIR / "storage" / "agent_memory" / "web_recovery_attempts.json"


def _load_recovery_attempts() -> dict[str, int]:
    if not ATTEMPT_COUNTER_PATH.exists():
        return {}
    try:
        payload = json.loads(ATTEMPT_COUNTER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): int(value) for key, value in payload.items() if isinstance(value, int)}


def _record_recovery_attempt(key: str, *, reset: bool = False) -> int:
    attempts = _load_recovery_attempts()
    if reset:
        attempts.pop(key, None)
        count = 0
    else:
        count = int(attempts.get(key, 0)) + 1
        attempts[key] = count
    ATTEMPT_COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATTEMPT_COUNTER_PATH.write_text(json.dumps(attempts, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return count


def _forensic_facts_packet(pid: str) -> dict[str, object]:
    if not pid.strip():
        return {"ok": False, "error": "missing_project_id"}
    payload = core._run_forensic_doctor_json(pid)
    if payload.get("ok") is not True:
        return payload
    report = payload.get("report")
    if not isinstance(report, dict):
        return {"ok": False, "error": "forensic report was not a JSON object"}
    tts = report.get("tts") if isinstance(report.get("tts"), dict) else {}
    return {
        "ok": True,
        "status": report.get("status", "unknown"),
        "critical_findings": report.get("critical_findings", []),
        "recommended_actions": report.get("recommended_actions", []),
        "tts": {
            "db": tts.get("db") if isinstance(tts, dict) else {},
            "processes": tts.get("processes") if isinstance(tts, dict) else {},
            "artifacts": tts.get("artifacts") if isinstance(tts, dict) else {},
        },
    }


@mcp.tool()
def ask_openrouter_subagent(
    mode: str = "debug",
    task: str = "",
    project_id: str = "",
    files: str = "",
    log_file: str = "",
    dry_run: bool = False,
    essential: bool = False,
) -> str:
    """Ask the OpenRouter advisory subagent without shell argument parsing.

    Use this when Cline/local LM Studio repeats a failure or needs external review.
    The task is passed in-process, so Korean text, quotes, JSON, and line breaks
    are not routed through PowerShell `--task` quoting.
    """
    core._configure_stdout()
    requested_mode = mode.strip() or "debug"
    if requested_mode not in openrouter_harness.MODE_BUDGETS:
        return f"{_wrapper_header(_resolve_project_id(project_id))}\n\nunsupported OpenRouter mode: {requested_mode}"
    pid = _resolve_project_id(project_id)
    task_text = task.strip()
    if pid:
        facts = _forensic_facts_packet(pid)
        task_text = (
            f"{task_text}\n\n"
            "=== redacted forensic facts packet ===\n"
            f"{json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True)}"
        ).strip()
    if not task_text:
        return f"{_wrapper_header(pid)}\n\nOpenRouter task is empty. Provide a concrete failure or question."
    try:
        result = openrouter_harness.run_harness(
            mode=requested_mode,
            task=task_text,
            files=_parse_openrouter_files(files),
            log_file=log_file.strip(),
            dry_run=dry_run,
            essential=essential,
            max_input_chars=24000,
            timeout_sec=45,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "error": openrouter_harness._redact_text(f"{type(exc).__name__}: {exc}"),
        }
    else:
        payload = openrouter_harness.redact(openrouter_harness._result_to_dict(result))
    return (
        f"{_wrapper_header(pid)}\n\n"
        "=== ask_openrouter_subagent result ===\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}"
    )


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """Search the public web through DuckDuckGo HTML without paid external APIs."""
    core._configure_stdout()
    response = shared_search_web(query.strip(), max_results=max_results)
    return format_search_response(response)
    cleaned_query = query.strip()
    if not cleaned_query:
        return "검색어가 비어 있습니다. 사용자가 찾으려는 주제를 query에 넣어 다시 호출하세요."
    limit = max(1, min(int(max_results), 8))
    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": cleaned_query})
    request = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            page = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return (
            "search_web failed\n"
            f"query: {cleaned_query}\n"
            f"error: {type(exc).__name__}: {exc}\n"
            "다른 검색어로 다시 시도하거나 run_powershell로 직접 URL 접근을 점검하세요."
        )

    parser = _DuckDuckGoResultParser()
    parser.feed(page)
    results = _dedupe_results(parser.results, limit)
    if not results:
        return (
            "search_web returned no parsed results\n"
            f"query: {cleaned_query}\n"
            f"search_url: {search_url}\n"
            "검색 페이지가 차단되었거나 결과 구조가 바뀌었을 수 있습니다."
        )

    lines = [
        "=== search_web results ===",
        f"query: {cleaned_query}",
        f"search_url: {search_url}",
        "instruction: Use these URLs as sources. Prefer official docs when present.",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.append(f"{index}. {result['title']}")
        lines.append(f"   url: {result['url']}")
        snippet = result.get("snippet", "")
        if snippet:
            lines.append(f"   snippet: {snippet[:500]}")
    return "\n".join(lines)


@mcp.tool()
def read_url_or_search(query_or_url: str = "", count: int = 3, prefer_domain: str = "") -> str:
    """Read a URL directly, or search the web if the input is a query."""
    core._configure_stdout()
    payload = shared_read_url_or_search(query_or_url, count=count, prefer_domain=prefer_domain)
    return format_read_url_or_search(payload)


def _cdp_version_payload(cdp_url: str, timeout_sec: float = 2.0) -> dict[str, object]:
    endpoint = cdp_url.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(endpoint, timeout=timeout_sec) as response:
            raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except Exception as exc:
        return {
            "ok": False,
            "endpoint": endpoint,
            "failure_class": "cdp_endpoint_unavailable",
            "message": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "endpoint": endpoint,
            "failure_class": "cdp_invalid_response",
            "message": "CDP /json/version did not return a JSON object.",
        }
    return {
        "ok": True,
        "endpoint": endpoint,
        "browser": str(payload.get("Browser") or ""),
        "websocket_debugger_url": str(payload.get("webSocketDebuggerUrl") or ""),
    }


@mcp.tool()
def ensure_browser_ready(cdp_url: str = "http://127.0.0.1:9225", open_url: str = "about:blank") -> str:
    """CRITICAL: You MUST call this tool FIRST before using any Playwright or browser-use tools.
    It opens the browser and prepares the connection. If the user asks to open a browser or navigate, call this FIRST."""
    core._configure_stdout()
    attempt_key = f"ensure_browser_ready:{cdp_url.rstrip('/')}"
    actions: list[str] = ["checked_cdp_json_version"]
    first = _cdp_version_payload(cdp_url)
    if first.get("ok") is True:
        _record_recovery_attempt(attempt_key, reset=True)
        return json.dumps(
            {
                "ok": True,
                "tool": "ensure_browser_ready",
                "cdp_url": cdp_url,
                "open_url": open_url,
                "attempted_actions": actions,
                "recovery_attempt_count": 0,
                "next_action_suggestion": "use_playwright_or_browser_use",
                "cdp": first,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    start_script = ROOT_DIR / "start-cline-browser.cmd"
    if not start_script.exists():
        attempt_count = _record_recovery_attempt(attempt_key)
        return json.dumps(
            {
                "ok": False,
                "tool": "ensure_browser_ready",
                "cdp_url": cdp_url,
                "open_url": open_url,
                "failure_class": "browser_repair_script_missing",
                "message": f"Missing repair script: {start_script}",
                "attempted_actions": actions,
                "recovery_attempt_count": attempt_count,
                "next_action_suggestion": "use_search_web_or_http_request",
                "openrouter_escalation_recommended": attempt_count >= 3,
                "cdp": first,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    try:
        subprocess.run(
            [str(start_script)],
            cwd=str(ROOT_DIR),
            timeout=20,
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        actions.append("started_start_cline_browser_cmd")
    except Exception as exc:
        attempt_count = _record_recovery_attempt(attempt_key)
        return json.dumps(
            {
                "ok": False,
                "tool": "ensure_browser_ready",
                "cdp_url": cdp_url,
                "open_url": open_url,
                "failure_class": "browser_repair_command_failed",
                "message": f"{type(exc).__name__}: {exc}",
                "attempted_actions": actions,
                "recovery_attempt_count": attempt_count,
                "next_action_suggestion": "use_search_web_or_http_request",
                "openrouter_escalation_recommended": attempt_count >= 3,
                "cdp": first,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    time.sleep(1.0)
    actions.append("rechecked_cdp_json_version")
    second = _cdp_version_payload(cdp_url)
    if second.get("ok") is True:
        _record_recovery_attempt(attempt_key, reset=True)
        return json.dumps(
            {
                "ok": True,
                "tool": "ensure_browser_ready",
                "cdp_url": cdp_url,
                "open_url": open_url,
                "attempted_actions": actions,
                "recovery_attempt_count": 0,
                "next_action_suggestion": "use_playwright_or_browser_use",
                "cdp": second,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    attempt_count = _record_recovery_attempt(attempt_key)
    return json.dumps(
        {
            "ok": False,
            "tool": "ensure_browser_ready",
            "cdp_url": cdp_url,
            "open_url": open_url,
            "failure_class": str(second.get("failure_class") or "cdp_endpoint_unavailable"),
            "message": str(second.get("message") or "CDP endpoint did not become ready after repair."),
            "attempted_actions": actions,
            "recovery_attempt_count": attempt_count,
            "next_action_suggestion": "ask_openrouter_subagent_or_use_search_web" if attempt_count >= 3 else "use_search_web_or_http_request",
            "openrouter_escalation_recommended": attempt_count >= 3,
            "cdp_before": first,
            "cdp_after": second,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


@mcp.tool()
def operator_status() -> str:
    """Show OpenClaw-style local operator authority status."""
    operator_core._configure_stdout()
    result: object = operator_core.operator_status()
    return str(result)


def _latest_flow_screenshot(project_id: str = "") -> str:
    screenshot_dir = ROOT_DIR / "storage" / "flow_desktop_screenshots"
    if not screenshot_dir.exists():
        return ""
    patterns = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(screenshot_dir.glob(pattern))
    if project_id.strip():
        preferred = [path for path in candidates if project_id.strip() in path.name]
        if preferred:
            candidates = preferred
    if not candidates:
        return ""
    return str(max(candidates, key=lambda path: path.stat().st_mtime))


def _extract_last_screenshot(text: str) -> str:
    matches = re.findall(r"[A-Za-z]:\\\\[^\"'\r\n]+?\.(?:png|jpg|jpeg|webp)", text, flags=re.IGNORECASE)
    return matches[-1].replace("\\\\", "\\") if matches else ""


@mcp.tool()
def analyze_browser_screenshot(
    image_path: str = "",
    question: str = "Analyze the browser screenshot and recommend the next GUI action.",
    project_id: str = "",
) -> str:
    """Analyze a browser/Flow screenshot through OpenRouter Gemma 4 Vision."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    selected_path = image_path.strip() or _latest_flow_screenshot(pid)
    if not selected_path:
        return f"{_wrapper_header(pid)}\n\nanalyze_browser_screenshot error: no screenshot path was provided and no recent Flow screenshot was found."
    context = json.dumps(_forensic_facts_packet(pid), ensure_ascii=False, sort_keys=True) if pid else ""
    try:
        result = openrouter_harness.analyze_screenshot(
            selected_path,
            question=question,
            context=context,
            max_tokens=800,
            timeout_sec=45,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "error": openrouter_harness._redact_text(f"{type(exc).__name__}: {exc}"),
            "image_path": selected_path,
        }
    else:
        payload = openrouter_harness.redact(openrouter_harness._result_to_dict(result))
    return (
        f"{_wrapper_header(pid)}\n\n"
        "[VISION_ANALYSIS]\n"
        f"image_path: {selected_path}\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}"
    )


@mcp.tool()
def run_powershell(command: str, cwd: str = "", timeout_sec: int = 60, force_approve: bool = False) -> str:
    """Run a local PowerShell command through the OpenClaw-style operator."""
    operator_core._configure_stdout()
    result: object = operator_core.run_powershell(command, cwd, timeout_sec, force_approve)
    return str(result)


@mcp.tool()
def legacy_flow_desktop(
    project_id: str,
    sentence_number: int,
    mode: str = "generate-one",
    wait_seconds: int = 60,
    download_timeout_seconds: int = 45,
) -> str:
    """Retired compatibility wrapper for the old desktop Flow path."""
    operator_core._configure_stdout()
    result: object = (
        "Legacy desktop Flow path is retired. Use continue_video_workflow or generate_one_image."
    )
    _unused_legacy_args = (
        project_id,
        sentence_number,
        mode,
        wait_seconds,
        download_timeout_seconds,
    )
    return str(result)
    text = str(result)
    failed = "exit_code: 0" not in text or '"ok": false' in text.lower()
    screenshot = _extract_last_screenshot(text) or _latest_flow_screenshot(project_id)
    if failed and screenshot:
        if os.getenv("FLOW_AUTO_ANALYZE_FAILURE", "1").strip().lower() not in {"0", "false", "no"}:
            try:
                context = json.dumps(_forensic_facts_packet(project_id), ensure_ascii=False, sort_keys=True) if project_id.strip() else ""
                analysis = openrouter_harness.analyze_screenshot(
                    screenshot,
                    question=(
                        "Google Flow browser automation failed. Analyze the screenshot, "
                        "identify the current UI state, visible blockers, and recommend the next concrete GUI action."
                    ),
                    context=context,
                    max_tokens=800,
                    timeout_sec=45,
                )
                payload = openrouter_harness.redact(openrouter_harness._result_to_dict(analysis))
                text += (
                    "\n\n[AUTO_OPENROUTER_VISION_ANALYSIS]\n"
                    f"image_path: {screenshot}\n"
                    f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}"
                )
            except Exception as exc:
                text += (
                    "\n\n[AUTO_OPENROUTER_VISION_ANALYSIS_FAILED]\n"
                    f"image_path: {screenshot}\n"
                    f"error: {openrouter_harness._redact_text(f'{type(exc).__name__}: {exc}')}"
                )
        text += (
            "\n\n[SCREENSHOT_ANALYSIS_NEEDED]\n"
            f"image_path: {screenshot}\n"
            "If AUTO_OPENROUTER_VISION_ANALYSIS is absent or inconclusive, call analyze_browser_screenshot(image_path='<above path>') before choosing the next GUI action."
        )
    return text


def main() -> None:
    core._configure_stdout()
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Run newauto stepwise workflow commands or start the MCP server.")
        parser.add_argument(
            "command",
            nargs="?",
            choices=(
                "start_video_workflow",
                "start-video-workflow",
                "continue_video_workflow",
                "continue-video-workflow",
                "repair_tts",
                "repair-tts",
            ),
            help="Optional command alias for agent runners that pass tool names as positional arguments.",
        )
        parser.add_argument(
            "--action",
            choices=(
                "start_video_workflow",
                "start-video-workflow",
                "continue_video_workflow",
                "continue-video-workflow",
                "repair_tts",
                "repair-tts",
            ),
            help="Command alias used by Cline and other shell runners.",
        )
        parser.add_argument("--start-video-workflow", action="store_true", help="Start a new stepwise HPSL video workflow.")
        parser.add_argument("--continue-video-workflow", action="store_true", help="Run one next step for the latest workflow.")
        parser.add_argument("--project-id", default="", help="newauto project id to continue.")
        parser.add_argument("--keyword", default="", help="Keyword or URL for --start-video-workflow.")
        parser.add_argument("--min-date", default="", help="Optional minimum date to include in the source request.")
        parser.add_argument("--title", default="", help="Optional project title.")
        parser.add_argument("--target-minutes", type=int, default=1, help="Target video length in minutes.")
        parser.add_argument("--tone", default="설명형", help="Script tone.")
        args = parser.parse_args()

        command = args.action or args.command
        if command in ("start_video_workflow", "start-video-workflow"):
            args.start_video_workflow = True
        if command in ("continue_video_workflow", "continue-video-workflow"):
            args.continue_video_workflow = True
        repair_tts_requested = command in ("repair_tts", "repair-tts")

        requested_count = sum([bool(args.start_video_workflow), bool(args.continue_video_workflow), repair_tts_requested])
        if requested_count > 1:
            parser.error("Choose only one CLI action.")
        if args.start_video_workflow:
            request = args.keyword.strip()
            if not request:
                parser.error("--keyword is required with --start-video-workflow.")
            if args.min_date.strip():
                request = f"{request} {args.min_date.strip()} 이후"
            print(
                start_video_workflow(
                    keyword_or_url=request,
                    title=args.title,
                    target_minutes=args.target_minutes,
                    tone=args.tone,
                )
            )
            return
        if args.continue_video_workflow:
            print(continue_video_workflow(args.project_id))
            return
        if repair_tts_requested:
            print(repair_tts(args.project_id))
            return
        parser.error("No CLI action requested. Use no arguments to run as an MCP stdio server.")

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
