import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE_DIR = ROOT / "storage" / "browser_smoke"
SERVER_START_TIMEOUT_SEC = 30.0


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _chrome_candidates() -> list[Path]:
    return [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]


def _chrome_path() -> Path:
    for candidate in _chrome_candidates():
        if candidate.exists():
            return candidate
    raise RuntimeError("Chrome executable not found")


def _wait_for_health(base_url: str) -> None:
    deadline = time.monotonic() + SERVER_START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("ok") is True:
                return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Server health check did not become ready in time")


def _request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> object:
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=15.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _create_project(base_url: str) -> str:
    body = urllib.parse.urlencode({"title": "browser-smoke"}).encode("utf-8")
    payload = _request_json(
        f"{base_url}/api/projects",
        method="POST",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if not isinstance(payload, dict) or "id" not in payload:
        raise RuntimeError("Project creation returned an unexpected payload")
    return str(payload["id"])


def _delete_project(base_url: str, project_id: str) -> None:
    try:
        _request_json(f"{base_url}/api/projects/{project_id}", method="DELETE")
    except Exception:
        pass


def _chrome_dom(url: str, output_html: Path, screenshot_path: Path) -> str:
    chrome = _chrome_path()
    dump = subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--virtual-time-budget=5000",
            "--window-size=1440,1600",
            f"--screenshot={screenshot_path}",
            "--dump-dom",
            url,
        ],
        capture_output=True,
        text=False,
        check=False,
    )
    stdout_text = (dump.stdout or b"").decode("utf-8", errors="replace")
    stderr_text = (dump.stderr or b"").decode("utf-8", errors="replace")
    if dump.returncode != 0:
        detail = (stderr_text or stdout_text).strip()
        raise RuntimeError(f"Chrome headless smoke failed: {detail}")
    output_html.write_text(stdout_text, encoding="utf-8")
    return stdout_text


def _assert_contains(dom: str, expected: list[str], label: str) -> None:
    missing = [item for item in expected if item not in dom]
    if missing:
        raise RuntimeError(f"{label} DOM missing expected text: {', '.join(missing)}")


def main() -> int:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["NEWAUTO_DISABLE_BACKGROUND_WORKERS"] = "1"
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    project_id = ""
    try:
        _wait_for_health(base_url)
        project_id = _create_project(base_url)

        step2_url = f"{base_url}/?project={project_id}&step=2"
        step4_url = f"{base_url}/?project={project_id}&step=4"

        step2_dom = _chrome_dom(step2_url, SMOKE_DIR / "step2.html", SMOKE_DIR / "step2.png")
        _assert_contains(
            step2_dom,
            ["AI Image Gen", "Scene Plan 생성", "Render Plan 생성"],
            "step2",
        )

        step4_dom = _chrome_dom(step4_url, SMOKE_DIR / "step4.html", SMOKE_DIR / "step4.png")
        _assert_contains(
            step4_dom,
            ["Run Pre-flight", "System Health", "Render Report", "Operator", "렌더 시작"],
            "step4",
        )
        print(f"Browser smoke passed. Artifacts saved in {SMOKE_DIR}")
        return 0
    finally:
        if project_id:
            _delete_project(base_url, project_id)
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
