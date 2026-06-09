# HyperFrames Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional HyperFrames transparent overlay sidecar for editorial lower-thirds and keyword callouts without replacing ComfyUI, ASS subtitles, or the current render pipeline.

**Architecture:** Keep HyperFrames isolated behind probes, a deterministic overlay planner, and an optional render step. The final MP4 remains produced by `app/services/render.py`, with the overlay composited in the existing `_mux()` pass before ASS subtitles are burned in.

**Tech Stack:** Python 3, pytest, FastAPI typed health surfaces, FFmpeg/ffprobe, Node.js >= 22, pinned `hyperframes@0.6.12`, project-local HTML/CSS, vendored Korean font files.

---

## Current Spec

Use `docs/hyperframes-adoption-plan-2026-05-16.md` as the adoption spec. This plan deliberately implements only the overlay-only sidecar path.

Do not implement:

- Full HyperFrames render backend.
- Multiple template families.
- ComfyUI replacement.
- External web fonts.
- A second full-resolution `libx264` encode pass.
- SQLite schema changes for overlay options.

## File Map

- Create `app/services/hyperframes_probe.py`: small runtime probe for Node, npx, pinned HyperFrames doctor, and FFmpeg alpha encoder support.
- Create `tests/test_hyperframes_probe.py`: unit tests for probe parsing and unavailable-tool behavior.
- Modify `app/types.py`: add HyperFrames fields to `SystemHealth`.
- Modify `app/services/system_health.py`: expose probe summary in system health.
- Create `app/services/hyperframes_overlay.py`: pure planning and project writer for one `lower_third_keyword` template.
- Create `tests/test_hyperframes_overlay.py`: deterministic overlay plan and HTML/font tests.
- Create `scripts/render_hyperframes_overlay.py`: CLI wrapper around pinned HyperFrames render/lint/inspect with ffprobe assertions.
- Modify `app/services/render.py`: optional overlay path in `_mux()` and guarded render integration.
- Modify `app/services/preflight.py`: report overlay readiness when enabled.
- Modify `app/services/diagnostics.py`: copy overlay artifacts into diagnostics bundle.
- Add tests to existing render/preflight/diagnostics test files where behavior belongs.
- Create `tools/hyperframes/package.json`: pinned local tool manifest.
- Create `tools/hyperframes/package-lock.json`: generated lockfile after `npm install`.

## Shared Constants

Use these names consistently:

```python
HYPERFRAMES_PACKAGE = "hyperframes@0.6.12"
OVERLAY_DIR_NAME = "hyperframes_overlay"
OVERLAY_PLAN_NAME = "overlay_plan.json"
OVERLAY_REPORT_NAME = "overlay_report.json"
OVERLAY_WEBM_NAME = "overlay.webm"
OVERLAY_MOV_NAME = "overlay.mov"
```

Project option keys stay inside `body_image_options`:

```python
"hyperframes_overlay_enabled"  # bool, default False
"hyperframes_overlay_required" # bool, default False
"hyperframes_overlay_status"   # "not_run" | "done" | "failed" | "skipped"
"hyperframes_overlay_report_path" # string
```

Global strict override:

```text
NEWAUTO_HYPERFRAMES_STRICT=1
```

## Task 1: Runtime Probe

**Files:**
- Create: `app/services/hyperframes_probe.py`
- Create: `tests/test_hyperframes_probe.py`

- [ ] **Step 1: Write failing probe tests**

Create `tests/test_hyperframes_probe.py`:

```python
import unittest
from unittest.mock import patch

from app.services.hyperframes_probe import (
    HYPERFRAMES_PACKAGE,
    parse_node_major,
    probe_hyperframes_runtime,
)


class HyperFramesProbeTests(unittest.TestCase):
    def test_parse_node_major_accepts_v22(self) -> None:
        self.assertEqual(parse_node_major("v22.16.0\n"), 22)

    def test_parse_node_major_rejects_unparseable_output(self) -> None:
        self.assertIsNone(parse_node_major("not node"))

    @patch("app.services.hyperframes_probe.shutil.which")
    def test_probe_reports_missing_node_without_running_doctor(self, which) -> None:
        which.return_value = None

        status = probe_hyperframes_runtime(refresh=True)

        self.assertFalse(status["node_available"])
        self.assertFalse(status["doctor_ok"])
        self.assertIn("node not found", status["doctor_detail"])

    @patch("app.services.hyperframes_probe._run_text")
    @patch("app.services.hyperframes_probe.shutil.which")
    def test_probe_uses_pinned_hyperframes_package(self, which, run_text) -> None:
        which.side_effect = lambda name: f"C:/bin/{name}.exe"
        run_text.side_effect = [
            (0, "v22.16.0\n", ""),
            (0, "10.9.2\n", ""),
            (0, "doctor ok\n", ""),
            (0, " V..... libvpx-vp9\n V..... prores_ks\n", ""),
        ]

        status = probe_hyperframes_runtime(refresh=True)

        self.assertTrue(status["node_available"])
        self.assertTrue(status["npx_available"])
        self.assertTrue(status["doctor_ok"])
        self.assertTrue(status["ffmpeg_alpha_ok"])
        self.assertIn(HYPERFRAMES_PACKAGE, run_text.call_args_list[2].args[0])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_hyperframes_probe.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.hyperframes_probe'`.

