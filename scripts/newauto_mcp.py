from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date
from hashlib import md5
from pathlib import Path
from typing import Literal, cast

from mcp.server.fastmcp import FastMCP


ROOT_DIR = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:9001"
HEALTH_URL = f"{BASE_URL}/health"
FLOW_URL = "https://labs.google/fx/tools/flow"
URL_RE = re.compile(r"https?://[^\s)>\"]+")
DEFAULT_DOWNLOADS_DIR = Path.home() / "Downloads"
FLOW_ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"}
FLOW_BROWSER_SCRIPT = ROOT_DIR / "scripts" / "flow_browser_automation.py"
FLOW_DESKTOP_SCRIPT = ROOT_DIR / "scripts" / "flow_desktop_control.py"
SOURCE_COLLECT_SCRIPT = ROOT_DIR / "scripts" / "source_collect_job.py"
STEPWISE_DIR = ROOT_DIR / "storage" / "stepwise_workflows"
STEPWISE_LATEST_PATH = STEPWISE_DIR / "latest.json"
SOURCE_DRAFT_WORKER_LOCK = ROOT_DIR / "storage" / "source_draft_worker.lock"
SOURCE_DRAFT_WORKER_LOG = ROOT_DIR / "storage" / "logs" / "source_draft_worker.log"
SOURCE_COLLECT_LOG = ROOT_DIR / "storage" / "logs" / "source_collect_mcp.log"
RUNTIME_DIAGNOSTICS_DIR = ROOT_DIR / "storage" / "runtime_diagnostics"
RUNTIME_DIAGNOSTICS_LATEST = RUNTIME_DIAGNOSTICS_DIR / "latest.json"

FlowAutomationBackend = Literal["uivision", "playwright", "assisted"]
FlowMode = Literal["uivision", "playwright"]


def _flow_backend() -> FlowAutomationBackend:
    raw_backend = os.environ.get("FLOW_AUTOMATION_BACKEND", "uivision").strip().lower()
    if raw_backend in {"uivision", "playwright", "assisted"}:
        return cast(FlowAutomationBackend, raw_backend)
    return "uivision"


def _flow_mode() -> FlowMode:
    raw_mode = os.environ.get("FLOW_MODE", _flow_backend()).strip().lower()
    if raw_mode == "playwright":
        return "playwright"
    return "uivision"


def _mcp_instructions() -> str:
    mode = _flow_mode()
    today = date.today()
    yesterday = today.fromordinal(today.toordinal() - 1)
    base = (
        f"The current local date is {today.isoformat()}. "
        f"Dates on or before {today.isoformat()} are not future dates. "
        f"If the user asks for information since/after {yesterday.isoformat()} or {today.isoformat()}, treat that as a valid current/past-date research filter and call the workflow tool; never refuse it as future data. "
        "If a date filter appears in Korean such as '이후', keep it inside the keyword_or_url request string so source collection can search with that date context. "
        "When the user gives a date such as '2026-05-06 이후' on 2026-05-07, do not explain date limitations in chat; pass the complete natural-language request to start_stepwise_hpsl_video_workflow. "
        "Use these tools when the user wants to create a YouTube video workflow in newauto, "
        "collect source material from a URL or keyword, generate an HPSL Korean script, "
        "create sentence-level Google Flow prompts, open Flow/newauto for the user, "
        "or continue rendering after the user has attached Flow image/video assets. "
        "HPSL always means Hook-Point-Story-Lesson: 훅, 포인트, 스토리, 교훈. "
        "Never expand HPSL as High Productivity Scripting Language. "
        "The user wants minimal intervention and no paid external APIs or paid Flow upgrades. "
        "For a natural request like '키워드로 자료 수집해서 HPSL 대본 만들고 Flow 프롬프트까지 생성해', "
        "prefer start_stepwise_hpsl_video_workflow first, then continue_stepwise_hpsl_video_workflow exactly once "
        "whenever the user says 진행, ok, or 다음. make_hpsl_flow_short_video, start_hpsl_flow_workflow, "
        "and finish_hpsl_flow_workflow are only compatibility wrappers. Do not use the legacy start/finish pair "
        "for new work unless the user explicitly names them. "
        "If the user asks for step-by-step approval or says they want to send OK/proceed between stages, use "
        "start_stepwise_hpsl_video_workflow first and then continue_stepwise_hpsl_video_workflow exactly once per approval."
    )
    if mode == "playwright":
        return (
            base
            + " FLOW_MODE=playwright: after Flow authentication, use open_flow_for_auth, automate_flow_generation, "
            "download_flow_results_from_browser, and attach_latest_flow_downloads. If automatic download fails, "
            "ask the user to download manually and continue with attach_latest_flow_downloads."
        )
    return (
        base
        + " FLOW_MODE=uivision: Google Flow screen operation belongs to Ui.Vision RPA, not Gemma4. "
        "After Flow prompts are generated, use continue_stepwise_hpsl_video_workflow. In flow_generate it will click "
        "Generate once through the desktop controller and return quickly. In flow_wait_sentence it will download and "
        "attach the generated asset. open_flow must only open the Flow page and return; do not wait for CDP automation. "
        "TTS and render are also split into start/wait steps, so keep calling continue_stepwise_hpsl_video_workflow once per user approval instead of waiting for long jobs inside one tool call. "
        "When renamed files like flow_s001_*.png are downloaded, call attach_renamed_flow_downloads only as a fallback. "
        "Use attach_latest_flow_downloads only as a fallback for manual downloads."
    )


mcp = FastMCP(
    name="newauto-hpsl-flow",
    log_level="ERROR",
    instructions=_mcp_instructions(),
)


class NewautoError(RuntimeError):
    pass


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def _object_to_int(value: object, fallback: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return fallback
    return fallback


def _json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    form: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, object]:
    url = f"{BASE_URL}{path}"
    headers: dict[str, str] = {}
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload_obj = json.loads(detail)
        except json.JSONDecodeError:
            payload_obj = {"detail": detail}
        message = payload_obj.get("detail") if isinstance(payload_obj, dict) else detail
        raise NewautoError(f"{method} {path} failed: HTTP {exc.code} {message}") from exc
    except urllib.error.URLError as exc:
        raise NewautoError(f"newauto server is not reachable at {BASE_URL}: {exc}") from exc
    if not raw:
        return {}
    try:
        payload_obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NewautoError(f"{method} {path} returned invalid JSON: {raw[:200]}") from exc
    if not isinstance(payload_obj, dict):
        raise NewautoError(f"{method} {path} returned non-object JSON.")
    return cast(dict[str, object], payload_obj)


def _health_ok() -> bool:
    try:
        payload = _json_request("GET", "/health", timeout=5)
    except NewautoError:
        return False
    return payload.get("ok") is True


def _run_text_command(command: list[str], *, timeout: int = 5) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"error: {exc}"
    output = (completed.stdout or completed.stderr).strip()
    return output or f"exit={completed.returncode}"


def _git_commit(short: bool = True) -> str:
    args = ["git", "rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    result = _run_text_command(args, timeout=5)
    if result.startswith("error:") or result.startswith("exit="):
        return result
    return result.splitlines()[0].strip()


def _mcp_file_hash() -> str:
    return md5(Path(__file__).read_bytes()).hexdigest()[:8]


def _powershell(script: str, *, timeout: int = 5) -> str:
    return _run_text_command(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        timeout=timeout,
    )


def _port_owner_pid(port: int) -> str:
    script = (
        f"$p=(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue "
        "| Select-Object -First 1 -ExpandProperty OwningProcess); "
        "if ($p) { [string]$p }"
    )
    result = _powershell(script)
    return result.strip() or "none"


def _process_command_line(pid: str) -> str:
    if not pid.strip() or pid == "none":
        return ""
    script = (
        f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" -ErrorAction SilentlyContinue; "
        "if ($p) { $p.CommandLine }"
    )
    return _powershell(script, timeout=5)


def _resolved_omnivoice_python() -> str:
    script_path = ROOT_DIR / "scripts" / "resolve_omnivoice_python.ps1"
    if not script_path.exists():
        return f"missing: {script_path}"
    return _run_text_command(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
        timeout=10,
    )


def _mcp_process_lines() -> list[str]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -match 'newauto_mcp.py|run-newauto-mcp' } | "
        "ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }"
    )
    output = _powershell(script, timeout=8)
    if not output or output.startswith("error:") or output.startswith("exit="):
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _flow_window_lines() -> list[str]:
    try:
        import pygetwindow as gw
    except Exception as exc:
        return [f"pygetwindow unavailable: {exc}"]
    lines: list[str] = []
    for window in gw.getAllWindows():
        title = str(window.title)
        if "Flow" not in title:
            continue
        lines.append(f"{title}|{window.left},{window.top},{window.width},{window.height}")
    return lines


