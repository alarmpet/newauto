# Browser And Flow Rules

## Gate
- If there is no explicit action request, answer directly and do not use browser tools.
- Simple questions never need Playwright, browser-use, screenshots, or vision analysis.

## Article Reading
- For article/news/source collection, use text-first extraction.
- Prefer HTML fetch or targeted DOM selectors for title, body, author, dates, outlet, and canonical URL.
- For Naver News, prefer `#title_area`, `#dic_area`, reporter/date selectors, canonical/meta tags, and mobile fallback.
- Browser state dumps are not article extraction.

## Screenshot Budget
- Use screenshots for visual UI state, captcha/login/overlay, layout bugs, click-target uncertainty, generated images, or visual review.
- Use DOM/status/logs before screenshots when text is enough.
- Keep base64 images, full-page screenshots, full HTML, full accessibility trees, and large interactive dumps out of local Qwen context.
- If visual analysis is required, pass a screenshot file path to `analyze_browser_screenshot` and keep only the returned text facts.

## Playwright
- Current useful Playwright MCP tools include `browser_navigate`, `browser_evaluate`, `browser_snapshot`, `browser_tabs`, `browser_wait_for`, and `browser_network_requests`.
- There is no `browser_extract_content` tool; use `browser_evaluate` with selectors instead.
- If a requested browser tool is not visible, report the missing tool name instead of inventing one.

## Google Flow
- "Flow" means Google Flow at `https://labs.google/fx/ko/tools/flow/` unless the user says local app, MakeLens app, or port `9002`.
- Inspect current tabs/pages and prefer an existing Google Flow tab when present.
- Do not use hardcoded old Flow project UUIDs as targets.
- Do not navigate to local newauto for Google Flow tasks unless explicitly requested.
- Opening a URL is not success; verify with DOM/browser result, app API, downloaded file, or project media artifact.
- Pace interactive Flow generation one prompt at a time unless a script explicitly owns the loop.

## Local App Browser
- For local newauto app tasks, use `http://127.0.0.1:9002` unless the user explicitly asks for another port.
- `scripts/open_browser.ps1` is for the local app, not Google Flow.