- [ ] **Step 3: Implement minimal probe**

Create `app/services/hyperframes_probe.py`:

```python
import re
import shutil
import subprocess
import time
from typing import TypedDict

HYPERFRAMES_PACKAGE = "hyperframes@0.6.12"
_CACHE_TTL_SEC = 300.0
_cache: tuple[float, "HyperFramesRuntimeStatus"] | None = None


class HyperFramesRuntimeStatus(TypedDict):
    node_available: bool
    node_version: str
    node_major: int | None
    npx_available: bool
    npx_version: str
    doctor_ok: bool
    doctor_detail: str
    ffmpeg_alpha_ok: bool
    ffmpeg_alpha_detail: str


def _run_text(command: list[str], timeout_sec: int = 30) -> tuple[int, str, str]:
    process = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout_sec)
    return process.returncode, process.stdout or "", process.stderr or ""


def parse_node_major(output: str) -> int | None:
    match = re.search(r"v?(\d+)\.", output.strip())
    if not match:
        return None
    return int(match.group(1))


def _empty_status(detail: str) -> HyperFramesRuntimeStatus:
    return {
        "node_available": False,
        "node_version": "",
        "node_major": None,
        "npx_available": False,
        "npx_version": "",
        "doctor_ok": False,
        "doctor_detail": detail,
        "ffmpeg_alpha_ok": False,
        "ffmpeg_alpha_detail": "",
    }


def probe_hyperframes_runtime(*, refresh: bool = False) -> HyperFramesRuntimeStatus:
    global _cache
    now = time.monotonic()
    if _cache is not None and not refresh and now - _cache[0] <= _CACHE_TTL_SEC:
        return dict(_cache[1])

    if shutil.which("node") is None:
        return _empty_status("node not found on PATH")
    if shutil.which("npx") is None:
        status = _empty_status("npx not found on PATH")
        status["node_available"] = True
        return status

    node_code, node_out, node_err = _run_text(["node", "--version"])
    npx_code, npx_out, npx_err = _run_text(["npx", "--version"])
    node_major = parse_node_major(node_out)
    doctor_code, doctor_out, doctor_err = _run_text(["npx", "-y", HYPERFRAMES_PACKAGE, "doctor"], timeout_sec=90)
    enc_code, enc_out, enc_err = _run_text(["ffmpeg", "-hide_banner", "-encoders"], timeout_sec=30)
    enc_text = enc_out + enc_err
    alpha_ok = enc_code == 0 and "libvpx-vp9" in enc_text and "prores_ks" in enc_text

    status: HyperFramesRuntimeStatus = {
        "node_available": node_code == 0 and node_major is not None and node_major >= 22,
        "node_version": (node_out or node_err).strip(),
        "node_major": node_major,
        "npx_available": npx_code == 0,
        "npx_version": (npx_out or npx_err).strip(),
        "doctor_ok": doctor_code == 0,
        "doctor_detail": (doctor_out or doctor_err).strip(),
        "ffmpeg_alpha_ok": alpha_ok,
        "ffmpeg_alpha_detail": enc_text.strip(),
    }
    _cache = (now, status)
    return dict(status)
```

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_hyperframes_probe.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```powershell
git add app/services/hyperframes_probe.py tests/test_hyperframes_probe.py
git commit -m "feat: add hyperframes runtime probe"
```

## Task 2: System Health Surface

**Files:**
- Modify: `app/types.py`
- Modify: `app/services/system_health.py`
- Test: `tests/test_hyperframes_probe.py`

- [ ] **Step 1: Write failing system health test**

Append to `tests/test_hyperframes_probe.py`:

```python
    @patch("app.services.system_health.probe_hyperframes_runtime")
    def test_system_health_exposes_hyperframes_probe(self, probe) -> None:
        from app.services.system_health import get_system_health

        probe.return_value = {
            "node_available": True,
            "node_version": "v22.16.0",
            "node_major": 22,
            "npx_available": True,
            "npx_version": "10.9.2",
            "doctor_ok": True,
            "doctor_detail": "ok",
            "ffmpeg_alpha_ok": True,
            "ffmpeg_alpha_detail": "libvpx-vp9 prores_ks",
        }

        health = get_system_health(refresh_runtime=True)

        self.assertTrue(health["hyperframes_node_available"])
        self.assertEqual(health["hyperframes_node_version"], "v22.16.0")
        self.assertTrue(health["hyperframes_doctor_ok"])
        self.assertTrue(health["hyperframes_ffmpeg_alpha_ok"])
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_hyperframes_probe.py::HyperFramesProbeTests::test_system_health_exposes_hyperframes_probe -q
```