def _start_newauto_server() -> None:
    run_bat = ROOT_DIR / "run-newauto-9001.cmd"
    if not run_bat.exists():
        raise NewautoError(f"run.bat not found: {run_bat}")
    command = (
        "Start-Process -WindowStyle Hidden "
        f"-FilePath '{run_bat}' "
        f"-WorkingDirectory '{ROOT_DIR}'"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def _ensure_server(timeout_sec: int = 45) -> None:
    if _health_ok():
        return
    _start_newauto_server()
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _health_ok():
            return
        time.sleep(1.0)
    raise NewautoError(
        "newauto server did not become ready. Open C:/Users/petbl/newauto/run.bat once, "
        "then ask me to continue."
    )


def _extract_project(payload: dict[str, object]) -> dict[str, object]:
    project = payload.get("project")
    if isinstance(project, dict):
        return cast(dict[str, object], project)
    return payload


def _project_url(pid: str, *, step: int = 2) -> str:
    return f"{BASE_URL}/?project={urllib.parse.quote(pid)}&step={step}"


def _is_url(text: str) -> bool:
    return URL_RE.search(text) is not None


def _first_url(text: str) -> str:
    match = URL_RE.search(text)
    if match is None:
        raise NewautoError("No URL found in input.")
    return match.group(0).rstrip(".,")


def _keyword_from_blocked_url(url: str, original_request: str) -> str:
    parsed = urllib.parse.urlparse(url)
    slug_text = " ".join(
        part
        for part in re.split(r"[-_/]+", urllib.parse.unquote(parsed.path))
        if part and not part.isdigit() and len(part) > 1
    )
    host_text = parsed.netloc.replace("www.", "").split(":")[0]
    request_without_url = URL_RE.sub(" ", original_request)
    keyword = " ".join((request_without_url, slug_text, host_text)).strip()
    keyword = re.sub(r"\s+", " ", keyword)
    return keyword[:220] or host_text or "latest AI news"


def _poll_project(pid: str, *, timeout_sec: int = 900) -> dict[str, object]:
    deadline = time.time() + timeout_sec
    last_project: dict[str, object] = {}
    while time.time() < deadline:
        project = _json_request("GET", f"/api/projects/{pid}", timeout=15)
        last_project = project
        state = str(project.get("source_draft_state") or "")
        if state == "done":
            return project
        if state == "error":
            raise NewautoError(str(project.get("source_draft_error") or "source draft generation failed"))
        time.sleep(3.0)
    raise NewautoError(f"Timed out waiting for HPSL generation. Last project state: {last_project}")


def _prepare_sources_for_project(pid: str, request: str) -> str:
    clean_request = request.strip()
    if _is_url(clean_request):
        source_url = _first_url(clean_request)
        try:
            _json_request("POST", f"/api/projects/{pid}/source/url/analyze", form={"url": source_url}, timeout=120)
            return f"URL: {source_url}"
        except NewautoError as exc:
            fallback_keyword = _keyword_from_blocked_url(source_url, clean_request)
            _json_request(
                "POST",
                f"/api/projects/{pid}/source/keyword/collect",
                form={"keyword": fallback_keyword},
                timeout=180,
            )
            return f"URL blocked, fallback keyword: {fallback_keyword} (blocked URL: {source_url}; reason: {exc})"
    _json_request("POST", f"/api/projects/{pid}/source/keyword/collect", form={"keyword": clean_request}, timeout=180)
    return f"keyword: {clean_request}"


def _source_collect_command(pid: str, request: str) -> list[str]:
    clean_request = request.strip()
    if _is_url(clean_request):
        source_url = _first_url(clean_request)
        mode = "url"
        query = source_url
    else:
        mode = "keyword"
        query = clean_request
    return [
        sys.executable,
        str(SOURCE_COLLECT_SCRIPT),
        "--project-id",
        pid,
        "--mode",
        mode,
        "--query",
        query,
    ]


def _enqueue_source_collection(pid: str, request: str) -> str:
    clean_request = request.strip()
    if not clean_request:
        raise NewautoError("source collection request is empty.")
    SOURCE_COLLECT_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_handle = SOURCE_COLLECT_LOG.open("a", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(
        _source_collect_command(pid, clean_request),
        cwd=str(ROOT_DIR),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=(
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform.startswith("win")
            else 0
        ),
    )
    log_handle.close()
    if _is_url(clean_request):
        return f"URL collection queued: {_first_url(clean_request)}"
    return f"keyword collection queued: {clean_request}"


def _check_source_collection_done(pid: str) -> dict[str, object] | None:
    project = _json_request("GET", f"/api/projects/{pid}", timeout=15)
    source_state = str(project.get("source_draft_state") or "")
    source_count, _, _ = _project_counts(project)
    if source_state == "done" and source_count > 0:
        return project
    if source_state == "error":
        raise NewautoError(str(project.get("source_draft_error") or "source collection failed"))
    return None


def _task_status(pid: str, task_key: str) -> dict[str, object]:
    project = _json_request("GET", f"/api/projects/{pid}/status", timeout=15)
    task_state = str(project.get(f"{task_key}_state") or "")
    if task_state == "error":
        raise NewautoError(str(project.get(f"{task_key}_error") or f"{task_key} failed"))
    return project


def _check_task_done(pid: str, task_key: str) -> dict[str, object] | None:
    project = _task_status(pid, task_key)
    if str(project.get(f"{task_key}_state") or "") == "done":
        return project
    return None


def _brief_prompt_queue(manifest: dict[str, object], *, limit: int = 5, include_prompts: bool = False) -> str:
    entries_obj = manifest.get("entries")
    if not isinstance(entries_obj, list):
        return "No Flow prompt entries were returned."
    lines: list[str] = []
    for raw_entry in entries_obj[:limit]:
        if not isinstance(raw_entry, dict):
            continue
        idx = raw_entry.get("sentence_idx")
        narration = str(raw_entry.get("narration") or "")
        prompt = str(raw_entry.get("prompt") or "")
        status = str(raw_entry.get("status") or "")
        line = f"- sentence {int(idx) + 1 if isinstance(idx, int) else '?'} [{status}] {narration[:120]}"
        if include_prompts:
            line += f"\n  flow prompt: {prompt[:700]}"
        lines.append(line)
    return "\n".join(lines) if lines else "No usable Flow prompt entries were returned."


def _project_sentence_asset_status(project: dict[str, object]) -> tuple[int, int, list[int]]:
    sentences = project.get("sentences")
    mappings = project.get("body_image_mappings")
    sentence_count = len(sentences) if isinstance(sentences, list) else 0
    mapped_indexes = _mapped_sentence_indexes(mappings)
    missing = [index + 1 for index in range(sentence_count) if index not in mapped_indexes]
    return sentence_count, len(mapped_indexes), missing


def _project_coverage_text(project_id: str) -> str:
    if not project_id.strip():
        return "project_id not provided"
    try:
        project = _json_request("GET", f"/api/projects/{project_id}", timeout=10)
        sentence_count, attached_count, missing = _project_sentence_asset_status(project)
    except NewautoError as exc:
        return f"error: {exc}"
    return f"{attached_count}/{sentence_count} missing={missing}"


def _stepwise_next_step(project_id: str) -> str:
    try:
        state = _load_stepwise_state(project_id)
    except Exception as exc:
        return f"error: {exc}"
    return str(state.get("next_step") or "")


def _runtime_snapshot(project_id: str = "") -> dict[str, object]:
    pid_9001 = _port_owner_pid(9001)
    pid_1234 = _port_owner_pid(1234)
    pid_9223 = _port_owner_pid(9223)
    stepwise_state: dict[str, object] = {}
    if project_id.strip():
        try:
            stepwise_state = _load_stepwise_state(project_id)
        except Exception as exc:
            stepwise_state = {"error": str(exc)}
    coverage = _project_coverage_text(project_id) if project_id.strip() else "project_id not provided"
    snapshot: dict[str, object] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "project_id": project_id,
        "mcp_script": str(Path(__file__).resolve()),
        "mcp_file_hash": _mcp_file_hash(),
        "git_commit": _git_commit(short=False),
        "git_commit_short": _git_commit(short=True),
        "mcp_pid": os.getpid(),
        "python_executable": sys.executable,
        "cwd": str(ROOT_DIR),
        "base_url": BASE_URL,
        "flow_automation_backend": _flow_backend(),
        "flow_mode": _flow_mode(),
        "api_server_ok": _health_ok(),
        "api_server_pid_9001": pid_9001,
        "api_server_command_9001": _process_command_line(pid_9001),
        "resolved_omnivoice_python": _resolved_omnivoice_python(),
        "lmstudio_server_pid_1234": pid_1234,
        "flow_cdp_pid_9223": pid_9223,
        "mcp_processes": _mcp_process_lines(),
        "flow_windows": _flow_window_lines(),
        "stepwise_state": stepwise_state,
        "stepwise_next_step": str(stepwise_state.get("next_step") or ""),
        "asset_coverage": coverage,
    }
    RUNTIME_DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIAGNOSTICS_LATEST.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def _debug_footer(next_step_before: str = "", next_step_after: str = "") -> str:
    api_pid = _port_owner_pid(9001)
    lines = [
        "---",
        f"mcp_commit: {_git_commit(short=True)}",
        f"mcp_pid: {os.getpid()}",
        f"api_pid_9001: {api_pid}",
    ]
    if next_step_before or next_step_after:
        lines.append(f"step: {next_step_before or '?'} -> {next_step_after or '?'}")
    return "\n".join(lines)


def _append_debug_footer(message: str, *, project_id: str = "", next_step_before: str = "") -> str:
    next_step_after = ""
    if project_id.strip():
        try:
            state = _load_stepwise_state(project_id)
            next_step_after = str(state.get("next_step") or "")
        except Exception:
            next_step_after = ""
    return f"{message}\n\n{_debug_footer(next_step_before, next_step_after)}"


def _mapped_sentence_indexes(mappings: object) -> set[int]:
    mapped_indexes: set[int] = set()
    if not isinstance(mappings, list):
        return mapped_indexes
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        raw_sentence_idx = mapping.get("sentence_idx")
        if isinstance(raw_sentence_idx, int):
            mapped_indexes.add(raw_sentence_idx)
    return mapped_indexes


def _latest_flow_asset_paths(downloads_dir: Path, *, limit: int, since_minutes: int = 180) -> list[str]:
    if not downloads_dir.exists():
        raise NewautoError(f"Downloads folder not found: {downloads_dir}")
    cutoff = time.time() - max(1, since_minutes) * 60
    candidates = [
        path
        for path in downloads_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in FLOW_ASSET_EXTENSIONS
        and path.stat().st_mtime >= cutoff
        and not path.name.endswith(".crdownload")
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    selected = candidates[: max(1, limit)]
    selected.reverse()
    return [str(path) for path in selected]


def _uivision_project_dir(project_id: str) -> Path:
    path = ROOT_DIR / "storage" / "projects" / project_id / "uivision"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _uivision_marker_path(project_id: str) -> Path:
    return _uivision_project_dir(project_id) / "run_done.json"


def _uivision_file_overview(project_id: str) -> str:
    directory = _uivision_project_dir(project_id)
    csv_path = directory / "flow_prompts.csv"
    marker_path = _uivision_marker_path(project_id)
    return (
        f"- Ui.Vision folder: {directory}\n"
        f"- CSV: {csv_path}\n"
        f"- marker: {marker_path}"
    )


def _prepare_uivision_payload(project_id: str) -> dict[str, object]:
    return _json_request("POST", f"/api/flow/prompts/{project_id}/uivision/prepare", timeout=30)


def _uivision_instructions(project_id: str, *, sentence_number: int = 1, batch: bool = False) -> str:
    mode = "6문장 batch" if batch else f"{sentence_number}번 문장 단건"
    return (
        f"Ui.Vision으로 Flow {mode} 생성을 진행할 준비가 됐어.\n\n"
        f"- project_id: {project_id}\n"
        f"{_uivision_file_overview(project_id)}\n\n"
        "사용자님이 해줄 일:\n"
        "1. Flow 로그인/권한승인 화면이 있으면 승인\n"
        "2. Ui.Vision에서 Flow_Generate_One 또는 Flow_Generate_Batch 매크로 실행\n"
        "3. 매크로가 다운로드 파일을 `flow_s001_...` 형식으로 저장/rename했는지 확인\n"
        "4. 끝나면 LM Studio에 `진행`이라고 입력\n\n"
        "주의: 매크로 실행 중에는 Flow 브라우저를 건드리지 말아줘. "
        "결제/4K 업그레이드/유료 크레딧 버튼은 누르면 안 돼."
    )


def _run_flow_browser_script(args: list[str], *, timeout_sec: int = 180) -> dict[str, object]:
    command = [sys.executable, str(FLOW_BROWSER_SCRIPT), *args]
    completed = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise NewautoError(
            "Flow browser automation failed: "
            f"{completed.stderr.strip() or completed.stdout.strip() or completed.returncode}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise NewautoError(f"Flow browser automation returned invalid JSON: {completed.stdout[:500]}") from exc
    if not isinstance(payload, dict):
        raise NewautoError("Flow browser automation returned non-object JSON.")
    return cast(dict[str, object], payload)


def _run_flow_desktop_control(
    project_id: str,
    sentence_number: int,
    *,
    mode: str,
    downloads_before: list[str] | None = None,
    wait_seconds: int = 62,
    download_timeout_seconds: int = 45,
) -> dict[str, object]:
    python_command = os.environ.get("NEWAUTO_DESKTOP_PYTHON", "python").strip() or "python"
    command = [
        python_command,
        str(FLOW_DESKTOP_SCRIPT),
        project_id,
        "--sentence",
        str(sentence_number),
        "--mode",
        mode,
        "--wait-seconds",
        str(wait_seconds),
        "--download-timeout-seconds",
        str(download_timeout_seconds),
        "--api-base",
        BASE_URL,
    ]
    if downloads_before is not None:
        command.extend(["--downloads-before-json", json.dumps(downloads_before, ensure_ascii=False)])
    subprocess_timeout = 35 if mode == "click-generate" else max(90, download_timeout_seconds + 35)
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=subprocess_timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        code = "FLOW_GENERATE_CLICK_TIMEOUT" if mode == "click-generate" else "MCP_TRANSPORT_TIMEOUT_SUSPECTED"
        raise NewautoError(
            f"{code}: Flow desktop control exceeded {subprocess_timeout}s. "
            f"stdout={str(exc.stdout or '')[:300]} stderr={str(exc.stderr or '')[:300]}"
        ) from exc
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout.strip())
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            parsed_payload = cast(dict[str, object], payload)
            if completed.returncode == 0 or parsed_payload.get("ok") is False:
                return parsed_payload
    if completed.returncode != 0:
        combined_error = completed.stderr.strip() or completed.stdout.strip() or str(completed.returncode)
        if "Flow browser window was not found" in combined_error:
            code = "FLOW_WINDOW_NOT_FOUND"
        elif "No completed new Flow download" in combined_error:
            code = "FLOW_DOWNLOAD_NOT_READY"
        elif "attach failed" in combined_error:
            code = "FLOW_ATTACH_FAILED"
        elif mode == "click-generate":
            code = "FLOW_GENERATE_CLICK_FAILED"
        else:
            code = "FLOW_DESKTOP_CONTROL_FAILED"
        raise NewautoError(
            f"{code}: Flow desktop control failed: {combined_error}"
        )
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise NewautoError(f"Flow desktop control returned invalid JSON: {completed.stdout[:500]}") from exc
    if not isinstance(payload, dict):
        raise NewautoError("Flow desktop control returned non-object JSON.")
    return cast(dict[str, object], payload)


def _set_stepwise_fields(state: dict[str, object], fields: dict[str, object]) -> dict[str, object]:
    updated = dict(state)
    updated.update(fields)
    updated["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_stepwise_state(updated)
    return updated


def _pending_attach_path(project_id: str, sentence_number: int) -> Path:
    return _uivision_project_dir(project_id) / f"pending_attach_{sentence_number:03d}.json"


def _load_pending_attach(project_id: str, sentence_number: int) -> dict[str, object] | None:
    path = _pending_attach_path(project_id, sentence_number)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise NewautoError(f"Pending attach file is invalid: {path}")
    return cast(dict[str, object], payload)


def _attach_pending_flow_asset(project_id: str, sentence_number: int, pending: dict[str, object]) -> dict[str, object]:
    asset_path = str(pending.get("asset_path") or "")
    if not asset_path:
        raise NewautoError(f"Pending attach for sentence {sentence_number} has no asset_path.")
    response = _json_request(
        "POST",
        f"/api/flow/assets/{project_id}/attach-local",
        payload={"paths": [asset_path], "start_sentence_number": sentence_number},
        timeout=60,
    )
    _pending_attach_path(project_id, sentence_number).unlink(missing_ok=True)
    return response


def _object_to_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return f'"{pid}"' in completed.stdout
    try:
        import os

        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    return True


def _ensure_source_draft_worker(timeout_sec: int = 20) -> None:
    if SOURCE_DRAFT_WORKER_LOCK.exists():
        try:
            worker_pid = int(SOURCE_DRAFT_WORKER_LOCK.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            worker_pid = 0
        if worker_pid and _pid_exists(worker_pid):
            return
        SOURCE_DRAFT_WORKER_LOCK.unlink(missing_ok=True)
    SOURCE_DRAFT_WORKER_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_handle = SOURCE_DRAFT_WORKER_LOG.open("a", encoding="utf-8")
    env = dict(os.environ)
    env["LLM_PROVIDER"] = "lmstudio"
    env["LMSTUDIO_BASE_URL"] = "http://127.0.0.1:1234"
    env["SCRIPT_LLM_MODEL"] = "google/gemma-4-e4b"
    subprocess.Popen(
        [sys.executable, "-m", "app.workers.source_draft_worker"],
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
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if SOURCE_DRAFT_WORKER_LOCK.exists():
            return
        time.sleep(0.5)
    raise NewautoError("source draft worker did not start.")


def _stepwise_path(project_id: str) -> Path:
    STEPWISE_DIR.mkdir(parents=True, exist_ok=True)
    return STEPWISE_DIR / f"{project_id}.json"


def _save_stepwise_state(state: dict[str, object]) -> None:
    STEPWISE_DIR.mkdir(parents=True, exist_ok=True)
    project_id = str(state.get("project_id") or "")
    if not project_id:
        raise NewautoError("stepwise state is missing project_id.")
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    _stepwise_path(project_id).write_text(payload, encoding="utf-8")
    STEPWISE_LATEST_PATH.write_text(payload, encoding="utf-8")


def _load_stepwise_state(project_id: str = "") -> dict[str, object]:
    path = _stepwise_path(project_id.strip()) if project_id.strip() else STEPWISE_LATEST_PATH
    if not path.exists():
        raise NewautoError("No stepwise workflow state exists. Start with start_stepwise_hpsl_video_workflow.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise NewautoError("Stepwise workflow state is invalid.")
    return cast(dict[str, object], payload)


def _set_next_step(state: dict[str, object], next_step: str) -> dict[str, object]:
    updated = dict(state)
    updated["next_step"] = next_step
    updated["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_stepwise_state(updated)
    return updated


def _project_counts(project: dict[str, object]) -> tuple[int, int, int]:
    sources = project.get("source_draft_sources")
    sentences = project.get("sentences")
    warnings = project.get("source_draft_warnings")
    return (
        len(sources) if isinstance(sources, list) else 0,
        len(sentences) if isinstance(sentences, list) else 0,
        len(warnings) if isinstance(warnings, list) else 0,
    )


def _draft_sentence_count(project: dict[str, object]) -> int:
    draft = str(project.get("source_draft_script") or "").strip()
    if not draft:
        return 0
    return len([line for line in draft.splitlines() if line.strip()])


def _enqueue_hpsl_script(pid: str, state: dict[str, object]) -> None:
    _ensure_source_draft_worker()
    _json_request(
        "POST",
        f"/api/projects/{pid}/source/script/generate",
        form={
            "tone": str(state.get("tone") or "설명형"),
            "target_minutes": str(max(1, min(8, _object_to_int(state.get("target_minutes"), 1)))),
            "language": "ko",
            "mode": "",
            "note": "HPSL은 훅-포인트-스토리-교훈 구조다. 이 4단계를 지키고, 각 문장이 Flow 장면 하나가 되게 작성해.",
            "script_structure": "hpsl",
        },
        timeout=30,
    )


def _check_hpsl_script_done(pid: str) -> dict[str, object] | None:
    project = _json_request("GET", f"/api/projects/{pid}", timeout=15)
    draft_state = str(project.get("source_draft_state") or "")
    if draft_state == "done" and _draft_sentence_count(project) > 0:
        return project
    if draft_state == "error":
        raise NewautoError(str(project.get("source_draft_error") or "source draft generation failed"))
    return None


def _enqueue_tts(pid: str, voice_preset: str) -> dict[str, object]:
    project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
    if str(project.get("tts_state") or "") in {"queued", "running", "done"}:
        return project
    _json_request(
        "POST",
        f"/api/projects/{pid}/tts",
        payload={
            "voice_preset": voice_preset,
            "tts_profile": {
                "mode": "design",
                "synthesis_mode": "full_passage",
                "language": "ko",
            },
        },
        timeout=30,
    )
    return _task_status(pid, "tts")


def _enqueue_render(pid: str) -> dict[str, object]:
    project = _json_request("GET", f"/api/projects/{pid}/status", timeout=30)
    if str(project.get("render_state") or "") in {"queued", "running", "done"}:
        return project
    _json_request("POST", f"/api/projects/{pid}/scene-plan/build", timeout=60)
    _json_request("POST", f"/api/projects/{pid}/render-plan/build", timeout=60)
    preflight = _json_request("GET", f"/api/projects/{pid}/preflight", timeout=60)
    if preflight.get("ok") is not True:
        checks = preflight.get("checks")
        failed: list[str] = []
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, dict) and check.get("ok") is not True:
                    failed.append(f"{check.get('key')}: {check.get('message')}")
        raise NewautoError("Preflight failed: " + "; ".join(failed[:8]))
    _json_request("POST", f"/api/projects/{pid}/render", timeout=30)
    return _task_status(pid, "render")


@mcp.tool()
def start_stepwise_hpsl_video_workflow(
    keyword_or_url: str,
    title: str = "",
    target_minutes: int = 1,
    tone: str = "설명형",
) -> str:
    """Start an approval-gated video workflow. Do not reject user date filters; pass them through in keyword_or_url."""
    _configure_stdout()
    _ensure_server()
    clean_request = keyword_or_url.strip()
    if not clean_request:
        return "키워드나 URL을 알려줘."
    project_title = title.strip() or clean_request[:70] or "Stepwise HPSL Flow Shorts"
    created = _json_request("POST", "/api/projects", form={"title": project_title})
    pid = str(created.get("id") or "")
    if not pid:
        raise NewautoError("newauto project creation did not return an id.")
    source_mode = _enqueue_source_collection(pid, clean_request)
    state: dict[str, object] = {
        "project_id": pid,
        "request": clean_request,
        "title": project_title,
        "target_minutes": max(1, min(8, int(target_minutes or 1))),
        "tone": tone,
        "source_mode": source_mode,
        "next_step": "source_collect_wait",
        "voice_preset": "male-announcer-40s-50s",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _save_stepwise_state(state)
    webbrowser.open(_project_url(pid, step=1))
    return (
        "1단계 시작: 자료 수집을 백그라운드로 시작했어.\n\n"
        f"- project_id: {pid}\n"
        f"- source: {source_mode}\n"
        f"- newauto: {_project_url(pid, step=1)}\n\n"
        "다음 단계: 자료 수집 완료 여부 확인.\n"
        "`진행`, `ok`, `다음`이라고 말하면 완료 여부만 확인하고, 끝났을 때 대본 생성 단계로 넘길게."
    )


def _continue_stepwise_hpsl_video_workflow_impl(project_id: str = "") -> str:
    """Run exactly one next step in the approval-gated HPSL Flow video workflow, then stop and ask for approval."""
    _configure_stdout()
    _ensure_server()
    state = _load_stepwise_state(project_id)
    pid = str(state.get("project_id") or "")
    if not pid:
        raise NewautoError("Stepwise state is missing project_id.")
    next_step = str(state.get("next_step") or "")

    if next_step == "source_collect":
        clean_request = str(state.get("request") or "").strip()
        if not clean_request:
            return "자료 수집을 재시도할 원본 키워드/URL이 상태에 없어. 새 워크플로우로 다시 시작해줘."
        source_mode = _enqueue_source_collection(pid, clean_request)
        _set_stepwise_fields(state, {"next_step": "source_collect_wait", "source_mode": source_mode})
        return (
            "1단계 재시작: 자료 수집을 백그라운드로 다시 시작했어.\n\n"
            f"- project_id: {pid}\n"
            f"- source: {source_mode}\n\n"
            "`진행`이라고 말하면 완료 여부만 확인할게."
        )

    if next_step == "source_collect_wait":
        try:
            project = _check_source_collection_done(pid)
        except NewautoError as exc:
            _set_stepwise_fields(state, {"next_step": "source_collect"})
            return (
                "1단계 확인: 자료 수집이 오류 상태야.\n\n"
                f"- project_id: {pid}\n"
                f"- reason: {exc}\n\n"
                "같은 요청으로 자료 수집을 다시 시작하려면 `진행`이라고 말해줘."
            )
        if project is None:
            project_status = _json_request("GET", f"/api/projects/{pid}", timeout=15)
            draft_state = str(project_status.get("source_draft_state") or "idle")
            progress = project_status.get("source_draft_progress")
            phase = str(project_status.get("source_draft_phase") or "")
            last_log = str(project_status.get("source_draft_last_log") or "")
            return (
                "1단계 진행 중: 자료 수집이 아직 끝나지 않았어.\n\n"
                f"- project_id: {pid}\n"
                f"- source_draft_state: {draft_state}\n"
                f"- progress: {progress}\n"
                f"- phase: {phase or '-'}\n"
                f"- last_log: {last_log or '-'}\n\n"
                "잠시 뒤 `진행`이라고 말하면 다시 확인할게."
            )
        source_count, _, warning_count = _project_counts(project)
        _set_stepwise_fields(state, {"next_step": "script_generate"})
        return (
            "1단계 완료: 자료 수집이 성공했어.\n\n"
            f"- project_id: {pid}\n"
            f"- collected sources: {source_count}\n"
            f"- warnings: {warning_count}\n\n"
            "다음 단계: HPSL(훅-포인트-스토리-교훈) 대본 생성.\n"
            "`진행`이라고 말하면 대본 생성만 실행할게."
        )

    if next_step == "script_generate":
        completed_project = _check_hpsl_script_done(pid)
        if completed_project is not None:
            source_count, _, warning_count = _project_counts(completed_project)
            draft_sentence_count = _draft_sentence_count(completed_project)
            _set_next_step(state, "flow_prompts")
            return (
                "2단계 완료: HPSL(훅-포인트-스토리-교훈) 대본 생성이 이미 끝나 있었어.\n\n"
                f"- project_id: {pid}\n"
                f"- sources used: {source_count}\n"
                f"- draft sentences: {draft_sentence_count}\n"
                f"- warnings: {warning_count}\n"
                f"- newauto: {_project_url(pid, step=1)}\n\n"
                "다음 단계: 대본 적용 + 문장별 Flow 프롬프트 생성.\n"
                "`진행`이라고 말하면 다음 단계만 실행할게."
            )
        project = _json_request("GET", f"/api/projects/{pid}", timeout=15)
        draft_state = str(project.get("source_draft_state") or "")
        if draft_state not in {"queued", "running"}:
            _enqueue_hpsl_script(pid, state)
        _set_stepwise_fields(
            state,
            {
                "next_step": "script_generate_wait",
                "script_generate_started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        )
        return (
            "2단계 시작: HPSL(훅-포인트-스토리-교훈) 대본 생성을 큐에 등록했어.\n\n"
            f"- project_id: {pid}\n"
            f"- source_draft_state: {draft_state or 'queued'}\n"
            f"- newauto: {_project_url(pid, step=1)}\n\n"
            "생성은 백그라운드 worker가 진행해. 10~30초 뒤 `진행`이라고 말하면 완료 여부만 확인할게."
        )

    if next_step == "script_generate_wait":
        try:
            wait_project = _check_hpsl_script_done(pid)
        except NewautoError as exc:
            return (
                "2단계 실패: HPSL 대본 생성 worker가 오류를 반환했어.\n\n"
                f"- project_id: {pid}\n"
                f"- reason: {exc}\n\n"
                "서버/MCP를 재시작한 뒤 다시 `진행`이라고 말하면 같은 단계에서 복구를 시도할 수 있어."
            )
        if wait_project is None:
            project_peek = _json_request("GET", f"/api/projects/{pid}", timeout=15)
            draft_state = str(project_peek.get("source_draft_state") or "idle")
            draft_phase = str(project_peek.get("source_draft_phase") or "")
            draft_error = str(project_peek.get("source_draft_error") or "")
            return (
                "2단계 대기 중: HPSL 대본 생성이 아직 끝나지 않았어.\n\n"
                f"- project_id: {pid}\n"
                f"- source_draft_state: {draft_state}\n"
                f"- source_draft_phase: {draft_phase or 'n/a'}\n"
                f"- source_draft_error: {draft_error or 'none'}\n\n"
                "조금 뒤 `진행`이라고 말하면 같은 단계에서 다시 확인할게."
            )
        source_count, _, warning_count = _project_counts(wait_project)
        draft_sentence_count = _draft_sentence_count(wait_project)
        _set_next_step(state, "flow_prompts")
        return (
            "2단계 완료: HPSL(훅-포인트-스토리-교훈) 대본 생성이 끝났어.\n\n"
            f"- project_id: {pid}\n"
            f"- sources used: {source_count}\n"
            f"- draft sentences: {draft_sentence_count}\n"
            f"- warnings: {warning_count}\n"
            f"- newauto: {_project_url(pid, step=1)}\n\n"
            "다음 단계: 대본 적용 + 문장별 Flow 프롬프트 생성.\n"
            "`진행`이라고 말하면 다음 단계만 실행할게."
        )

    if next_step == "flow_prompts":
        _json_request("POST", f"/api/projects/{pid}/source/script/apply", form={}, timeout=30)
        manifest = _json_request(
            "POST",
            f"/api/flow/prompts/{pid}",
            payload={"aspect_ratio": "9:16", "mode": "assisted"},
            timeout=30,
        )
        uivision_payload = _prepare_uivision_payload(pid)
        project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
        _, sentence_count, _ = _project_counts(project)
        entries = manifest.get("entries")
        prompt_count = len(entries) if isinstance(entries, list) else 0
        _set_next_step(state, "flow_auth")
        webbrowser.open(_project_url(pid, step=2))
        csv_path = str(uivision_payload.get("csv_path") or "")
        return (
            "3단계 완료: 대본 적용과 Flow 프롬프트 생성이 끝났어.\n\n"
            f"- project_id: {pid}\n"
            f"- script sentences: {sentence_count}\n"
            f"- Flow prompts: {prompt_count}\n"
            f"- Ui.Vision CSV: {csv_path}\n"
            f"- newauto: {_project_url(pid, step=2)}\n\n"
            "다음 단계: Flow 인증/Ui.Vision 준비.\n"
            "`진행`이라고 말하면 현재 backend에 맞춰 다음 단계만 안내하거나 실행할게."
        )

    if next_step == "flow_auth":
        backend = _flow_backend()
        if backend == "uivision":
            webbrowser.open(FLOW_URL)
            _set_next_step(state, "flow_generate")
            return (
                "4단계 준비 완료: Ui.Vision 방식으로 Flow를 열었어.\n\n"
                f"- project_id: {pid}\n"
                f"- backend: {backend}\n"
                f"{_uivision_file_overview(pid)}\n\n"
                "Flow 로그인/권한승인이 필요하면 사용자님이 승인해줘.\n"
                "인증이 끝났거나 이미 로그인되어 있으면 `진행`이라고 말해줘. "
                "다음에는 Ui.Vision 매크로 실행 안내로 넘어갈게."
            )
        if backend == "assisted":
            webbrowser.open(FLOW_URL)
            _set_next_step(state, "flow_generate")
            return (
                "4단계 준비 완료: 수동 보조 방식으로 Flow를 열었어.\n\n"
                f"- project_id: {pid}\n"
                f"{_uivision_file_overview(pid)}\n\n"
                "Flow 로그인/권한승인을 완료한 뒤 `진행`이라고 말해줘. "
                "다음에는 프롬프트 파일 위치와 수동 입력 순서를 안내할게."
            )
        result = _run_flow_browser_script(["open", "--project-id", pid], timeout_sec=60)
        _set_next_step(state, "flow_generate")
        return (
            "4단계 준비 완료: Flow 인증 브라우저를 열었어.\n\n"
            f"- project_id: {pid}\n"
            f"- result: {result.get('message') or result}\n\n"
            "여기서는 사용자님 작업이 필요해: Flow 로그인/권한승인을 완료해줘.\n"
            "인증이 끝나면 `진행`이라고 말해줘. 그때 프롬프트 입력과 Generate 클릭을 자동 시도할게."
        )

    if next_step == "flow_generate":
        backend = _flow_backend()
        if backend == "uivision":
            _prepare_uivision_payload(pid)
            project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
            sentence_count, attached_count, missing = _project_sentence_asset_status(project)
            if not missing:
                _set_next_step(state, "tts")
                return (
                    "4단계 완료: Flow 이미지가 이미 모든 문장에 연결되어 있어.\n\n"
                    f"- project_id: {pid}\n"
                    f"- coverage: {attached_count}/{sentence_count}\n\n"
                    "다음 단계: OmniVoice 음성 생성.\n"
                    "`진행`이라고 말하면 음성 생성만 실행하고 다시 멈출게."
                )
            sentence_number = missing[0]
            pending = _load_pending_attach(pid, sentence_number)
            if pending is not None:
                _set_stepwise_fields(
                    state,
                    {
                        "next_step": "flow_wait_sentence",
                        "active_sentence_number": sentence_number,
                    },
                )
                return (
                    "4단계 복구 대기: 이미 다운로드된 Flow 파일이 있고 attach만 남아 있어.\n\n"
                    f"- project_id: {pid}\n"
                    f"- target sentence: {sentence_number}\n"
                    f"- pending asset: {pending.get('asset_path')}\n\n"
                    "`진행`이라고 말하면 Flow를 다시 생성하지 않고 이 파일을 문장 asset에 연결할게."
                )
            try:
                result = _run_flow_desktop_control(pid, sentence_number, mode="click-generate")
            except NewautoError as exc:
                return (
                    "4단계 중단: Flow Generate 클릭 전에 사용자 확인이 필요해.\n\n"
                    f"- project_id: {pid}\n"
                    f"- target sentence: {sentence_number}\n"
                    f"- reason: {exc}\n\n"
                    "Flow 창이 로그인된 상태로 열려 있고, 생성 입력창이 보이는지 확인해줘. "
                    "인증/팝업을 처리한 뒤 `진행`이라고 말하면 같은 문장을 다시 시도할게."
                )
            downloads_before = _object_to_str_list(result.get("downloads_before"))
            screenshots = _object_to_str_list(result.get("screenshots"))
            _set_stepwise_fields(
                state,
                {
                    "next_step": "flow_wait_sentence",
                    "active_sentence_number": sentence_number,
                    "downloads_before": downloads_before,
                    "flow_generate_started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "flow_generate_screenshots": screenshots,
                },
            )
            return (
                "4단계 진행: Flow Generate 클릭만 완료했어.\n\n"
                f"- project_id: {pid}\n"
                f"- target sentence: {sentence_number}\n"
                f"- coverage before: {attached_count}/{sentence_count}\n"
                f"- screenshots: {screenshots}\n\n"
                "이 호출에서는 다운로드/attach를 기다리지 않았어. "
                "Flow 화면에 결과 이미지가 보이면 `진행`이라고 말해줘. 그러면 다운로드와 문장 연결만 실행할게."
            )
        if backend == "assisted":
            _prepare_uivision_payload(pid)
            _set_next_step(state, "flow_download")
            return (
                "4단계 대기: 수동 보조 방식으로 프롬프트를 입력해줘.\n\n"
                f"{_uivision_file_overview(pid)}\n"
                f"- single prompt API: {BASE_URL}/api/flow/prompts/{pid}/sentence/1\n\n"
                "Flow에 프롬프트를 입력하고 생성/다운로드를 완료한 뒤, "
                "파일명을 `flow_s001_...` 형식으로 맞춰서 `진행`이라고 말해줘."
            )
        result = _run_flow_browser_script(
            ["generate", "--project-id", pid, "--start-sentence-number", "1", "--limit", "0"],
            timeout_sec=240,
        )
        if result.get("ok") is not True:
            return (
                "4단계 중단: Flow 자동 입력/생성에서 사용자 확인이 필요해.\n\n"
                f"- project_id: {pid}\n"
                f"- reason: {result.get('message') or result}\n\n"
                "Flow 창에서 로그인/팝업/입력창 상태를 정리한 뒤 `진행`이라고 말해줘. 같은 단계를 다시 시도할게."
            )
        _set_next_step(state, "flow_download")
        return (
            "4단계 완료: Flow 프롬프트 입력과 Generate 클릭을 자동 시도했어.\n\n"
            f"- project_id: {pid}\n"
            f"- prompts processed: {result.get('processed')}\n\n"
            "다음 단계: Flow 결과 다운로드 자동 클릭/감지.\n"
            "결과가 화면에 생성됐으면 `진행`이라고 말해줘. 아직 생성 중이면 기다렸다가 말해줘."
        )

    if next_step == "flow_wait_sentence":
        sentence_number = _object_to_int(state.get("active_sentence_number"), 0)
        if sentence_number <= 0:
            _set_next_step(state, "flow_generate")
            return (
                "4단계 복구: 기다리는 문장 번호가 없어 flow_generate로 되돌렸어.\n\n"
                f"- project_id: {pid}\n\n"
                "`진행`이라고 말하면 빠진 문장부터 다시 Generate 클릭을 시도할게."
            )
        pending = _load_pending_attach(pid, sentence_number)
        try:
            if pending is not None:
                attach_response = _attach_pending_flow_asset(pid, sentence_number, pending)
                result = {
                    "ok": True,
                    "mode": "pending-attach",
                    "downloaded": pending.get("asset_path"),
                    "attached": attach_response.get("attached"),
                }
            else:
                downloads_before = _object_to_str_list(state.get("downloads_before"))
                result = _run_flow_desktop_control(
                    pid,
                    sentence_number,
                    mode="download-attach",
                    downloads_before=downloads_before,
                    download_timeout_seconds=45,
                )
        except NewautoError as exc:
            return (
                "4단계 대기: Flow 결과 다운로드/연결을 아직 끝내지 못했어.\n\n"
                f"- project_id: {pid}\n"
                f"- target sentence: {sentence_number}\n"
                f"- reason: {exc}\n\n"
                "Flow에서 해당 결과 이미지가 보이는지 확인해줘. 보이면 다시 `진행`이라고 말해줘. "
                "같은 문장을 재생성하지 않고 다운로드/attach만 다시 시도할게."
            )
        if result.get("ok") is not True:
            return (
                "4단계 대기: 다운로드는 되었지만 문장 연결이 아직 끝나지 않았어.\n\n"
                f"- project_id: {pid}\n"
                f"- target sentence: {sentence_number}\n"
                f"- downloaded: {result.get('downloaded')}\n"
                f"- pending_attach: {result.get('pending_attach')}\n"
                f"- error: {result.get('error')}\n\n"
                "`진행`이라고 말하면 같은 파일을 다시 attach만 시도할게."
            )
        refreshed = _json_request("GET", f"/api/projects/{pid}", timeout=30)
        sentence_count, attached_count, missing = _project_sentence_asset_status(refreshed)
        if missing:
            _set_stepwise_fields(
                state,
                {
                    "next_step": "flow_generate",
                    "active_sentence_number": 0,
                    "downloads_before": [],
                    "flow_generate_started_at": "",
                    "flow_generate_screenshots": [],
                },
            )
            return (
                "4단계 일부 완료: Flow 결과 다운로드와 문장 연결이 끝났어.\n\n"
                f"- project_id: {pid}\n"
                f"- completed sentence: {sentence_number}\n"
                f"- downloaded: {result.get('downloaded')}\n"
                f"- attached: {result.get('attached')}\n"
                f"- coverage: {attached_count}/{sentence_count}\n"
                f"- missing: {missing}\n\n"
                "`진행`이라고 말하면 다음 빠진 문장 Generate 클릭만 이어서 실행할게."
            )
        _set_stepwise_fields(
            state,
            {
                "next_step": "tts",
                "active_sentence_number": 0,
                "downloads_before": [],
                "flow_generate_started_at": "",
                "flow_generate_screenshots": [],
            },
        )
        return (
            "4단계 완료: Flow 이미지 생성/다운로드/문장별 연결이 모두 끝났어.\n\n"
            f"- project_id: {pid}\n"
            f"- completed sentence: {sentence_number}\n"
            f"- downloaded: {result.get('downloaded')}\n"
            f"- coverage: {attached_count}/{sentence_count}\n\n"
            "다음 단계: OmniVoice 음성 생성.\n"
            "`진행`이라고 말하면 음성 생성만 실행하고 다시 멈출게."
        )

    if next_step == "flow_download":
        backend = _flow_backend()
        project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
        sentence_count, attached_count, missing = _project_sentence_asset_status(project)
        if backend in {"uivision", "assisted"}:
            try:
                attach_response = _json_request(
                    "POST",
                    f"/api/flow/assets/{pid}/attach-renamed",
                    payload={"search_dir": str(DEFAULT_DOWNLOADS_DIR), "since_minutes": 480},
                    timeout=60,
                )
            except NewautoError as exc:
                return (
                    "5단계 대기: 아직 `flow_sNNN_...` 형식의 다운로드 파일을 찾지 못했어.\n\n"
                    f"- project_id: {pid}\n"
                    f"- backend: {backend}\n"
                    f"- coverage: {attached_count}/{sentence_count}\n"
                    f"- missing: {missing}\n"
                    f"- reason: {exc}\n\n"
                    "Ui.Vision 매크로가 다운로드 직후 파일명을 `flow_s001_...`처럼 바꾸도록 실행해줘. "
                    "끝나면 `진행`이라고 말하면 같은 단계에서 다시 첨부할게."
            )
            attached = attach_response.get("attached")
            raw_refreshed = attach_response.get("project")
            refreshed_project = (
                raw_refreshed if isinstance(raw_refreshed, dict) else _json_request("GET", f"/api/projects/{pid}", timeout=30)
            )
            sentence_count, attached_count, missing = _project_sentence_asset_status(
                cast(dict[str, object], refreshed_project)
            )
            if missing:
                return (
                    "5단계 일부 완료: rename된 Flow 파일을 붙였지만 아직 빠진 문장이 있어.\n\n"
                    f"- project_id: {pid}\n"
                    f"- attached this run: {attached if isinstance(attached, list) else []}\n"
                    f"- coverage: {attached_count}/{sentence_count}\n"
                    f"- missing: {missing}\n\n"
                    "남은 문장도 Ui.Vision으로 생성/다운로드/rename한 뒤 `진행`이라고 말해줘."
                )
            _set_next_step(state, "tts")
            return (
                "5단계 완료: rename된 Flow 이미지/영상 다운로드와 문장별 연결이 끝났어.\n\n"
                f"- project_id: {pid}\n"
                f"- coverage: {attached_count}/{sentence_count}\n"
                f"- attached this run: {attached if isinstance(attached, list) else []}\n\n"
                "다음 단계: OmniVoice 음성 생성.\n"
                "`진행`이라고 말하면 음성 생성만 실행하고 다시 멈출게."
            )

        download_result = _run_flow_browser_script(["download", "--project-id", pid, "--limit", "0"], timeout_sec=180)
        try:
            paths = _latest_flow_asset_paths(DEFAULT_DOWNLOADS_DIR, limit=max(1, len(missing)), since_minutes=180)
        except NewautoError:
            paths = []
        if not paths:
            return (
                "5단계 중단: Flow 다운로드 파일을 아직 찾지 못했어.\n\n"
                f"- project_id: {pid}\n"
                f"- auto-download result: {download_result.get('message') or download_result}\n"
                f"- coverage: {attached_count}/{sentence_count}\n"
                f"- missing: {missing}\n\n"
                "Flow에서 다운로드 버튼만 직접 눌러줘. 다운로드가 끝나면 `진행`이라고 말해줘. 같은 단계에서 자동 첨부를 이어갈게."
            )
        attach_response = _json_request(
            "POST",
            f"/api/flow/assets/{pid}/attach-local",
            payload={"paths": paths, "start_sentence_number": 1},
            timeout=60,
        )
        attached = attach_response.get("attached")
        raw_refreshed = attach_response.get("project")
        refreshed_project = (
            raw_refreshed if isinstance(raw_refreshed, dict) else _json_request("GET", f"/api/projects/{pid}", timeout=30)
        )
        sentence_count, attached_count, missing = _project_sentence_asset_status(cast(dict[str, object], refreshed_project))
        if missing:
            return (
                "5단계 일부 완료: 다운로드 파일을 붙였지만 아직 빠진 문장이 있어.\n\n"
                f"- project_id: {pid}\n"
                f"- attached this run: {attached if isinstance(attached, list) else []}\n"
                f"- coverage: {attached_count}/{sentence_count}\n"
                f"- missing: {missing}\n\n"
                "남은 Flow 결과를 다운로드한 뒤 `진행`이라고 말해줘. 같은 단계에서 계속 첨부할게."
            )
        _set_next_step(state, "tts")
        return (
            "5단계 완료: Flow 이미지/영상 다운로드와 문장별 연결이 끝났어.\n\n"
            f"- project_id: {pid}\n"
            f"- coverage: {attached_count}/{sentence_count}\n"
            f"- attached this run: {attached if isinstance(attached, list) else []}\n\n"
            "다음 단계: OmniVoice 음성 생성.\n"
            "`진행`이라고 말하면 음성 생성만 실행하고 다시 멈출게."
        )

    if next_step == "tts":
        voice_preset = str(state.get("voice_preset") or "male-announcer-40s-50s")
        completed_project = _check_task_done(pid, "tts")
        if completed_project is not None:
            _set_next_step(state, "render")
            return (
                "6단계 완료: OmniVoice 음성 생성이 이미 끝나 있었어.\n\n"
                f"- project_id: {pid}\n"
                f"- voice_preset: {completed_project.get('voice_preset') or voice_preset}\n"
                f"- tts_state: {completed_project.get('tts_state')} {completed_project.get('tts_progress')}%\n\n"
                "다음 단계: 싱크/자막/렌더링.\n"
                "`진행`이라고 말하면 최종 렌더만 시작할게."
            )
        project = _enqueue_tts(pid, voice_preset)
        _set_stepwise_fields(
            state,
            {
                "next_step": "tts_wait",
                "tts_started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        )
        return (
            "6단계 시작: OmniVoice 음성 생성을 큐에 등록했어.\n\n"
            f"- project_id: {pid}\n"
            f"- voice_preset: {project.get('voice_preset') or voice_preset}\n"
            f"- tts_state: {project.get('tts_state')} {project.get('tts_progress')}%\n\n"
            "음성 생성은 백그라운드 worker가 진행해. 잠시 뒤 `진행`이라고 말하면 완료 여부만 확인할게."
        )

    if next_step == "tts_wait":
        try:
            tts_project = _check_task_done(pid, "tts")
        except NewautoError as exc:
            return (
                "6단계 실패: OmniVoice 음성 생성 worker가 오류를 반환했어.\n\n"
                f"- project_id: {pid}\n"
                f"- reason: {exc}\n\n"
                "원인을 확인한 뒤 `진행`이라고 말하면 같은 단계에서 다시 확인할게."
            )
        if tts_project is None:
            project_peek = _task_status(pid, "tts")
            return (
                "6단계 대기 중: OmniVoice 음성 생성이 아직 끝나지 않았어.\n\n"
                f"- project_id: {pid}\n"
                f"- tts_state: {project_peek.get('tts_state')}\n"
                f"- tts_progress: {project_peek.get('tts_progress')}%\n"
                f"- tts_error: {project_peek.get('tts_error') or 'none'}\n\n"
                "조금 뒤 `진행`이라고 말하면 같은 단계에서 다시 확인할게."
            )
        voice_preset = str(state.get("voice_preset") or "male-announcer-40s-50s")
        _set_next_step(state, "render")
        return (
            "6단계 완료: OmniVoice 음성 생성이 끝났어.\n\n"
            f"- project_id: {pid}\n"
            f"- voice_preset: {tts_project.get('voice_preset') or voice_preset}\n"
            f"- tts_state: {tts_project.get('tts_state')} {tts_project.get('tts_progress')}%\n\n"
            "다음 단계: 싱크/자막/렌더링.\n"
            "`진행`이라고 말하면 최종 렌더만 시작할게."
        )

    if next_step == "render":
        completed_project = _check_task_done(pid, "render")
        if completed_project is not None:
            _set_next_step(state, "done")
            return (
                "7단계 완료: 최종 렌더링이 이미 끝나 있었어.\n\n"
                f"- project_id: {pid}\n"
                f"- render_state: {completed_project.get('render_state')} {completed_project.get('render_progress')}%\n"
                f"- output: {BASE_URL}/api/projects/{pid}/output\n"
                f"- newauto: {_project_url(pid, step=4)}"
            )
        try:
            project = _enqueue_render(pid)
        except NewautoError as exc:
            return (
                "7단계 시작 실패: 렌더링 전 점검에서 막혔어.\n\n"
                f"- project_id: {pid}\n"
                f"- reason: {exc}\n"
                f"- newauto: {_project_url(pid, step=4)}"
            )
        _set_stepwise_fields(
            state,
            {
                "next_step": "render_wait",
                "render_started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        )
        return (
            "7단계 시작: 싱크/자막/최종 렌더링을 큐에 등록했어.\n\n"
            f"- project_id: {pid}\n"
            f"- render_state: {project.get('render_state')} {project.get('render_progress')}%\n"
            f"- render_phase: {project.get('render_phase') or 'queued'}\n\n"
            "렌더링은 백그라운드 worker가 진행해. 잠시 뒤 `진행`이라고 말하면 완료 여부만 확인할게."
        )

    if next_step == "render_wait":
        try:
            render_project = _check_task_done(pid, "render")
        except NewautoError as exc:
            return (
                "7단계 실패: 최종 렌더링 worker가 오류를 반환했어.\n\n"
                f"- project_id: {pid}\n"
                f"- reason: {exc}\n"
                f"- newauto: {_project_url(pid, step=4)}"
            )
        if render_project is None:
            project_peek = _task_status(pid, "render")
            return (
                "7단계 대기 중: 최종 렌더링이 아직 끝나지 않았어.\n\n"
                f"- project_id: {pid}\n"
                f"- render_state: {project_peek.get('render_state')}\n"
                f"- render_progress: {project_peek.get('render_progress')}%\n"
                f"- render_phase: {project_peek.get('render_phase') or 'n/a'}\n"
                f"- render_detail: {project_peek.get('render_progress_detail') or 'n/a'}\n"
                f"- render_error: {project_peek.get('render_error') or project_peek.get('render_last_log') or 'none'}\n\n"
                "조금 뒤 `진행`이라고 말하면 같은 단계에서 다시 확인할게."
            )
        _set_next_step(state, "done")
        return (
            "7단계 완료: 최종 렌더링이 끝났어.\n\n"
            f"- project_id: {pid}\n"
            f"- render_state: {render_project.get('render_state')} {render_project.get('render_progress')}%\n"
            f"- output: {BASE_URL}/api/projects/{pid}/output\n"
            f"- newauto: {_project_url(pid, step=4)}"
        )

    if next_step == "done":
        return (
            "이 워크플로우는 이미 완료됐어.\n\n"
            f"- project_id: {pid}\n"
            f"- output: {BASE_URL}/api/projects/{pid}/output\n"
            f"- newauto: {_project_url(pid, step=4)}"
        )

    raise NewautoError(f"Unknown stepwise next_step: {next_step}")


@mcp.tool()
def continue_stepwise_hpsl_video_workflow(project_id: str = "") -> str:
    """Run exactly one next step in the approval-gated HPSL Flow video workflow, then stop and ask for approval."""
    state: dict[str, object] = {}
    pid = project_id.strip()
    next_step_before = ""
    try:
        state = _load_stepwise_state(project_id)
        pid = str(state.get("project_id") or pid)
        next_step_before = str(state.get("next_step") or "")
    except Exception:
        next_step_before = ""
    message = _continue_stepwise_hpsl_video_workflow_impl(project_id)
    return _append_debug_footer(message, project_id=pid, next_step_before=next_step_before)


@mcp.tool()
def diagnose_newauto_runtime(project_id: str = "") -> str:
    """Return MCP runtime identity, API server owner, stepwise state, and asset coverage for LM Studio debugging."""
    _configure_stdout()
    pid = project_id.strip()
    snapshot = _runtime_snapshot(pid)
    return (
        "=== newauto MCP Runtime Diagnosis ===\n"
        f"mcp_script: {snapshot.get('mcp_script')}\n"
        f"mcp_file_hash: {snapshot.get('mcp_file_hash')}\n"
        f"git_commit: {snapshot.get('git_commit_short')}\n"
        f"mcp_pid: {snapshot.get('mcp_pid')}\n"
        f"python_executable: {snapshot.get('python_executable')}\n"
        f"cwd: {snapshot.get('cwd')}\n"
        f"BASE_URL: {snapshot.get('base_url')}\n"
        f"FLOW_AUTOMATION_BACKEND: {snapshot.get('flow_automation_backend')}\n"
        f"FLOW_MODE: {snapshot.get('flow_mode')}\n"
        f"api_server_ok: {snapshot.get('api_server_ok')}\n"
        f"api_server_pid_9001: {snapshot.get('api_server_pid_9001')}\n"
        f"api_server_command_9001: {snapshot.get('api_server_command_9001')}\n"
        f"resolved_omnivoice_python: {snapshot.get('resolved_omnivoice_python')}\n"
        f"mcp_processes: {snapshot.get('mcp_processes')}\n"
        f"flow_windows: {snapshot.get('flow_windows')}\n"
        f"stepwise_next_step: {snapshot.get('stepwise_next_step')}\n"
        f"asset_coverage: {snapshot.get('asset_coverage')}\n"
        f"diagnostic_json: {RUNTIME_DIAGNOSTICS_LATEST}"
    )


@mcp.tool()
def flow_asset_coverage(project_id: str) -> str:
    """Return sentence asset coverage for a project without advancing the workflow."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
    sentence_count, attached_count, missing = _project_sentence_asset_status(project)
    return _append_debug_footer(
        (
            "Flow asset coverage\n\n"
            f"- project_id: {pid}\n"
            f"- coverage: {attached_count}/{sentence_count}\n"
            f"- missing: {missing if missing else 'none'}"
        ),
        project_id=pid,
    )


@mcp.tool()
def flow_generate_one_sentence(project_id: str, sentence_number: int) -> str:
    """Diagnostic-only: click Generate for one Flow sentence prompt without waiting for download."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    target_sentence = max(1, int(sentence_number or 1))
    result = _run_flow_desktop_control(pid, target_sentence, mode="click-generate")
    return _append_debug_footer(
        (
            "Flow one-sentence Generate click completed.\n\n"
            f"- project_id: {pid}\n"
            f"- sentence: {target_sentence}\n"
            f"- window_title: {result.get('window_title')}\n"
            f"- screenshots: {result.get('screenshots')}\n\n"
            "Flow 결과 이미지가 보이면 `flow_download_one_sentence`로 다운로드/attach만 테스트해."
        ),
        project_id=pid,
    )


@mcp.tool()
def flow_download_one_sentence(project_id: str, sentence_number: int) -> str:
    """Diagnostic-only: download and attach one currently visible/generated Flow result for a sentence."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    target_sentence = max(1, int(sentence_number or 1))
    result = _run_flow_desktop_control(
        pid,
        target_sentence,
        mode="download-attach",
        downloads_before=[],
        download_timeout_seconds=45,
    )
    if result.get("ok") is not True:
        return _append_debug_footer(
            (
                "Flow one-sentence download/attach did not complete.\n\n"
                f"- project_id: {pid}\n"
                f"- sentence: {target_sentence}\n"
                f"- downloaded: {result.get('downloaded')}\n"
                f"- pending_attach: {result.get('pending_attach')}\n"
                f"- error: {result.get('error')}"
            ),
            project_id=pid,
        )
    return _append_debug_footer(
        (
            "Flow one-sentence download/attach completed.\n\n"
            f"- project_id: {pid}\n"
            f"- sentence: {target_sentence}\n"
            f"- downloaded: {result.get('downloaded')}\n"
            f"- attached: {result.get('attached')}\n"
            f"- screenshots: {result.get('screenshots')}"
        ),
        project_id=pid,
    )


@mcp.tool()
def make_hpsl_flow_short_video(
    keyword_or_url: str,
    title: str = "",
    target_minutes: int = 1,
    tone: str = "설명형",
) -> str:
    """Compatibility wrapper. Do not answer date objections yourself; start the stepwise workflow with the full request string."""
    return cast(
        str,
        start_stepwise_hpsl_video_workflow(
            keyword_or_url=keyword_or_url,
            title=title,
            target_minutes=target_minutes,
            tone=tone,
        ),
    )


@mcp.tool()
def automate_flow_generation(
    project_id: str,
    start_sentence_number: int = 1,
    limit: int = 0,
    click_generate: bool = True,
) -> str:
    """Use local Playwright to operate Google Flow after user authentication: fill sentence prompts and optionally click Generate."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    if not pid:
        return "project_id가 필요해."
    command = "generate" if click_generate else "fill"
    result = _run_flow_browser_script(
        [
            command,
            "--project-id",
            pid,
            "--start-sentence-number",
            str(max(1, int(start_sentence_number or 1))),
            "--limit",
            str(max(0, int(limit or 0))),
        ],
        timeout_sec=240,
    )
    if result.get("ok") is not True:
        webbrowser.open(FLOW_URL)
        return (
            "Flow 자동화가 사용자 확인 지점에서 멈췄어.\n\n"
            f"- project_id: {pid}\n"
            f"- reason: {result.get('message') or result}\n"
            f"- Flow: {FLOW_URL}\n\n"
            "열린 Flow 창에서 로그인/권한승인/팝업닫기를 해준 뒤, 다시 `automate_flow_generation`을 실행하면 이어서 시도할게."
        )
    processed = result.get("processed")
    downloads_seen = result.get("downloads_seen")
    return (
        "Flow 브라우저 자동화를 실행했어.\n\n"
        f"- project_id: {pid}\n"
        f"- prompts processed: {processed if processed is not None else result.get('count', 0)}\n"
        f"- downloads seen during run: {downloads_seen if isinstance(downloads_seen, list) else []}\n\n"
        "Flow 결과가 화면에 만들어지면 다운로드만 확인해줘. 다운로드가 끝나면 `Flow 다운로드 끝났어`라고 말하면 "
        "`attach_latest_flow_downloads`로 자동 첨부하고 렌더까지 이어갈게."
    )


@mcp.tool()
def download_flow_results_from_browser(project_id: str, expected_count: int = 0) -> str:
    """Try to click visible Download buttons in the Flow browser and save results to the Downloads folder."""
    _configure_stdout()
    pid = project_id.strip()
    if not pid:
        return "project_id가 필요해."
    project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
    sentence_count, attached_count, missing = _project_sentence_asset_status(project)
    needed = expected_count if expected_count > 0 else max(1, len(missing) or sentence_count - attached_count)
    result = _run_flow_browser_script(
        [
            "download",
            "--project-id",
            pid,
            "--limit",
            str(needed),
        ],
        timeout_sec=180,
    )
    if result.get("ok") is not True:
        return (
            "Flow 다운로드 자동 클릭을 완료하지 못했어.\n\n"
            f"- project_id: {pid}\n"
            f"- reason: {result.get('message') or result}\n\n"
            "Flow 화면에서 다운로드 버튼을 직접 눌러줘. 파일이 Downloads 폴더에 저장되면 "
            "`Flow 다운로드 끝났어`라고 말해줘. 그러면 내가 자동 첨부부터 이어갈게."
        )
    return (
        "Flow 다운로드 버튼 자동 클릭을 시도했어.\n\n"
        f"- project_id: {pid}\n"
        f"- clicked: {result.get('clicked')}\n"
        f"- downloads: {result.get('downloads')}\n\n"
        "이제 `attach_latest_flow_downloads`로 다운로드 파일을 문장 asset에 붙일 수 있어."
    )


@mcp.tool()
def open_flow_for_auth(project_id: str = "") -> str:
    """Open a persistent Playwright Flow browser profile for the user to authenticate once."""
    _configure_stdout()
    pid = project_id.strip() or "manual"
    if _flow_backend() == "uivision":
        webbrowser.open(FLOW_URL)
        return (
            "Flow 페이지를 열었어.\n"
            f"- project_id: {pid}\n"
            f"- Flow: {FLOW_URL}\n\n"
            "Ui.Vision/데스크톱 제어 모드에서는 CDP 연결을 기다리지 않아. "
            "로그인/권한승인이 끝났으면 LM Studio에 `진행`이라고 말해줘."
        )
    result = _run_flow_browser_script(["open", "--project-id", pid], timeout_sec=60)
    return (
        "Flow 인증용 브라우저를 열었어.\n"
        f"- result: {result.get('message') or result}\n"
        "로그인/권한승인을 끝낸 뒤 LM Studio 채팅에 `인증 끝났어`라고 말하면, "
        "`automate_flow_generation`으로 프롬프트 입력과 생성 클릭을 이어갈 수 있어."
    )


@mcp.tool()
def start_hpsl_flow_workflow(
    request: str,
    title: str = "",
    target_minutes: int = 1,
    tone: str = "설명형",
) -> str:
    """Compatibility wrapper for older LM Studio calls. Starts the approval-gated workflow only."""
    return cast(
        str,
        start_stepwise_hpsl_video_workflow(
            keyword_or_url=request,
            title=title,
            target_minutes=target_minutes,
            tone=tone,
        ),
    )


@mcp.tool()
def finish_hpsl_flow_workflow(project_id: str) -> str:
    """Compatibility wrapper for older LM Studio calls. Advances exactly one step and stops."""
    pid = project_id.strip()
    if not pid:
        return "project_id가 필요해."
    try:
        return cast(str, continue_stepwise_hpsl_video_workflow(pid))
    except NewautoError as exc:
        return (
            "구형 finish 도구가 호출됐지만 단계형 상태를 찾지 못했어.\n\n"
            f"- project_id: {pid}\n"
            f"- reason: {exc}\n\n"
            "새 작업은 `start_stepwise_hpsl_video_workflow`로 시작하고, 이후에는 `진행`이라고 말해서 "
            "`continue_stepwise_hpsl_video_workflow`를 한 단계씩 호출하는 방식으로 진행해야 해."
        )


@mcp.tool()
def get_flow_prompt_queue(project_id: str, limit: int = 8) -> str:
    """Show the current sentence-level Flow prompt queue for a newauto project."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    manifest = _json_request("GET", f"/api/flow/prompts/{pid}", timeout=30)
    return (
        f"newauto: {_project_url(pid, step=2)}\n"
        "Context-safe summary only. Use get_single_flow_prompt for one full prompt, or copy prompts from newauto UI.\n\n"
        f"{_brief_prompt_queue(manifest, limit=max(1, min(20, limit)), include_prompts=False)}"
    )


@mcp.tool()
def get_single_flow_prompt(project_id: str, sentence_number: int) -> str:
    """Return one full Flow prompt only. Use this instead of dumping the whole prompt queue into chat."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    manifest = _json_request("GET", f"/api/flow/prompts/{pid}", timeout=30)
    entries_obj = manifest.get("entries")
    if not isinstance(entries_obj, list):
        return "No Flow prompt entries are available."
    target_idx = max(0, int(sentence_number) - 1)
    for raw_entry in entries_obj:
        if not isinstance(raw_entry, dict):
            continue
        if raw_entry.get("sentence_idx") != target_idx:
            continue
        narration = str(raw_entry.get("narration") or "")
        prompt = str(raw_entry.get("prompt") or "")
        return (
            f"sentence {sentence_number}\n"
            f"narration: {narration[:300]}\n\n"
            f"Flow prompt:\n{prompt[:1800]}"
        )
    return f"Sentence {sentence_number} was not found in the Flow prompt manifest."


@mcp.tool()
def prepare_uivision_flow_batch(project_id: str) -> str:
    """Prepare CSV/TXT files for Ui.Vision to generate Google Flow assets without dumping all prompts into chat."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    if not pid:
        return "project_id가 필요해."
    payload = _prepare_uivision_payload(pid)
    prompt_paths = payload.get("prompt_paths")
    prompt_count = len(prompt_paths) if isinstance(prompt_paths, list) else 0
    webbrowser.open(FLOW_URL)
    return (
        "Ui.Vision용 Flow 프롬프트 파일을 준비했어.\n\n"
        f"- project_id: {pid}\n"
        f"- prompts: {prompt_count}\n"
        f"- csv_path: {payload.get('csv_path')}\n"
        f"- folder: {payload.get('directory')}\n\n"
        "다음 행동:\n"
        "1. Flow 로그인/권한승인이 필요하면 사용자님이 승인\n"
        "2. Ui.Vision에서 Flow_Generate_One 매크로로 1번 문장부터 테스트\n"
        "3. 다운로드 파일명이 `flow_s001_...` 형식인지 확인\n"
        "4. 끝나면 `진행` 또는 `Flow 다운로드 끝났어`라고 말해줘\n\n"
        "매크로 실행 중에는 Flow 브라우저를 건드리지 말고, 결제/4K 업그레이드/유료 크레딧 버튼은 누르지 마."
    )


@mcp.tool()
def open_newauto_project(project_id: str, step: int = 2) -> str:
    """Open a newauto project in the browser so the user can click only the required UI actions."""
    _ensure_server()
    url = _project_url(project_id.strip(), step=max(1, min(5, int(step or 2))))
    webbrowser.open(url)
    return f"Opened newauto project: {url}"


@mcp.tool()
def open_flow() -> str:
    """Open Google Flow for the user. Use this when the next step is user authentication or clicking Generate in Flow."""
    if _flow_backend() == "uivision":
        try:
            state = _load_stepwise_state("")
            pid = str(state.get("project_id") or "manual")
            if str(state.get("next_step") or "") == "flow_auth":
                _set_next_step(state, "flow_generate")
        except Exception:
            pid = "manual"
        webbrowser.open(FLOW_URL)
        return (
            "Flow 페이지를 열었어.\n\n"
            f"- project_id: {pid}\n"
            f"- Flow: {FLOW_URL}\n"
            f"- backend: {_flow_backend()}\n\n"
            "이 모드에서는 CDP/Playwright 연결을 기다리지 않아서 timeout이 나지 않아. "
            "로그인/권한승인이 끝났거나 이미 로그인되어 있으면 `진행`이라고 말해줘. "
            "다음 단계에서는 Generate 클릭만 빠르게 실행할게."
        )
    try:
        state = _load_stepwise_state("")
        pid = str(state.get("project_id") or "manual")
        result = _run_flow_browser_script(["open", "--project-id", pid], timeout_sec=60)
        if str(state.get("next_step") or "") == "flow_auth":
            _set_next_step(state, "flow_generate")
        return (
            "Flow CDP 전용 브라우저를 열었어.\n\n"
            f"- project_id: {pid}\n"
            f"- clicked_new_project: {result.get('clicked_new_project')}\n"
            f"- result: {result.get('message') or result}\n\n"
            "로그인/권한승인이 끝났으면 `진행`이라고 말해줘. 다음에는 프롬프트 입력과 생성 버튼 클릭을 자동 시도할게."
        )
    except Exception as exc:
        webbrowser.open(FLOW_URL)
        return (
            f"Opened Flow fallback: {FLOW_URL}\n"
            f"CDP 자동화 브라우저를 열지 못했어: {exc}\n"
            "이 경우 Flow 창에서 로그인/권한승인만 완료한 뒤 다시 `진행`이라고 말해줘."
        )


@mcp.tool()
def get_newauto_status(project_id: str) -> str:
    """Check newauto project state, missing Flow assets, TTS state, render state, and next action."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
    manifest = _json_request("GET", f"/api/flow/manifest/{pid}", timeout=30)
    sentences = project.get("sentences")
    mappings = project.get("body_image_mappings")
    entries = manifest.get("entries")
    sentence_count = len(sentences) if isinstance(sentences, list) else 0
    mapped_indexes = _mapped_sentence_indexes(mappings)
    missing = [index + 1 for index in range(sentence_count) if index not in mapped_indexes]
    attached = len(mapped_indexes)
    flow_ready = len(entries) if isinstance(entries, list) else 0
    next_action = (
        "Flow 결과 파일을 문장별로 첨부해줘."
        if missing
        else "모든 문장 asset이 연결된 것으로 보여. continue_after_flow_assets를 호출하면 TTS/렌더를 진행할 수 있어."
    )
    return (
        f"project_id: {pid}\n"
        f"newauto: {_project_url(pid, step=2)}\n"
        f"source_draft: {project.get('source_draft_state')} {project.get('source_draft_progress')}%\n"
        f"sentences: {sentence_count}\n"
        f"flow prompts: {flow_ready}\n"
        f"attached assets: {attached}/{sentence_count}\n"
        f"missing sentence assets: {missing if missing else 'none'}\n"
        f"tts: {project.get('tts_state')} {project.get('tts_progress')}%\n"
        f"render: {project.get('render_state')} {project.get('render_progress')}%\n"
        f"next: {next_action}"
    )


@mcp.tool()
def attach_latest_flow_downloads(
    project_id: str,
    downloads_dir: str = "",
    count: int = 0,
    start_sentence_number: int = 1,
    since_minutes: int = 180,
) -> str:
    """Attach the latest Flow image/video downloads to the project in sentence order, so the user does not need to upload them one by one."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
    sentence_count, attached_count, missing = _project_sentence_asset_status(project)
    if sentence_count == 0:
        return "아직 적용된 대본 문장이 없어. 먼저 HPSL 대본을 적용해야 해."
    needed = len(missing) if count <= 0 else count
    if needed <= 0:
        return "이미 모든 문장에 Flow asset이 붙어 있어. 이제 continue_after_flow_assets를 실행하면 돼."
    source_dir = Path(downloads_dir).expanduser() if downloads_dir.strip() else DEFAULT_DOWNLOADS_DIR
    paths = _latest_flow_asset_paths(source_dir, limit=needed, since_minutes=since_minutes)
    if len(paths) < needed:
        webbrowser.open(FLOW_URL)
        return (
            "다운로드 폴더에서 붙일 Flow 파일을 충분히 찾지 못했어.\n"
            f"- folder: {source_dir}\n"
            f"- needed: {needed}\n"
            f"- found: {len(paths)}\n"
            f"- current attached: {attached_count}/{sentence_count}\n"
            f"- missing sentence assets: {missing}\n\n"
            "Flow에서 결과 이미지를 다운로드한 뒤 다시 `Flow 다운로드 끝났어`라고 말해줘."
        )
    response = _json_request(
        "POST",
        f"/api/flow/assets/{pid}/attach-local",
        payload={
            "paths": paths,
            "start_sentence_number": max(1, int(start_sentence_number or 1)),
        },
        timeout=60,
    )
    refreshed = response.get("project")
    refreshed_project = refreshed if isinstance(refreshed, dict) else _json_request("GET", f"/api/projects/{pid}", timeout=30)
    sentence_count, attached_count, missing = _project_sentence_asset_status(cast(dict[str, object], refreshed_project))
    attached = response.get("attached")
    skipped = response.get("skipped")
    webbrowser.open(_project_url(pid, step=2))
    return (
        "다운로드된 Flow 파일을 문장 asset으로 연결했어.\n\n"
        f"- project_id: {pid}\n"
        f"- attached files: {attached if isinstance(attached, list) else []}\n"
        f"- skipped: {skipped if isinstance(skipped, list) else []}\n"
        f"- asset coverage: {attached_count}/{sentence_count}\n"
        f"- missing sentence assets: {missing if missing else 'none'}\n"
        f"- newauto: {_project_url(pid, step=2)}\n\n"
        + (
            "이제 `continue_after_flow_assets`를 실행하면 OmniVoice 음성, 싱크, 자막, 렌더링까지 진행할 수 있어."
            if not missing
            else "아직 빠진 문장이 있어. 남은 Flow 결과를 더 다운로드한 뒤 다시 알려줘."
        )
    )


@mcp.tool()
def attach_renamed_flow_downloads(
    project_id: str,
    downloads_dir: str = "",
    since_minutes: int = 480,
) -> str:
    """Attach Ui.Vision-renamed Flow downloads like flow_s001_*.png by parsing the sentence number from filenames."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    if not pid:
        return "project_id가 필요해."
    source_dir = Path(downloads_dir).expanduser() if downloads_dir.strip() else DEFAULT_DOWNLOADS_DIR
    response = _json_request(
        "POST",
        f"/api/flow/assets/{pid}/attach-renamed",
        payload={"search_dir": str(source_dir), "since_minutes": max(1, int(since_minutes or 480))},
        timeout=60,
    )
    refreshed = response.get("project")
    refreshed_project = refreshed if isinstance(refreshed, dict) else _json_request("GET", f"/api/projects/{pid}", timeout=30)
    sentence_count, attached_count, missing = _project_sentence_asset_status(cast(dict[str, object], refreshed_project))
    attached = response.get("attached")
    skipped = response.get("skipped")
    webbrowser.open(_project_url(pid, step=2))
    return (
        "파일명 기반으로 Flow 다운로드를 문장 asset에 연결했어.\n\n"
        f"- project_id: {pid}\n"
        f"- folder: {source_dir}\n"
        f"- attached files: {attached if isinstance(attached, list) else []}\n"
        f"- skipped: {skipped if isinstance(skipped, list) else []}\n"
        f"- asset coverage: {attached_count}/{sentence_count}\n"
        f"- missing sentence assets: {missing if missing else 'none'}\n"
        f"- newauto: {_project_url(pid, step=2)}\n\n"
        + (
            "이제 `continue_after_flow_assets` 또는 단계형 `진행`으로 OmniVoice/TTS 단계로 넘어갈 수 있어."
            if not missing
            else "아직 빠진 문장이 있어. 남은 문장을 Ui.Vision으로 생성/다운로드/rename한 뒤 다시 알려줘."
        )
    )


@mcp.tool()
def continue_after_flow_assets(project_id: str, voice_preset: str = "male-announcer-40s-50s") -> str:
    """After Flow assets are attached, resume the approval-gated TTS/render workflow without long polling."""
    _configure_stdout()
    _ensure_server()
    pid = project_id.strip()
    project = _json_request("GET", f"/api/projects/{pid}", timeout=30)
    sentences = project.get("sentences")
    mappings = project.get("body_image_mappings")
    sentence_count = len(sentences) if isinstance(sentences, list) else 0
    mapped_indexes = _mapped_sentence_indexes(mappings)
    missing = [index + 1 for index in range(sentence_count) if index not in mapped_indexes]
    if missing:
        webbrowser.open(_project_url(pid, step=2))
        return (
            "아직 Flow 결과 파일이 빠진 문장이 있어. 렌더를 시작하지 않았어.\n"
            f"- missing sentence assets: {missing}\n"
            f"- newauto: {_project_url(pid, step=2)}\n"
            "빠진 문장 행에서 `Flow 결과 파일 첨부`를 눌러 파일을 붙인 뒤 다시 말해줘."
        )

    next_step = "render" if str(project.get("tts_state") or "") == "done" else "tts"
    state = {
        "project_id": pid,
        "request": str(project.get("title") or ""),
        "target_minutes": 1,
        "voice_preset": voice_preset,
        "next_step": next_step,
        "source_mode": "existing project",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _save_stepwise_state(state)
    return _continue_stepwise_hpsl_video_workflow_impl(pid)


def main() -> None:
    _configure_stdout()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

