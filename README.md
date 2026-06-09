## LLM Provider Migration (Ollama ↔ LM Studio)

`docs/solutions/` stores documented fixes and workflow lessons with searchable frontmatter; relevant when debugging or changing prompt, image, TTS, render, or autopilot behavior.

This project supports two LLM providers with the same script generation flow:

- `ollama` (default)
- `lmstudio`

### Environment variables

Set these when starting the server:

- `LLM_PROVIDER`
  - `ollama` (default)
  - `lmstudio`
- `OLLAMA_BASE_URL` (for Ollama API, default `http://127.0.0.1:11434`)
- `LMSTUDIO_BASE_URL` (for LM Studio API, default `http://127.0.0.1:1234`)

### Migration behavior

- Ollama calls use `/api/generate`.
- LM Studio calls use `/v1/chat/completions`.
- Request mapping:
  - `system` + `prompt` -> `messages` (`system`, `user`)
  - `num_predict` -> `max_tokens`
  - `keep_alive` is not sent to LM Studio (no-op in adapter).
- LM Studio warm/unload are treated as no-op in current adapter.
- If `LLM_PROVIDER=lmstudio` but `LMSTUDIO_BASE_URL` is missing, the app keeps running by falling back to `OLLAMA_BASE_URL` and logging a warning.
- `SCRIPT_LLM_MODEL` default remains `gemma4:e4b`.

## Migration checklist (quick verification)

1. Set provider and URL
   - Set `LLM_PROVIDER=lmstudio`.
   - Set `LMSTUDIO_BASE_URL` (or temporarily use `OLLAMA_BASE_URL` for compatibility).
2. Verify model provider route usage
   - Ollama mode: uses `/api/generate`.
   - LM Studio mode: uses `/v1/chat/completions`.
3. Verify API payload mapping
   - `system` + `prompt` are mapped to OpenAI-like `messages` in LM Studio mode.
   - `num_predict` is mapped to `max_tokens` in LM Studio mode.
   - `keep_alive` is not sent to LM Studio (treated as no-op in adapter).
4. Verify operational compatibility
   - `source_draft_worker` resource key is set to `lmstudio`.
   - readiness check uses `/v1/models` in LM Studio mode.
   - unload/warm operations are no-op in LM Studio mode.