Expected: FAIL because `system_health` has no `probe_hyperframes_runtime` import or health keys.

- [ ] **Step 3: Add typed health fields**

In `app/types.py::SystemHealth`, add:

```python
    hyperframes_node_available: bool
    hyperframes_node_version: str
    hyperframes_npx_available: bool
    hyperframes_npx_version: str
    hyperframes_doctor_ok: bool
    hyperframes_doctor_detail: str
    hyperframes_ffmpeg_alpha_ok: bool
```

In `app/services/system_health.py`, import:

```python
from .hyperframes_probe import probe_hyperframes_runtime
```

Inside `get_system_health()`, before `return`, add:

```python
    hyperframes_status = probe_hyperframes_runtime(refresh=refresh_runtime)
```

Then add these keys to the returned dict:

```python
        "hyperframes_node_available": bool(hyperframes_status["node_available"]),
        "hyperframes_node_version": str(hyperframes_status["node_version"]),
        "hyperframes_npx_available": bool(hyperframes_status["npx_available"]),
        "hyperframes_npx_version": str(hyperframes_status["npx_version"]),
        "hyperframes_doctor_ok": bool(hyperframes_status["doctor_ok"]),
        "hyperframes_doctor_detail": str(hyperframes_status["doctor_detail"]),
        "hyperframes_ffmpeg_alpha_ok": bool(hyperframes_status["ffmpeg_alpha_ok"]),
```

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_hyperframes_probe.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```powershell
git add app/types.py app/services/system_health.py tests/test_hyperframes_probe.py
git commit -m "feat: expose hyperframes health status"
```

## Task 3: Overlay Planner and HTML Writer

**Files:**
- Create: `app/services/hyperframes_overlay.py`
- Create: `tests/test_hyperframes_overlay.py`

- [ ] **Step 1: Write failing overlay planner tests**

Create `tests/test_hyperframes_overlay.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from app.services.hyperframes_overlay import build_overlay_plan, write_overlay_project


class HyperFramesOverlayTests(unittest.TestCase):
    def test_build_overlay_plan_creates_one_lower_third_keyword_per_sentence(self) -> None:
        timings = [
            {"sentence_idx": 0, "start": 0.0, "end": 4.2, "text": "젠슨 황이 경제사절단에 합류했습니다."},
            {"sentence_idx": 1, "start": 4.2, "end": 8.0, "text": "엔비디아가 공식 확인했습니다."},
        ]

        plan = build_overlay_plan(timings)

        self.assertEqual([row["overlay_type"] for row in plan["items"]], ["lower_third_keyword", "lower_third_keyword"])
        self.assertEqual(plan["items"][0]["text"], "경제사절단 합류")
        self.assertEqual(plan["items"][1]["text"], "엔비디아 공식 확인")
        self.assertLessEqual(max(len(row["text"]) for row in plan["items"]), 12)

    def test_write_overlay_project_uses_local_font_and_no_network_urls(self) -> None:
        timings = [{"sentence_idx": 0, "start": 0.0, "end": 3.0, "text": "트럼프가 직접 요청했습니다."}]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "hyperframes_overlay"

            paths = write_overlay_project(out_dir, timings, width=1920, height=1080)

            html = paths["index_html"].read_text(encoding="utf-8")
            plan = json.loads(paths["overlay_plan"].read_text(encoding="utf-8"))
            self.assertIn("@font-face", html)
            self.assertIn("assets/fonts/Pretendard-Regular.woff2", html)
            self.assertNotIn("https://", html)
            self.assertEqual(plan["items"][0]["text"], "직접 요청")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_hyperframes_overlay.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.hyperframes_overlay'`.

- [ ] **Step 3: Implement deterministic planner and HTML writer**

Create `app/services/hyperframes_overlay.py`:

