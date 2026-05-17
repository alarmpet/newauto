# Cline + Qwen3.5 Obsidian Context

Updated: 2026-05-14 KST

Use the Obsidian Vault as a compact project memory source for `newauto`.

## First File To Read

Read this Vault note first:

`C:\Users\petbl\newauto_ObsidianVault\00_notes\_cline_qwen_context.md`

Then open only the specific note listed there that matches the active task.

## Purpose

The Vault contains older plans, troubleshooting records, and generated project evidence copied from `newauto`. It is useful for:

- remembering previous root causes
- finding known recovery paths
- understanding workflow intent
- avoiding repeated failed approaches
- locating relevant code areas faster

It is not authoritative when it conflicts with live code or current runtime state.

## Rules

- Prefer live code, API status, logs, tests, and git over old notes.
- Do not broadly load `06_project_data`; inspect only a specific project ID.
- Do not read or print secrets, tokens, cookies, OAuth files, browser profiles, `.env`, or `openrouter.txt`.
- Treat encoding-damaged notes as hints only.
- Keep summaries concise because Qwen runs best when context stays targeted.
- For article/news URL work, avoid browser screenshots and full browser state dumps. Use text fetch or targeted DOM extraction first.

## Current High-Value Lesson

The latest resolved issue is recorded in:

`C:\Users\petbl\newauto\issue.md`

Key lesson: if a Flow project already has all sentence images attached, ComfyUI health is not a render blocker. Check preflight first, rebuild stale scene/render plans, ensure the render worker is running, then render.
