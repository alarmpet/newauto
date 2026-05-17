import importlib
import os
import unittest
from unittest.mock import patch


class ConfigTests(unittest.TestCase):
    def _register_config_restore(self) -> None:
        snapshot = {
            key: os.getenv(key)
            for key in ("LLM_PROVIDER", "OLLAMA_BASE_URL", "LMSTUDIO_BASE_URL", "SCRIPT_LLM_MODEL", "NEWAUTO_DATA_DIR")
        }
        self.addCleanup(self._restore_config_env_and_reload, snapshot)
        return None

    def _restore_config_env_and_reload(self, snapshot: dict[str, str | None]) -> None:
        restored: dict[str, str] = {}
        clear_keys: list[str] = []
        for key, original in snapshot.items():
            if original is None:
                clear_keys.append(key)
            else:
                restored[key] = original
        with patch.dict(os.environ, restored, clear=False):
            for key in clear_keys:
                os.environ.pop(key, None)
            from app import config

            importlib.reload(config)

    def test_lmstudio_falls_back_to_ollama_url_with_warning(self) -> None:
        from app import config

        self._register_config_restore()
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "lmstudio",
            "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            "LMSTUDIO_BASE_URL": "",
        }, clear=False):
            with patch.object(config._LOGGER, "warning") as warn:
                importlib.reload(config)

                self.assertEqual(config.LLM_PROVIDER, "lmstudio")
                self.assertEqual(config.LMSTUDIO_BASE_URL, "http://127.0.0.1:11434")
                warn.assert_called_once()

    def test_lmstudio_uses_explicit_base_url_without_warning(self) -> None:
        from app import config

        self._register_config_restore()
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "lmstudio",
            "LMSTUDIO_BASE_URL": "http://127.0.0.1:1234",
        }, clear=False):
            with patch.object(config._LOGGER, "warning") as warn:
                with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://127.0.0.1:11434"}, clear=False):
                    importlib.reload(config)

                self.assertEqual(config.LLM_PROVIDER, "lmstudio")
                self.assertEqual(config.LMSTUDIO_BASE_URL, "http://127.0.0.1:1234")
                warn.assert_not_called()

    def test_newauto_data_dir_overrides_storage_dir(self) -> None:
        from app import config

        self._register_config_restore()
        with patch.dict(os.environ, {"NEWAUTO_DATA_DIR": r"C:\newauto-test-data"}, clear=False):
            importlib.reload(config)

            self.assertEqual(str(config.STORAGE_DIR), r"C:\newauto-test-data")
            self.assertEqual(str(config.PROJECTS_DIR), r"C:\newauto-test-data\projects")

    def test_lmstudio_defaults_to_builtin_base_url_when_missing(self) -> None:
        from app import config

        self._register_config_restore()
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "lmstudio",
            "OLLAMA_BASE_URL": "",
            "LMSTUDIO_BASE_URL": "",
        }, clear=False):
            with patch.object(config._LOGGER, "warning") as warn:
                importlib.reload(config)

                self.assertEqual(config.LLM_PROVIDER, "lmstudio")
                self.assertEqual(config.LMSTUDIO_BASE_URL, "http://127.0.0.1:1234")
                warn.assert_not_called()

    def test_default_llm_is_lmstudio_gemma4(self) -> None:
        from app import config

        self._register_config_restore()
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "",
            "LMSTUDIO_BASE_URL": "",
            "SCRIPT_LLM_MODEL": "",
        }, clear=False):
            importlib.reload(config)

            self.assertEqual(config.LLM_PROVIDER, "lmstudio")
            self.assertEqual(config.LMSTUDIO_BASE_URL, "http://127.0.0.1:1234")
            self.assertEqual(config.SCRIPT_LLM_MODEL, "google/gemma-4-e4b")
