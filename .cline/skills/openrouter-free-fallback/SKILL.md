# OpenRouter Free Fallback

Use this skill when Cline needs OpenRouter help in restricted mode. Only OpenRouter free models and MCP tools are allowed.

## Default

- Use MCP tools and the repository MCP wrappers first.
- Do not use shell, browser, GUI, or non-MCP local tools from Cline.
- Do not use OpenRouter for trivial edits, normal file reading, simple searches, or routine implementation.
- Prefer the `newauto` repository harness over direct API calls.
- For `/api/projects/<id>/output` 404s after render appears complete, check `/api/projects/<id>/render-report` and the filesystem once. If the completed artifact is `output_shorts.mp4`, use `?format=shorts`; if the mismatch is still unexplained after those checks, escalate through OpenRouter before more local retries.
- Do not parse `/api/projects/<id>/output` as JSON. Use `/api/projects/<id>/render-report` for JSON metadata.

## Required Budget Check

Before any OpenRouter call, run:

```powershell
python scripts\openrouter_subagent_harness.py --budget-status --json-output
```

Run this only through an MCP tool or an allowed repository MCP wrapper. Do not execute it through Cline shell/terminal in restricted mode.

If the budget is near the limit or a rate limit occurs, stop and ask the user.

## Allowed Calling Path

Use the repository harness:

```powershell
python scripts\openrouter_subagent_harness.py --mode review --task-stdin --files <relevant-files> --json-output
```

Use this path only through MCP or an allowed repository MCP wrapper in restricted mode.

Use `--task-stdin` or `--task-file` for Korean, multiline, quoted, JSON-like, or shell-sensitive prompts.

## Model Rules

- Use only OpenRouter models ending with `:free`.
- Never call paid OpenRouter models.
- If specifying a model manually, pass it as a separate `--model <id>:free` argument.

## Secret Safety

- Never read or send `openrouter.txt`.
- Never expose or transmit API keys, tokens, cookies, browser profiles, credentials, private keys, or credential-containing logs.
- Never send full private logs or full project dumps.
- Send only concise summaries, selected file snippets, and relevant error output.

## After Advice

- Treat OpenRouter output as advisory, not authoritative.
- Verify locally before editing or applying a recommendation.
- Report the confirmed local result to the user in Korean.
