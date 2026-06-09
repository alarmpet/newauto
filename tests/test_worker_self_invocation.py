import unittest
from unittest.mock import patch

from app import main as app_main


class WorkerSelfInvocationTests(unittest.TestCase):
    def test_worker_command_uses_app_main_subcommand(self) -> None:
        with patch.object(app_main.sys, "executable", r"C:\Python\python.exe"), patch.object(
            app_main.sys,
            "frozen",
            False,
            create=True,
        ):
            self.assertEqual(
                app_main._worker_command("render"),
                [r"C:\Python\python.exe", "-m", "app.main", "--worker", "render"],
            )

    def test_worker_command_uses_frozen_self_invocation(self) -> None:
        with patch.object(app_main.sys, "executable", r"C:\Program Files\newauto Studio\newauto-sidecar.exe"), patch.object(
            app_main.sys,
            "frozen",
            True,
            create=True,
        ):
            self.assertEqual(
                app_main._worker_command("render"),
                [r"C:\Program Files\newauto Studio\newauto-sidecar.exe", "--worker", "render"],
            )

    def test_main_dispatches_worker_subcommand(self) -> None:
        with patch.object(app_main, "run_worker", return_value=7) as run_worker:
            exit_code = app_main.main(["--worker", "tts"])

        self.assertEqual(exit_code, 7)
        run_worker.assert_called_once_with("tts")

    def test_run_worker_rejects_unknown_worker(self) -> None:
        with self.assertRaises(ValueError):
            app_main.run_worker("missing")

    def test_spawn_worker_uses_self_invocation_command(self) -> None:
        popen_calls: list[list[str]] = []

        class DummyProcess:
            pass

        def fake_popen(command: list[str], **_: object) -> DummyProcess:
            popen_calls.append(command)
            return DummyProcess()

        with patch.object(app_main.subprocess, "Popen", side_effect=fake_popen), patch.object(
            app_main.sys,
            "executable",
            r"C:\Python\python.exe",
        ), patch.object(app_main.sys, "frozen", False, create=True):
            app_main._spawn_worker("image")

        self.assertEqual(
            popen_calls,
            [[r"C:\Python\python.exe", "-m", "app.main", "--worker", "image"]],
        )

    def test_main_dispatches_serve_subcommand(self) -> None:
        with patch.object(app_main, "serve_api", return_value=0) as serve_api:
            exit_code = app_main.main(["--serve", "--host", "127.0.0.1", "--port", "0"])

        self.assertEqual(exit_code, 0)
        serve_api.assert_called_once_with(host="127.0.0.1", port=0)

    def test_main_rejects_invalid_serve_port(self) -> None:
        with patch.object(app_main, "serve_api", side_effect=AssertionError("should not serve")):
            exit_code = app_main.main(["--serve", "--port", "not-a-port"])

        self.assertEqual(exit_code, 2)

    def test_serve_api_prints_port_handshake(self) -> None:
        class DummySocket:
            def getsockname(self) -> tuple[str, int]:
                return ("127.0.0.1", 54321)

        class DummyServer:
            def __init__(self, config: object) -> None:
                self.config = config

            def run(self, *, sockets: list[DummySocket]) -> None:
                self.sockets = sockets

        with patch.object(app_main, "_open_listen_socket", return_value=DummySocket()), patch(
            "uvicorn.Config",
            return_value=object(),
        ) as config, patch("uvicorn.Server", side_effect=DummyServer) as server, patch("builtins.print") as print_fn:
            exit_code = app_main.serve_api(host="127.0.0.1", port=0)

        self.assertEqual(exit_code, 0)
        config.assert_called_once()
        server.assert_called_once()
        print_fn.assert_called_with("NEWAUTO_LISTEN_PORT=54321", flush=True)


if __name__ == "__main__":
    unittest.main()
