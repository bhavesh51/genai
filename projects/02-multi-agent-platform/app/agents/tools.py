"""
Project 2 – Multi-Agent Platform
Agent tools: web search, SQL query, code execution sandbox
"""
import logging
from typing import Optional

import httpx
from langchain.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)


@tool
async def search_web_tool(query: str) -> str:
    """Search the web for current information using SerpAPI."""
    if not settings.SERPAPI_KEY:
        return f"[Search unavailable – no SERPAPI_KEY configured] Query was: {query}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": settings.SERPAPI_KEY, "num": 5},
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("organic_results", [])
        snippets = "\n".join(
            f"- {r.get('title')}: {r.get('snippet', '')}" for r in results[:5]
        )
        return snippets or "No results found."


@tool
async def run_sql_query_tool(sql: str) -> str:
    """Execute a read-only SQL query against the analytics database."""
    import asyncpg
    # Safety: only allow SELECT statements
    clean = sql.strip().upper()
    if not clean.startswith("SELECT"):
        return "Error: only SELECT queries are allowed."
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        rows = await conn.fetch(sql)
        await conn.close()
        if not rows:
            return "Query returned no rows."
        headers = list(rows[0].keys())
        lines = [" | ".join(headers)]
        for row in rows[:50]:  # cap at 50 rows
            lines.append(" | ".join(str(v) for v in row.values()))
        return "\n".join(lines)
    except Exception as exc:
        logger.exception("SQL query failed: %s", exc)
        return f"Query error: {exc}"


@tool
async def run_code_tool(code: str, language: str = "python") -> str:
    """Execute Python code in an isolated sandbox and return stdout."""
    async with httpx.AsyncClient(
        base_url=settings.CODE_SANDBOX_URL, timeout=60.0
    ) as client:
        try:
            resp = await client.post(
                "/execute",
                json={"code": code, "language": language},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("stdout", "") + data.get("stderr", "")
        except Exception as exc:
            logger.warning("Code sandbox error: %s", exc)
            return f"Sandbox error: {exc}"
