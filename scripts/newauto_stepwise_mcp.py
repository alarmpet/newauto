from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp.server.fastmcp import FastMCP
from scripts import lmstudio_openclaw_operator_mcp as operator_core
from scripts import newauto_mcp as core


STEPWISE_INSTRUCTIONS = """
You are not a text-only AI. You are a local system operator with two local
hands: control_flow_desktop for GUI/Flow work and run_powershell for shell,
filesystem, git, server, and repair work.

The user should not need to know MCP tool names. Interpret the user's natural
Korean request, choose the right local tool yourself, and report only the
completed step, current state, and any user action required.

Available tools:
- diagnose_runtime(project_id="")
- start_video_workflow(keyword_or_url, title="", target_minutes=1, tone="설명형")
- continue_video_workflow(project_id="")
- check_assets(project_id="")
- generate_one_image(project_id="", sentence_number=0)
- repair_runtime(project_id="")
- search_web(query, max_results=5)
- operator_status()
- run_powershell(command, cwd="", timeout_sec=60, force_approve=false)
- control_flow_desktop(project_id, sentence_number, mode="generate-one")

Rules:
- For a new HPSL/Flow/video workflow, call start_video_workflow exactly once.
- When the user says 진행, ok, 다음, or continue, call continue_video_workflow
  exactly once. Never advance more than one workflow step for one approval.
- If a tool appears to fail or timeout, do not guess. Call diagnose_runtime and
  compare the saved project state before explaining anything.
- If diagnose_runtime shows stale state, locks, worker problems, or a mismatch,
  call repair_runtime once.
- If the user asks to search the web, look up information, find docs, or research
  a topic, call search_web first. Do not say real-time search is impossible.
- If the separate openclaw-operator plugin is not visible, use the operator
  fallback tools exposed by this newauto-stepwise server.
- Do not say browser clicking, GUI control, file work, or shell execution is
  impossible. Use control_flow_desktop or run_powershell.
- If run_powershell returns approval_required, ask the user for explicit
  approval. If the user approves, re-run the same command with force_approve=true.
- Use control_flow_desktop for Flow GUI work. If login, CAPTCHA, account
  permission, or desktop lock is required, tell the user exactly what to do.
- Scripts must be Korean. Flow image prompts must be English.
- HPSL means Hook-Point-Story-Lesson: 훅-포인트-스토리-교훈.
- Never print secrets, tokens, cookies, passwords, or authorization values.
- Reply in concise Korean after each successful step and ask the user to answer
  진행, ok, or 다음 before continuing.
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
        "check_assets, generate_one_image, repair_runtime, search_web, operator_status, "
        "run_powershell, control_flow_desktop"
    )
    return (
        "=== newauto-stepwise wrapper ===\n"
        f"wrapper_script: {Path(__file__).resolve()}\n"
        f"visible_tools: {visible_tools}\n"
        f"resolved_project_id: {resolved_project_id or 'none'}"
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
    return {
        "agentic_mode": "enabled",
        "context_target": 30000,
        "powershell_access": "unrestricted_with_policy_interceptor",
        "filesystem_access": "read_write_via_operator",
        "desktop_control": "flow_desktop_control",
        "operator_fallback": "available_in_newauto_stepwise",
        "visible_tools": [
            "diagnose_runtime",
            "start_video_workflow",
            "continue_video_workflow",
            "check_assets",
            "generate_one_image",
            "repair_runtime",
            "search_web",
            "operator_status",
            "run_powershell",
            "control_flow_desktop",
        ],
        "latest_project_id": project_id,
        "next_step": next_step,
        "flow_window_ready": flow_ready,
        "desktop_locked": desktop_state.get("desktop_locked", "undetermined"),
        "foreground_hwnd": desktop_state.get("foreground_hwnd", 0),
        "recommended_next_tool": recommended,
    }


@mcp.tool()
def diagnose_runtime(project_id: str = "") -> str:
    """Check MCP identity, API health, latest workflow state, and asset coverage."""
    core._configure_stdout()
    pid = _resolve_project_id(project_id)
    diagnosis = core.diagnose_newauto_runtime(pid)
    metadata = json.dumps(_agentic_metadata(pid), ensure_ascii=False, indent=2, sort_keys=True)
    return f"{_wrapper_header(pid)}\n\n=== agentic_metadata_json ===\n{metadata}\n\n{diagnosis}"


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
        _repair_stepwise_state(pid, actions)
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
    return result


def _normalize_duckduckgo_href(href: str) -> str:
    candidate = href.strip()
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    parsed = urllib.parse.urlparse(candidate)
    query = urllib.parse.parse_qs(parsed.query)
    redirected = query.get("uddg")
    if redirected:
        return redirected[0]
    return candidate


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._capture_title = False
        self._current_href = ""
        self._current_text: list[str] = []
        self._capture_snippet = False
        self._snippet_text: list[str] = []
        self._snippet_index = -1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        class_name = attr_map.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._capture_title = True
            self._current_href = attr_map.get("href", "")
            self._current_text = []
            return
        if "result__snippet" in class_name:
            self._capture_snippet = True
            self._snippet_text = []
            self._snippet_index = len(self.results) - 1

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_text.append(data)
        if self._capture_snippet:
            self._snippet_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture_title and tag == "a":
            title = " ".join("".join(self._current_text).split())
            url = _normalize_duckduckgo_href(self._current_href)
            if title and url:
                self.results.append({"title": title, "url": url, "snippet": ""})
            self._capture_title = False
            self._current_href = ""
            self._current_text = []
            return
        if self._capture_snippet and tag in {"a", "div"}:
            snippet = " ".join("".join(self._snippet_text).split())
            if snippet and 0 <= self._snippet_index < len(self.results):
                self.results[self._snippet_index]["snippet"] = snippet
            self._capture_snippet = False
            self._snippet_text = []
            self._snippet_index = -1


def _dedupe_results(results: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    seen_urls: set[str] = set()
    deduped: list[dict[str, str]] = []
    for result in results:
        url = result.get("url", "").strip()
        title = result.get("title", "").strip()
        if not url or not title or url in seen_urls:
            continue
        if not url.startswith(("http://", "https://")):
            continue
        seen_urls.add(url)
        deduped.append(
            {
                "title": title,
                "url": url,
                "snippet": result.get("snippet", "").strip(),
            }
        )
        if len(deduped) >= limit:
            break
    return deduped


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """Search the public web through DuckDuckGo HTML without paid external APIs."""
    core._configure_stdout()
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
def operator_status() -> str:
    """Show OpenClaw-style local operator authority status."""
    operator_core._configure_stdout()
    result: object = operator_core.operator_status()
    return str(result)


@mcp.tool()
def run_powershell(command: str, cwd: str = "", timeout_sec: int = 60, force_approve: bool = False) -> str:
    """Run a local PowerShell command through the OpenClaw-style operator."""
    operator_core._configure_stdout()
    result: object = operator_core.run_powershell(command, cwd, timeout_sec, force_approve)
    return str(result)


@mcp.tool()
def control_flow_desktop(
    project_id: str,
    sentence_number: int,
    mode: str = "generate-one",
    wait_seconds: int = 60,
    download_timeout_seconds: int = 45,
) -> str:
    """Control the authenticated Google Flow desktop UI for one sentence."""
    operator_core._configure_stdout()
    result: object = operator_core.control_flow_desktop(
        project_id,
        sentence_number,
        mode,
        wait_seconds,
        download_timeout_seconds,
    )
    return str(result)


def main() -> None:
    core._configure_stdout()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
