import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextmanager
def single_instance_lock(lock_path: Path) -> Iterator[bool]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    while lock_path.exists():
        try:
            existing_pid = int(lock_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            existing_pid = 0
        if existing_pid and _pid_exists(existing_pid):
            yield False
            return
        lock_path.unlink(missing_ok=True)
    try:
        file_descriptor = os.open(
            str(lock_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        yield True
    finally:
        lock_path.unlink(missing_ok=True)
