import asyncio
import logging
import re
import ssl
import time
from typing import Any, Dict, List, Optional
from urllib.parse import unquote
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("prime_gate.search.engine")

# Global in-memory cache for fast search responses: {query_hash: (timestamp, results)}
_SEARCH_CACHE: Dict[str, tuple[float, List[Dict[str, str]]]] = {}
_CACHE_TTL = 3600  # 1 hour cache

# Cloudflare DoH cache for bypass of regional DNS poisoning / ISP blocking
_DOH_CACHE: Dict[str, str] = {}


async def resolve_doh(hostname: str) -> str:
    """Resolve hostname using Cloudflare DNS over HTTPS to bypass local DNS blocks."""
    if hostname in _DOH_CACHE:
        return _DOH_CACHE[hostname]
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(
                "https://1.1.1.1/dns-query",
                params={"name": hostname, "type": "A"},
                headers={"accept": "application/dns-json"}
            )
            for a in r.json().get("Answer", []):
                if a.get("type") == 1:
                    ip = a.get("data")
                    if ip:
                        _DOH_CACHE[hostname] = ip
                        return ip
    except Exception as e:
        logger.debug(f"DoH resolution error for {hostname}: {e}")
    
    # Fallback to known stable DuckDuckGo IP
    return "20.43.161.105" if "duckduckgo" in hostname else hostname


class WebSearchEngine:
    """
    High-performance, zero-API-key search engine with anti-censorship DoH bypass,
    HTML result parsing, and GitHub repository search fallback.
    """

    @classmethod
    async def search(cls, query: str, max_results: int = 6) -> List[Dict[str, str]]:
        q = (query or "").strip()
        if not q:
            return []

        # Check cache
        cache_key = f"{q.lower()}:{max_results}"
        now = time.time()
        if cache_key in _SEARCH_CACHE:
            ts, cached_res = _SEARCH_CACHE[cache_key]
            if now - ts < _CACHE_TTL:
                return cached_res

        # 1. Primary: DuckDuckGo HTML via DoH
        results = await cls._search_duckduckgo_doh(q, max_results)

        # 2. Secondary Fallback: GitHub Search API if repository keywords are present
        if not results or any(kw in q.lower() for kw in ["github", "repo", "repository", "open source"]):
            gh_results = await cls._search_github_api(q, max_results=3)
            # Prepend or merge GitHub results
            existing_urls = {r["url"] for r in results}
            for gr in gh_results:
                if gr["url"] not in existing_urls:
                    results.insert(0, gr)
                    existing_urls.add(gr["url"])
            results = results[:max_results]

        # Cache results if found
        if results:
            _SEARCH_CACHE[cache_key] = (now, results)

        return results

    @classmethod
    async def _search_duckduckgo_doh(cls, query: str, max_results: int) -> List[Dict[str, str]]:
        ip = await resolve_doh("html.duckduckgo.com")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        headers = {
            "Host": "html.duckduckgo.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

        url = f"https://{ip}/html/"
        results: List[Dict[str, str]] = []
        try:
            async with httpx.AsyncClient(verify=ctx, timeout=10.0, follow_redirects=True) as client:
                resp = await client.post(url, data={"q": query}, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"DuckDuckGo returned HTTP {resp.status_code}")
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                for el in soup.find_all("div", class_="result"):
                    h2 = el.find("h2", class_="result__title")
                    if not h2:
                        continue
                    a = h2.find("a", class_="result__a")
                    if not a:
                        continue
                    title = a.text.strip()
                    raw_url = a.get("href", "")
                    if "uddg=" in raw_url:
                        real_url = unquote(raw_url.split("uddg=")[1].split("&")[0])
                    else:
                        real_url = raw_url

                    snip_a = el.find("a", class_="result__snippet")
                    snippet = snip_a.text.strip() if snip_a else ""

                    if real_url and real_url.startswith("http"):
                        results.append({
                            "title": title,
                            "url": real_url,
                            "snippet": snippet
                        })
                    if len(results) >= max_results:
                        break
        except Exception as e:
            logger.warning(f"DuckDuckGo search error: {e}")

        return results

    @classmethod
    async def _search_github_api(cls, query: str, max_results: int = 3) -> List[Dict[str, str]]:
        # Clean query for GitHub keywords
        clean_q = re.sub(r"\b(open source|github|repository|repos|repo|trending|best)\b", "", query, flags=re.I).strip()
        clean_q = re.sub(r"\s+", " ", clean_q)
        if not clean_q:
            clean_q = query

        headers = {
            "User-Agent": "PrimeGate-SearchEngine/1.2",
            "Accept": "application/vnd.github.v3+json"
        }
        url = "https://api.github.com/search/repositories"
        results: List[Dict[str, str]] = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params={"q": clean_q, "per_page": max_results, "sort": "stars"}, headers=headers)
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    for item in items:
                        full_name = item.get("full_name", "")
                        html_url = item.get("html_url", "")
                        desc = item.get("description") or "GitHub open-source repository"
                        stars = item.get("stargazers_count", 0)
                        results.append({
                            "title": f"{full_name} (* {stars:,} stars)",
                            "url": html_url,
                            "snippet": desc
                        })
        except Exception as e:
            logger.debug(f"GitHub search fallback error: {e}")

        return results


async def search_web(query: str, max_results: int = 6) -> List[Dict[str, str]]:
    return await WebSearchEngine.search(query, max_results=max_results)
