# Source Collection and Gemma4 Snapshot Routing Plan

## Goal

Cline should collect article/source content through text-first tools, and use screenshot analysis through OpenRouter Gemma4 only when visual/browser state cannot be solved from text or DOM.

## Decision Rule

Use screenshots only for visual diagnosis.

Do not use screenshots to read article content.

## Normal Article Collection Flow

1. Start with `sequential-thinking` for multi-step source/video workflows.
2. Use `web_fetch` or an equivalent text fetch tool to retrieve the article HTML.
3. Extract only the useful article fields:
   - title
   - body
   - author/reporter
   - published/updated date
   - outlet
   - canonical URL
4. For Naver News, try these selectors first:
   - `#title_area`
   - `#dic_area`
   - `.media_end_head_journalist_name`
   - `.media_end_head_info_datestamp_time`
   - canonical/meta tags
5. If text fetch is blocked or incomplete, open the page with Playwright but extract text only:
   - `document.querySelector('#dic_area')?.innerText`
   - article-specific selectors
   - `document.body.innerText`
6. If desktop Naver News is blocked, retry with mobile URL or mobile article body selectors.
7. Summarize article facts locally with LM Studio/Qwen.

## Visual/Browser Problem Flow

Use screenshot analysis only when one of these is true:

- browser operation fails
- page state is unclear from DOM/text
- UI is blocked by login, captcha, modal, popup, or consent layer
- click target is unclear
- generated Flow image/video result must be visually checked
- automation says `[SCREENSHOT_ANALYSIS_NEEDED]`

Then:

1. Capture a bounded screenshot.
2. Send it to OpenRouter Gemma4 using `analyze_browser_screenshot` or the approved image analysis script.
3. Ask Gemma4 for observable facts only.
4. Return to local Qwen/Cline with a text facts packet.
5. Verify the next action locally before clicking, retrying, or editing state.

## OpenRouter Boundary

OpenRouter Gemma4 is advisory only.

Do not send:

- API keys
- cookies
- browser profiles
- full logs
- full raw HTML
- full project dumps

Send only:

- bounded screenshots for visual diagnosis
- concise redacted facts
- selected relevant error snippets
- exact blocker description

## Expected Behavior for HPSL News Workflows

For a Naver News URL:

1. Plan with `sequential-thinking`.
2. Fetch/extract article text.
3. Produce Korean issue summary.
4. Create HPSL script.
5. Generate Flow prompts.
6. Continue image/TTS/render workflow.
7. Use OpenRouter Gemma4 screenshot analysis only if Flow/browser UI gets stuck or visual output needs inspection.

## Completion Criteria

- Article content was obtained from text/DOM, not screenshot OCR.
- Screenshot analysis was used only for visual/browser uncertainty.
- Any OpenRouter result was converted into a local text facts packet.
- Final workflow artifacts are verified by file path or project status before reporting completion.
