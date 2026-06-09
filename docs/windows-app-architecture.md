# Windows App Architecture

Date: 2026-05-15

This document splits the Windows Studio packaging decisions out of
`docs/newauto-windows-studio-master-plan-2026-05-15.md`.

## Decision

Use `Tauri 2 + FastAPI sidecar + existing Python engine`.

- Tauri owns the native Windows window, installer, menu, and shutdown lifecycle.
- FastAPI remains the local backend and serves the existing static UI.
- PyInstaller builds the backend as a `onedir` sidecar.
- User data lives outside the source tree through `NEWAUTO_DATA_DIR`, defaulting to `%LOCALAPPDATA%\newauto Studio` when frozen.
- LM Studio remains an optional external agent track. The deterministic pipeline must work with AI mode off.

## Startup

Development mode keeps the stable port:

```powershell
python -m app.main --serve --host 127.0.0.1 --port 9002
```

Sidecar mode uses a dynamic port:

```powershell
newauto-sidecar.exe --serve --host 127.0.0.1 --port 0
```

The backend prints one machine-readable line after binding:

```text
NEWAUTO_LISTEN_PORT=<port>
```

Tauri should parse that line and load `http://127.0.0.1:<port>/`.

The current Tauri shell starts the sidecar during setup, waits up to 30 seconds for the port line, keeps the process alive for the app lifetime, and navigates the main window to the dynamic backend URL. It sets `NEWAUTO_DISABLE_BACKGROUND_WORKERS=1` while the bundled sidecar is API/orchestration-only.

## Workers

Workers are invoked through the same entrypoint:

```powershell
python -m app.main --worker render
python -m app.main --worker tts
python -m app.main --worker image
python -m app.main --worker source_draft
python -m app.main --worker autopilot
```

Inside a PyInstaller bundle, the same pattern becomes:

```powershell
newauto-sidecar.exe --worker render
```

This avoids `python -m app.workers.*`, which does not map cleanly to a bundled executable.

## Build Pieces

- `src-tauri/`: Tauri shell and NSIS bundle config. The bundle includes the trimmed PyInstaller `onedir` sidecar as a resource at `newauto-sidecar/`.
- `scripts/build_pyinstaller_sidecar.ps1`: PyInstaller `onedir` sidecar builder. It excludes heavy ML/GPU packages such as Torch, Transformers, Diffusers, Gradio, SciPy, and scikit-learn so the Windows Studio shell can package the API/orchestration layer first.
- `scripts/pyinstaller_entry.py`: package-safe entrypoint that imports `app.main` instead of running `app/main.py` as a loose script.
- `scripts/smoke_sidecar_handshake.ps1`: launches the built sidecar on a dynamic port with an isolated `NEWAUTO_DATA_DIR`, checks `NEWAUTO_LISTEN_PORT`, calls `/health`, and terminates the process.
- `scripts/smoke_tauri_launch.ps1`: launches `src-tauri/target/debug/newauto-studio.exe`, reads the app-written port file, calls the bundled sidecar `/health`, and cleans up the local port owner.
- `scripts/check_windows_studio_deps.py`: local dependency diagnostic for Python, Node, Tauri CLI, Rust/Cargo, FFmpeg, FastAPI, Uvicorn, and PyInstaller.

## Current Gaps

- Rust/Cargo is installed on the current machine through Rustup.
- The Tauri shell is scaffolded and `npx tauri build --debug` produced an NSIS installer at `src-tauri/target/debug/bundle/nsis/newauto Studio_0.1.0_x64-setup.exe`.
- The PyInstaller sidecar builds at `dist/newauto-sidecar/newauto-sidecar.exe`.
- Sidecar handshake smoke passed on 2026-05-15: dynamic port output was detected and `/health` returned `ok=true`.
- The Tauri shell now spawns the sidecar and navigates the main window to its dynamic port in development/debug builds.
- Tauri app launch smoke passed on 2026-05-15: `src-tauri/target/debug/newauto-studio.exe` started its bundled sidecar, wrote the dynamic port file, and served `/health ok=true`.
- Bundling the untrimmed PyInstaller `onedir` folder failed in `makensis` because Torch/CUDA DLLs pushed the resource payload into multi-gigabyte territory. After excluding heavy ML/GPU packages, the sidecar folder is about 197 MB and `npx tauri build --debug` succeeds with the sidecar resource included.
- Tauri assigns the sidecar to a Windows JobObject with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, so the child process is cleaned up when the app exits or is force-closed. The launch smoke confirms no `newauto*` processes remain after cleanup.
- Full worker packaging is still pending. The bundled sidecar is currently scoped to the Studio API/orchestration shell; ML-heavy TTS/image/agent workers should be packaged separately or resolved from external runtimes.