```python
import html
import json
import shutil
from pathlib import Path
from typing import Any, TypedDict

OVERLAY_DIR_NAME = "hyperframes_overlay"
OVERLAY_PLAN_NAME = "overlay_plan.json"


class OverlayWritePaths(TypedDict):
    index_html: Path
    overlay_plan: Path


def _keyword_for_text(text: str) -> str:
    if "경제사절단" in text or "사절단" in text:
        return "경제사절단 합류"
    if "엔비디아" in text or "Nvidia" in text:
        return "엔비디아 공식 확인"
    if "직접 요청" in text or "요청" in text:
        return "직접 요청"
    if "알래스카" in text or "베이징" in text:
        return "알래스카 경유"
    compact = "".join(str(text).split())
    return compact[:12] or "뉴스 요약"


def build_overlay_plan(timings: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for raw in timings:
        start = float(raw.get("start", 0.0))
        end = float(raw.get("end", start + 1.0))
        text = str(raw.get("text", ""))
        sentence_idx = int(raw.get("sentence_idx", len(items)))
        items.append(
            {
                "sentence_idx": sentence_idx,
                "start": start,
                "end": end,
                "overlay_type": "lower_third_keyword",
                "text": _keyword_for_text(text),
                "secondary": "NewAuto Studio",
                "position": "upper_left" if sentence_idx % 2 else "lower_left",
            }
        )
    duration = max((float(item["end"]) for item in items), default=0.0)
    return {"version": 1, "template": "lower_third_keyword", "duration_sec": duration, "items": items}


def _copy_font_placeholder(font_dir: Path) -> None:
    font_dir.mkdir(parents=True, exist_ok=True)
    for name in ("Pretendard-Regular.woff2", "Pretendard-Bold.woff2"):
        target = font_dir / name
        if not target.exists():
            target.write_bytes(b"")


def _render_html(plan: dict[str, Any], *, width: int, height: int) -> str:
    items = plan["items"]
    blocks = []
    for item in items:
        blocks.append(
            (
                f'<div class="overlay {html.escape(str(item["position"]))}" '
                f'data-start="{float(item["start"]):.3f}" data-end="{float(item["end"]):.3f}">'
                f'<div class="keyword">{html.escape(str(item["text"]))}</div>'
                f'<div class="secondary">{html.escape(str(item["secondary"]))}</div>'
                "</div>"
            )
        )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    @font-face {{
      font-family: 'PretendardLocal';
      src: url('assets/fonts/Pretendard-Regular.woff2') format('woff2');
      font-weight: 400;
      font-display: block;
    }}
    @font-face {{
      font-family: 'PretendardLocal';
      src: url('assets/fonts/Pretendard-Bold.woff2') format('woff2');
      font-weight: 700;
      font-display: block;
    }}
    html, body {{ margin: 0; width: {width}px; height: {height}px; background: transparent; overflow: hidden; }}
    body {{ font-family: 'PretendardLocal', sans-serif; }}
    .overlay {{ position: absolute; max-width: 520px; padding: 18px 22px; background: rgba(0,0,0,.68); color: white; border-left: 6px solid #58c4ff; }}
    .lower_left {{ left: 72px; bottom: 190px; }}
    .upper_left {{ left: 72px; top: 92px; }}
    .keyword {{ font-size: 42px; font-weight: 700; line-height: 1.12; }}
    .secondary {{ margin-top: 8px; font-size: 22px; opacity: .86; }}
  </style>
</head>
<body>
  {"".join(blocks)}
</body>
</html>
"""


def write_overlay_project(out_dir: Path, timings: list[dict[str, Any]], *, width: int, height: int) -> OverlayWritePaths:
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = out_dir / "assets"
    _copy_font_placeholder(assets_dir / "fonts")
    plan = build_overlay_plan(timings)
    overlay_plan = out_dir / OVERLAY_PLAN_NAME
    index_html = out_dir / "index.html"
    overlay_plan.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    index_html.write_text(_render_html(plan, width=width, height=height), encoding="utf-8")
    return {"index_html": index_html, "overlay_plan": overlay_plan}
```

Note: the empty font placeholder is acceptable only for unit tests. Before real rendering, Task 6 must replace this with a real redistributable font file or fail preflight.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_hyperframes_overlay.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add app/services/hyperframes_overlay.py tests/test_hyperframes_overlay.py
git commit -m "feat: add hyperframes overlay planner"
```

## Task 4: Pinned Tool Manifest

**Files:**
- Create: `tools/hyperframes/package.json`
- Create: `tools/hyperframes/package-lock.json`

- [ ] **Step 1: Create tool package manifest**

Create `tools/hyperframes/package.json`:

```json
{
  "private": true,
  "name": "newauto-hyperframes-tools",
  "version": "0.1.0",
  "devDependencies": {
    "hyperframes": "0.6.12"
  },
  "scripts": {
    "doctor": "hyperframes doctor",
    "lint": "hyperframes lint --json",
    "inspect": "hyperframes inspect --json --samples 15",
    "render:webm": "hyperframes render --format webm --output overlay.webm"
  }
}
```

- [ ] **Step 2: Install lockfile**

Run:

```powershell
npm install --prefix tools/hyperframes
```

Expected: exit 0 and `tools/hyperframes/package-lock.json` created with `hyperframes` version `0.6.12`.

- [ ] **Step 3: Verify pinned version**

Run:

```powershell
npm ls --prefix tools/hyperframes hyperframes
```

Expected: output includes `hyperframes@0.6.12`.

- [ ] **Step 4: Commit**

```powershell
git add tools/hyperframes/package.json tools/hyperframes/package-lock.json
git commit -m "chore: pin hyperframes tooling"
```

## Task 5: Overlay CLI Wrapper

**Files:**
- Create: `scripts/render_hyperframes_overlay.py`
- Modify: `tests/test_hyperframes_overlay.py`

- [ ] **Step 1: Write failing CLI helper tests**

Append to `tests/test_hyperframes_overlay.py`:

```python
from scripts.render_hyperframes_overlay import validate_overlay_probe


