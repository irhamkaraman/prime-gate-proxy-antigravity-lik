#!/usr/bin/env python3
"""
Model Context Protocol (MCP) Web Search Server for Prime Gate.
Provides high-performance, real-time web search capability to Claude Code, OpenCode, and any MCP client.
Zero API keys required. Uses DuckDuckGo HTML with DoH anti-blocking bypass and GitHub search.
"""

import sys
import os
import json
import asyncio
import logging
from typing import Any, Dict, List, Optional

# Add parent directory to sys.path so it can import prime_gate directly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# Configure logging to stderr so it doesn't pollute stdout (which is reserved for JSON-RPC)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [mcp_search] %(message)s"
)
logger = logging.getLogger("mcp_search")


async def do_search(query: str, max_results: int = 6) -> List[Dict[str, str]]:
    """Execute search via prime_gate.search engine or local HTTP endpoint."""
    # 1. Try importing prime_gate.search
    try:
        from prime_gate.search import search_web
        return await search_web(query, max_results=max_results)
    except Exception as e:
        logger.warning(f"Direct search_web import failed ({e}), trying HTTP endpoint...")

    # 2. Try HTTP endpoint if prime_gate is running
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://127.0.0.1:52111/v1/search",
                json={"q": query},
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
    except Exception as e:
        logger.error(f"HTTP search fallback failed: {e}")

    return []


def format_search_results(results: List[Dict[str, str]], query: str) -> str:
    """Format search results into clean markdown for AI consumption."""
    if not results:
        return f"No search results found for query: '{query}'."

    output = [f"### Web Search Results for: \"{query}\"\n"]
    for i, res in enumerate(results, start=1):
        title = res.get("title", "Untitled")
        url = res.get("url", "")
        snippet = res.get("snippet", "").strip()
        output.append(f"{i}. **[{title}]({url})**")
        if snippet:
            output.append(f"   {snippet}")
        output.append("")

    return "\n".join(output)


TOOL_DEFINITION = {
    "name": "web_search",
    "description": (
        "Search the live web for current real-time documentation, repositories, tools, or facts. "
        "Returns verified titles, URLs, and relevant text snippets. "
        "Use whenever you need up-to-date information, libraries, releases, or solutions."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query string (e.g. 'latest python 3.12 features', 'open source ai agent cli')."
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (1-10, default: 6).",
                "default": 6
            }
        },
        "required": ["query"]
    }
}


async def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    # 1. Initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "prime-gate-web-search",
                    "version": "1.2.0"
                }
            }
        }

    # 2. Initialized Notification
    if method == "notifications/initialized":
        return None

    # 3. Ping
    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        }

    # 4. List Tools
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [TOOL_DEFINITION]
            }
        }

    # 5. Call Tool
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if name in ("web_search", "search_web", "search"):
            query = args.get("query") or args.get("q") or ""
            max_res = int(args.get("max_results") or 6)
            max_res = max(1, min(max_res, 10))

            try:
                results = await do_search(query, max_results=max_res)
                text_content = format_search_results(results, query)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": text_content
                            }
                        ],
                        "isError": False
                    }
                }
            except Exception as e:
                logger.error(f"Error during search execution: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error performing web search: {str(e)}"
                            }
                        ],
                        "isError": True
                    }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method or tool not found: {name}"
                }
            }

    # Unknown method
    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not supported: {method}"
            }
        }
    return None


def main():
    logger.info("Prime Gate MCP Web Search Server started (stdio mode)...")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except Exception as e:
                logger.warning(f"Failed to parse JSON-RPC line: {e}")
                continue

            resp = asyncio.run(handle_request(req))
            if resp is not None:
                out_str = json.dumps(resp) + "\n"
                sys.stdout.write(out_str)
                sys.stdout.flush()
        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            logger.error(f"MCP loop error: {e}")


if __name__ == "__main__":
    main()
