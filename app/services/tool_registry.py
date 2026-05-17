import importlib.util
import shutil
import subprocess
from pathlib import Path

from ..config import (
    COMFYUI_BASE_URL,
    COMFYUI_ENABLED,
    COMFYUI_INSTALL_DIR,
    LLM_PROVIDER,
    LMSTUDIO_BASE_URL,
    OLLAMA_BASE_URL,
)
from ..types import ToolStatus


def _command_version(command: str, *args: str) -> str:
    binary = shutil.which(command)
    if binary is None:
        return ""
    try:
        completed = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError:
        return ""
    output = (completed.stdout or completed.stderr or "").strip().splitlines()
    return output[0].strip()[:160] if output else ""


def _tool(
    *,
    key: str,
    label: str,
    available: bool,
    configured: bool,
    version: str,
    detail: str,
    install_path: str,
) -> ToolStatus:
    return {
        "key": key,
        "label": label,
        "availability": "available" if available else "unavailable",
        "configured": configured,
        "version": version,
        "detail": detail,
        "install_path": install_path,
    }


def list_tool_status() -> list[ToolStatus]:
    ffmpeg_bin = shutil.which("ffmpeg") or ""
    ollama_bin = shutil.which("ollama") or ""
    ytdlp_bin = shutil.which("yt-dlp") or ""
    npx_bin = shutil.which("npx") or ""
    faster_whisper_installed = importlib.util.find_spec("faster_whisper") is not None
    comfy_install_exists = COMFYUI_INSTALL_DIR.exists()
    llm_base_url = OLLAMA_BASE_URL if LLM_PROVIDER == "ollama" else LMSTUDIO_BASE_URL
    llm_is_configured = bool(llm_base_url)
    llm_detail = (
        f"Ollama endpoint: {OLLAMA_BASE_URL}"
        if LLM_PROVIDER == "ollama"
        else f"LM Studio endpoint: {LMSTUDIO_BASE_URL}"
    )
    llm_available = bool(ollama_bin) if LLM_PROVIDER == "ollama" else llm_is_configured

    return [
        _tool(
            key="ffmpeg",
            label="FFmpeg",
            available=bool(ffmpeg_bin),
            configured=bool(ffmpeg_bin),
            version=_command_version("ffmpeg", "-version"),
            detail="비디오 렌더와 오디오 처리",
            install_path=ffmpeg_bin,
        ),
        _tool(
            key="ollama",
            label="LLM Server",
            available=llm_available,
            configured=llm_is_configured,
            version="" if LLM_PROVIDER == "lmstudio" else _command_version("ollama", "--version"),
            detail=llm_detail,
            install_path=ollama_bin,
        ),
        _tool(
            key="comfyui",
            label="ComfyUI",
            available=comfy_install_exists,
            configured=COMFYUI_ENABLED or comfy_install_exists,
            version="",
            detail=f"이미지 생성 서버: {COMFYUI_BASE_URL}",
            install_path=str(COMFYUI_INSTALL_DIR) if comfy_install_exists else "",
        ),
        _tool(
            key="faster_whisper",
            label="faster-whisper",
            available=faster_whisper_installed,
            configured=faster_whisper_installed,
            version="python-package" if faster_whisper_installed else "",
            detail="전사/타임라인 보조 패키지",
            install_path="python-site-packages" if faster_whisper_installed else "",
        ),
        _tool(
            key="yt_dlp",
            label="yt-dlp",
            available=bool(ytdlp_bin),
            configured=bool(ytdlp_bin),
            version=_command_version("yt-dlp", "--version"),
            detail="외부 미디어 다운로드 도구",
            install_path=ytdlp_bin,
        ),
        _tool(
            key="playwright_mcp",
            label="Playwright MCP",
            available=bool(npx_bin),
            configured=bool(npx_bin),
            version=_command_version("npx", "--version"),
            detail="브라우저 검수 자동화용 런처 필요",
            install_path=npx_bin,
        ),
    ]
