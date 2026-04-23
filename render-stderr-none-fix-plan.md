# Render stderr None Fix Plan

## Goal

Fix the render failure where the job stops around `가로형 영상 구성` and crashes with:

```text
AttributeError: 'NoneType' object has no attribute 'strip'
```

Status: `[Done]`

## Confirmed Root Cause

The crash is not the original FFmpeg render failure. The render pipeline is failing while trying to format the FFmpeg log tail.

Relevant code in [app/services/render.py](C:/Users/petbl/newauto/app/services/render.py):

- `_run()` calls:
  - `subprocess.run(command, capture_output=True, text=True, check=False)`
- On success, `_run()` returns:
  - `_tail_lines(process.stderr)`
- `_tail_lines()` assumes `text` is always a string:
  - `text.strip().splitlines()`

That assumption is unsafe.

If `process.stderr` is `None`, the successful render path crashes here:

```python
def _tail_lines(text: str, limit: int = 12) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
```

So the actual sequence is:

1. `_build_visual_track()` calls `_run(...)`
2. FFmpeg may succeed or at least return without usable stderr text
3. `_run()` calls `_tail_lines(process.stderr)`
4. `process.stderr is None`
5. `_tail_lines()` crashes with `AttributeError`
6. Render job is marked as error at about `70%`

This means the renderer is currently vulnerable to a logging bug, not only a media-processing bug.

## Why It Shows At 70%

In [app/services/render.py](C:/Users/petbl/newauto/app/services/render.py), the landscape build phase sets:

- `build_visual_landscape`
- then `_build_visual_track(...)`

So once `_run()` returns from that phase and tries to read `stderr`, the job dies during the phase log handling. That is why the UI shows:

- phase: `가로형 영상 구성`
- progress: around `70%`

## Additional Problems Found

### 1. The failure path has the same unsafe assumption

In `_run()`:

```python
if process.returncode != 0:
    stderr_tail = process.stderr.strip().splitlines()[-20:]
```

If FFmpeg really fails and `process.stderr` is also `None`, the error handler itself will raise another `AttributeError` instead of returning a useful FFmpeg message.

### 2. `_tail_lines()` should accept empty log content safely

The helper is currently typed and implemented as if log text is always present. In practice, subprocess output can be:

- `None`
- empty string
- whitespace only

All of these should safely return `""`.

### 3. Render stage logging should not be able to crash rendering

Even if FFmpeg logging is missing, the render pipeline should continue or fail with the original render error, not with an internal bookkeeping error.

## Fix Plan

### Phase 1. Make log tail helpers null-safe `[Done]` (P0)

- Update `_tail_lines()` to accept `str | None`
- Return `""` when the value is `None`, empty, or whitespace-only

Suggested direction:

```python
def _tail_lines(text: str | None, limit: int = 12) -> str:
    if not text:
        return ""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-limit:])
```

Done when:

- `_tail_lines(None)` no longer crashes
- `_tail_lines("")` returns `""`

### Phase 2. Make `_run()` success and failure branches safe `[Done]` (P0)

- Replace direct `process.stderr.strip()` access with `_tail_lines(process.stderr, ...)`
- Preserve the real subprocess return code behavior

Suggested direction:

```python
def _run(command: list[str]) -> str:
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    stderr_tail = _tail_lines(process.stderr, limit=20)
    if process.returncode != 0:
        detail = stderr_tail or "ffmpeg failed with no stderr output"
        raise RuntimeError(f"ffmpeg failed:\n{detail}")
    return _tail_lines(process.stderr)
```

Done when:

- A missing `stderr` can never trigger `AttributeError`
- Real FFmpeg failures still produce useful errors

### Phase 3. Add regression tests for empty and missing stderr `[Done]` (P1)

Add tests around the render helper behavior:

```python
def test_tail_lines_handles_none(): ...
def test_tail_lines_handles_empty_string(): ...
def test_run_handles_success_with_none_stderr(): ...
def test_run_handles_failure_with_none_stderr(): ...
```

These can mock `subprocess.run` and feed:

- `returncode=0, stderr=None`
- `returncode=1, stderr=None`
- `returncode=1, stderr="actual ffmpeg error"`

Done when:

- The current crash becomes impossible to reintroduce silently

### Phase 4. Improve user-facing render error detail `[Done]` (P1)

- Ensure the final `render_last_log` stores the actual subprocess failure detail when available
- Avoid replacing a real FFmpeg error with a secondary Python `AttributeError`

Done when:

- If FFmpeg truly fails, the UI shows the real render reason
- If logs are absent, the UI shows a fallback message instead of a Python exception

## Expected Outcome

After this fix:

- Rendering will no longer crash just because `stderr` is missing
- The `가로형 영상 구성` phase can complete normally if FFmpeg succeeded
- If FFmpeg really fails, the UI will show the original render error rather than `NoneType.strip`
