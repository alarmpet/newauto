from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tauri_installed_sidecar_does_not_disable_workers_by_default():
    lib_rs = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")

    assert (
        '.env("NEWAUTO_DATA_DIR", data_dir)\n'
        '        .env("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")'
    ) not in lib_rs
    assert "NEWAUTO_STUDIO_DISABLE_BACKGROUND_WORKERS" in lib_rs


def test_backend_still_supports_explicit_worker_disable_env():
    main_py = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert 'DISABLE_BACKGROUND_WORKERS_ENV = "NEWAUTO_DISABLE_BACKGROUND_WORKERS"' in main_py
    assert "os.environ.get(DISABLE_BACKGROUND_WORKERS_ENV) == \"1\"" in main_py