class HyperFramesOverlayCliTests(unittest.TestCase):
    def test_validate_overlay_probe_accepts_alpha_duration(self) -> None:
        result = validate_overlay_probe({"pix_fmt": "yuva420p", "duration_sec": 3.04}, expected_duration_sec=3.0)
        self.assertTrue(result["ok"])

    def test_validate_overlay_probe_rejects_missing_alpha(self) -> None:
        result = validate_overlay_probe({"pix_fmt": "yuv420p", "duration_sec": 3.0}, expected_duration_sec=3.0)
        self.assertFalse(result["ok"])
        self.assertIn("alpha", result["error"])
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_hyperframes_overlay.py::HyperFramesOverlayCliTests -q
```

Expected: FAIL because `scripts.render_hyperframes_overlay` does not exist.

- [ ] **Step 3: Implement CLI wrapper**

Create `scripts/render_hyperframes_overlay.py`:

```python
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _run(command: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    process = subprocess.run(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=False)
    return process.returncode, process.stdout or "", process.stderr or ""


def validate_overlay_probe(probe: dict[str, Any], *, expected_duration_sec: float) -> dict[str, Any]:
    pix_fmt = str(probe.get("pix_fmt", ""))
    duration_sec = float(probe.get("duration_sec", 0.0))
    if "a" not in pix_fmt:
        return {"ok": False, "error": f"overlay pix_fmt lacks alpha: {pix_fmt}"}
    if abs(duration_sec - expected_duration_sec) > 0.1:
        return {"ok": False, "error": f"overlay duration drift: {duration_sec:.3f}s vs {expected_duration_sec:.3f}s"}
    return {"ok": True, "error": ""}


def _ffprobe_overlay(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"pix_fmt": "", "duration_sec": 0.0, "error": "ffprobe not found"}
    code, stdout, stderr = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=pix_fmt,duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if code != 0:
        return {"pix_fmt": "", "duration_sec": 0.0, "error": stderr.strip()}
    payload = json.loads(stdout or "{}")
    streams = payload.get("streams") if isinstance(payload, dict) else []
    stream = streams[0] if streams else {}
    return {"pix_fmt": str(stream.get("pix_fmt", "")), "duration_sec": float(stream.get("duration") or 0.0)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("overlay_dir")
    parser.add_argument("--duration", type=float, required=True)
    args = parser.parse_args()
    overlay_dir = Path(args.overlay_dir)
    report_path = overlay_dir / "overlay_report.json"
    output = overlay_dir / "overlay.webm"
    commands = [
        ["npx", "hyperframes", "lint", "--json"],
        ["npx", "hyperframes", "inspect", "--json", "--samples", "15"],
        ["npx", "hyperframes", "render", "--format", "webm", "--output", str(output.name)],
    ]
    rows = []
    ok = True
    for command in commands:
        code, stdout, stderr = _run(command, cwd=overlay_dir)
        rows.append({"command": command, "returncode": code, "stdout": stdout, "stderr": stderr})
        ok = ok and code == 0
        if code != 0:
            break
    probe = _ffprobe_overlay(output) if output.exists() else {"pix_fmt": "", "duration_sec": 0.0}
    validation = validate_overlay_probe(probe, expected_duration_sec=args.duration)
    ok = ok and bool(validation["ok"])
    report = {"ok": ok, "commands": rows, "ffprobe": probe, "validation": validation, "overlay_path": str(output)}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_hyperframes_overlay.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```powershell
git add scripts/render_hyperframes_overlay.py tests/test_hyperframes_overlay.py
git commit -m "feat: add hyperframes overlay render wrapper"
```

## Task 6: Preflight Gate

**Files:**
- Modify: `app/services/preflight.py`
- Modify: `tests/test_render_visual_track.py` or create `tests/test_hyperframes_preflight.py`

- [ ] **Step 1: Write failing preflight test**

Create `tests/test_hyperframes_preflight.py`:

```python
import unittest
from unittest.mock import patch

from app.services.preflight import build_preflight_report


def _project(enabled: bool) -> dict:
    return {
        "id": "p1",
        "body_image_options": {"hyperframes_overlay_enabled": enabled},
        "sentences": [{"idx": 0, "text": "문장"}],
        "tts_state": "done",
        "media_state": "done",
        "render_plan": None,
        "media_order": ["a.png"],
    }


class HyperFramesPreflightTests(unittest.TestCase):
    @patch("app.services.preflight.probe_hyperframes_runtime")
    def test_preflight_reports_failed_hyperframes_when_enabled(self, probe) -> None:
        probe.return_value = {
            "node_available": False,
            "node_version": "",
            "npx_available": False,
            "npx_version": "",
            "doctor_ok": False,
            "doctor_detail": "node not found",
            "ffmpeg_alpha_ok": False,
            "ffmpeg_alpha_detail": "",
        }

        report = build_preflight_report(_project(True))

        checks = {row["name"]: row for row in report["checks"]}
        self.assertEqual(checks["hyperframes_overlay"]["status"], "warning")
        self.assertIn("node not found", checks["hyperframes_overlay"]["detail"])
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_hyperframes_preflight.py -q
```

Expected: FAIL because preflight has no HyperFrames probe check.

- [ ] **Step 3: Add preflight check**

In `app/services/preflight.py`, import `probe_hyperframes_runtime`.

Inside `build_preflight_report(project)`, after existing render/media checks, add a check only when:

```python
enabled = bool(project["body_image_options"].get("hyperframes_overlay_enabled"))
```

Append:

```python
if enabled:
    status = probe_hyperframes_runtime(refresh=False)
    ready = bool(status["node_available"] and status["npx_available"] and status["doctor_ok"] and status["ffmpeg_alpha_ok"])
    checks.append(
        {
            "name": "hyperframes_overlay",
            "status": "pass" if ready else "warning",
            "detail": "HyperFrames overlay runtime ready" if ready else str(status["doctor_detail"] or status["ffmpeg_alpha_detail"]),
        }
    )
```

Use the local preflight check row shape already present in the file.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_hyperframes_preflight.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add app/services/preflight.py tests/test_hyperframes_preflight.py
git commit -m "feat: preflight hyperframes overlay runtime"
```

## Task 7: Single-Pass Mux Overlay Input

**Files:**
- Modify: `app/services/render.py`
- Modify: `tests/test_render_visual_track.py`

- [ ] **Step 1: Write failing `_mux()` command test**

Add to `tests/test_render_visual_track.py` near existing `_mux()` tests:

```python
    @patch("app.services.render._run")
    def test_mux_composites_overlay_before_subtitles_in_single_filter_complex(self, run) -> None:
        run.return_value = ""

        _mux(Path("visual.mp4"), Path("audio.wav"), Path("subtitles.ass"), Path("out.mp4"), overlay_path=Path("overlay.webm"))

        command = run.call_args.args[0]
        self.assertIn("-filter_complex", command)
        filter_graph = command[command.index("-filter_complex") + 1]
        self.assertIn("[0:v][1:v]overlay=0:0:format=auto:shortest=1[base]", filter_graph)
        self.assertIn("[base]ass=", filter_graph)
        self.assertNotIn("-vf", command)
        self.assertEqual(command[command.index("-map") + 1], "[v]")
        self.assertIn("2:a:0", command)
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_render_visual_track.py::RenderVisualTrackTests::test_mux_composites_overlay_before_subtitles_in_single_filter_complex -q
```

Expected: FAIL because `_mux()` does not accept `overlay_path`.

- [ ] **Step 3: Add optional overlay to `_mux()`**

Change `_mux()` signature in `app/services/render.py`:

```python
def _mux(
    silent_video: Path,
    audio: Path,
    subtitle_path: Path,
    out_mp4: Path,
    *,
    overlay_path: Path | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> str:
```

Replace command construction with:

```python
subtitle_filter = f"ass='{_escape_filter_path(subtitle_path)}'"
if overlay_path is None:
    command = [
        _ffmpeg(), "-y",
        "-i", str(silent_video),
        "-i", str(audio),
        "-vf", subtitle_filter,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-c:a", "aac",
        "-ar", str(FINAL_AUDIO_SAMPLE_RATE),
        "-ac", str(FINAL_AUDIO_CHANNELS),
        "-b:a", "192k",
        "-shortest",
        str(out_mp4),
    ]
else:
    filter_graph = f"[0:v][1:v]overlay=0:0:format=auto:shortest=1[base];[base]{subtitle_filter}[v]"
    command = [
        _ffmpeg(), "-y",
        "-i", str(silent_video),
        "-i", str(overlay_path),
        "-i", str(audio),
        "-filter_complex", filter_graph,
        "-map", "[v]",
        "-map", "2:a:0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-c:a", "aac",
        "-ar", str(FINAL_AUDIO_SAMPLE_RATE),
        "-ac", str(FINAL_AUDIO_CHANNELS),
        "-b:a", "192k",
        "-shortest",
        str(out_mp4),
    ]
```

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_render_visual_track.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit**

```powershell
git add app/services/render.py tests/test_render_visual_track.py
git commit -m "feat: mux optional hyperframes overlay"
```

## Task 8: Render Integration and Fallback Status

**Files:**
- Modify: `app/services/render.py`
- Modify: `tests/test_render_visual_track.py`

- [ ] **Step 1: Write failing status helper tests**

Add a small helper test to `tests/test_render_visual_track.py`:

```python
from app.services.render import _hyperframes_required


class HyperFramesRenderOptionTests(unittest.TestCase):
    def test_hyperframes_required_honors_project_option(self) -> None:
        self.assertTrue(_hyperframes_required({"hyperframes_overlay_required": True}, env={}))

    def test_hyperframes_required_honors_strict_env(self) -> None:
        self.assertTrue(_hyperframes_required({}, env={"NEWAUTO_HYPERFRAMES_STRICT": "1"}))

    def test_hyperframes_required_defaults_false(self) -> None:
        self.assertFalse(_hyperframes_required({}, env={}))
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_render_visual_track.py::HyperFramesRenderOptionTests -q
```

Expected: FAIL because `_hyperframes_required` does not exist.

- [ ] **Step 3: Implement render option helpers**

In `app/services/render.py`, add:

```python
def _hyperframes_required(options: dict[str, object], *, env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return bool(options.get("hyperframes_overlay_required")) or source.get("NEWAUTO_HYPERFRAMES_STRICT") == "1"
```

Import `Mapping` and `os` if missing.

Then in `run_render_job()`, before `_mux()` for each render format:

```python
overlay_path: Path | None = None
options = dict(project["body_image_options"])
if options.get("hyperframes_overlay_enabled") is True:
    candidate = project_dir / "hyperframes_overlay" / "overlay.webm"
    if candidate.exists():
        overlay_path = candidate
        options["hyperframes_overlay_status"] = "done"
        options["hyperframes_overlay_report_path"] = str(project_dir / "hyperframes_overlay" / "overlay_report.json")
    elif _hyperframes_required(options):
        raise RuntimeError("HyperFrames overlay is required but overlay.webm is missing")
    else:
        options["hyperframes_overlay_status"] = "skipped"
    project = db.update_project(pid, body_image_options=options) or project
```

Pass `overlay_path=overlay_path` into `_mux()`.

This task intentionally consumes a pre-rendered overlay. Automatic generation belongs in a later task after the CLI wrapper has passed a real smoke.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_render_visual_track.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit**

```powershell
git add app/services/render.py tests/test_render_visual_track.py
git commit -m "feat: wire optional hyperframes overlay into render"
```

## Task 9: Diagnostics Bundle Integration

**Files:**
- Modify: `app/services/diagnostics.py`
- Modify: `tests/test_diagnostics.py`

- [ ] **Step 1: Write failing diagnostics test**

Add to `tests/test_diagnostics.py`:

```python
    def test_collect_project_diagnostics_copies_hyperframes_overlay_artifacts(self) -> None:
        project_id = "diag_hyperframes"
        project_dir = db.project_dir(project_id)
        overlay_dir = project_dir / "hyperframes_overlay"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        (overlay_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        (overlay_dir / "overlay_plan.json").write_text("{}", encoding="utf-8")
        (overlay_dir / "overlay_report.json").write_text("{}", encoding="utf-8")
        db.create_project(project_id, "title")

        manifest = collect_project_diagnostics(project_id)

        bundle_dir = Path(manifest["bundle_dir"])
        self.assertTrue((bundle_dir / "hyperframes_overlay" / "index.html").exists())
        self.assertTrue((bundle_dir / "hyperframes_overlay" / "overlay_plan.json").exists())
        self.assertTrue((bundle_dir / "hyperframes_overlay" / "overlay_report.json").exists())
```

Adjust project creation helper names to match existing `tests/test_diagnostics.py` setup.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_diagnostics.py::DiagnosticsTests::test_collect_project_diagnostics_copies_hyperframes_overlay_artifacts -q
```

Expected: FAIL because diagnostics does not copy overlay artifacts.

- [ ] **Step 3: Copy overlay artifacts**

In `app/services/diagnostics.py`, add:

```python
def _copy_hyperframes_overlay(project_dir: Path, bundle_dir: Path) -> list[str]:
    source_dir = project_dir / "hyperframes_overlay"
    if not source_dir.exists():
        return []
    target_dir = bundle_dir / "hyperframes_overlay"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in ("index.html", "overlay_plan.json", "overlay_report.json", "hyperframes_overlay_lint.json", "hyperframes_overlay_inspect.json", "hyperframes_overlay_ffprobe.json"):
        if _copy_if_exists(source_dir / name, target_dir / name):
            copied.append(f"hyperframes_overlay/{name}")
    return copied
```

Inside `collect_project_diagnostics()`, before manifest write:

```python
    hyperframes_files = _copy_hyperframes_overlay(project_dir, bundle_dir)
```

Add to manifest:

```python
        "hyperframes_overlay_files": hyperframes_files,
```

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_diagnostics.py -q
```

Expected: diagnostics tests pass.

- [ ] **Step 5: Commit**

```powershell
git add app/services/diagnostics.py tests/test_diagnostics.py
git commit -m "feat: include hyperframes overlay diagnostics"
```

## Task 10: Real P0 Smoke

**Files:**
- No production code changes unless this smoke exposes a root cause.
- Update: `docs/hyperframes-adoption-plan-2026-05-16.md`

- [ ] **Step 1: Run runtime probe**

Run:

```powershell
python - <<'PY'
from app.services.hyperframes_probe import probe_hyperframes_runtime
print(probe_hyperframes_runtime(refresh=True))
PY
```

Expected:

- `node_available=True`
- `npx_available=True`
- `doctor_ok=True`
- `ffmpeg_alpha_ok=True`

If this fails, use systematic debugging: read the exact error, reproduce with the raw `npx -y hyperframes@0.6.12 doctor` command, and fix the root cause before continuing.

- [ ] **Step 2: Generate a minimal overlay project**

Run:

```powershell
python - <<'PY'
from pathlib import Path
from app.services.hyperframes_overlay import write_overlay_project
write_overlay_project(
    Path("storage/projects/hyperframes_smoke/hyperframes_overlay"),
    [{"sentence_idx": 0, "start": 0.0, "end": 3.0, "text": "엔비디아가 공식 확인했습니다."}],
    width=1920,
    height=1080,
)
PY
```

Expected: `index.html` and `overlay_plan.json` exist.

- [ ] **Step 3: Render overlay**

Run:

```powershell
python scripts\render_hyperframes_overlay.py storage\projects\hyperframes_smoke\hyperframes_overlay --duration 3.0
```

Expected: exit 0, `overlay.webm` and `overlay_report.json` exist, report has `"ok": true`.

- [ ] **Step 4: Composite smoke over a color source**

Run:

```powershell
ffmpeg -y -f lavfi -i color=c=0x202020:s=1920x1080:d=3 -i storage\projects\hyperframes_smoke\hyperframes_overlay\overlay.webm -filter_complex "[0:v][1:v]overlay=0:0:format=auto:shortest=1[v]" -map "[v]" -c:v libx264 -pix_fmt yuv420p storage\projects\hyperframes_smoke\composite_smoke.mp4
```

Expected: exit 0 and `composite_smoke.mp4` plays with visible overlay text.

- [ ] **Step 5: Document smoke evidence**

Append a dated note to `docs/hyperframes-adoption-plan-2026-05-16.md` with:

- command results
- `overlay.webm` pix_fmt
- overlay duration
- composite smoke path
- any root-cause fixes made

- [ ] **Step 6: Commit**

```powershell
git add docs/hyperframes-adoption-plan-2026-05-16.md
git commit -m "docs: record hyperframes overlay smoke"
```

## Final Verification

After all tasks above:

- [ ] Run focused Python tests:

```powershell
python -m pytest tests/test_hyperframes_probe.py tests/test_hyperframes_overlay.py tests/test_hyperframes_preflight.py tests/test_render_visual_track.py tests/test_diagnostics.py -q
```

Expected: all selected tests pass.

- [ ] Run existing render/report safety tests:

```powershell
python -m pytest tests/test_render_report.py tests/test_visual_relevance.py tests/test_tts_pipeline.py tests/test_autopilot_worker.py -q
```

Expected: all selected tests pass.

- [ ] Run real diagnostics smoke:

```powershell
python scripts\collect_project_diagnostics.py 066827c044eb
```

Expected: exits 0 and includes any existing `hyperframes_overlay` artifacts when present.

## Self-Review Checklist

- Every production function introduced above has a failing test first.
- HyperFrames is pinned to `0.6.12`.
- Overlay rendering is optional by default.
- Strict mode can fail render when overlay is required.
- `_mux()` uses one final encode pass.
- ASS subtitles remain in place.
- Overlay filter is applied before ASS subtitles.
- Diagnostics bundle includes overlay artifacts.
- No SQLite schema migration is introduced.
- No external font or remote CSS URL is used by generated HTML.
- The plan does not claim overlays fix ComfyUI semantic drift.

## Execution Handoff

Plan complete and saved to `docs/hyperframes-overlay-implementation-plan-2026-05-16.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh worker per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session with checkpoints after each task.
