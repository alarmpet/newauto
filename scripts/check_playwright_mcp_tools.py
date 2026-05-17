from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

MCP_PYTHON = Path.home() / "local-rag" / ".venv" / "Scripts" / "python.exe"

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ModuleNotFoundError:
    current = Path(sys.executable).resolve()
    if MCP_PYTHON.exists() and current != MCP_PYTHON.resolve():
        os.execv(str(MCP_PYTHON), [str(MCP_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise


REQUIRED_TOOLS = {
    "browser_navigate",
    "browser_evaluate",
    "browser_snapshot",
}
INVALID_TOOLS = {
    "browser_extract_content",
}


async def _list_playwright_tools() -> list[str]:
    params = StdioServerParameters(
        command="npx",
        args=["-y", "@playwright/mcp@latest"],
        env={"PLAYWRIGHT_BROWSERS_PATH": "0"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            return sorted(tool.name for tool in response.tools)


async def _main_async() -> dict[str, Any]:
    tools = await _list_playwright_tools()
    tool_set = set(tools)
    missing_required = sorted(REQUIRED_TOOLS - tool_set)
    invalid_visible = sorted(INVALID_TOOLS & tool_set)
    return {
        "ok": not missing_required and not invalid_visible,
        "required_tools": sorted(REQUIRED_TOOLS),
        "missing_required": missing_required,
        "invalid_tools_that_should_not_exist": sorted(INVALID_TOOLS),
        "invalid_visible": invalid_visible,
        "tool_count": len(tools),
        "tools": tools,
        "recommended_article_extraction_tool": "browser_evaluate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check actual @playwright/mcp tool names for Cline/Qwen routing.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    args = parser.parse_args()

    result = asyncio.run(_main_async())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ok={result['ok']} tool_count={result['tool_count']}")
        print(f"missing_required={result['missing_required']}")
        print(f"invalid_visible={result['invalid_visible']}")
        print("recommended_article_extraction_tool=browser_evaluate")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
