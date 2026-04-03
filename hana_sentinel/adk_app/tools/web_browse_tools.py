"""
Web Browse Tools — Fetch and parse web pages for knowledge questions.
Used by the chat agent to answer knowledge questions by browsing the web.
Supports SAP documentation and multiple FREE search engines:
  - DuckDuckGo (default, no API key needed)
  - SearXNG (open source metasearch, public instances)
  - Brave Search (free tier with API key)
  - Google Custom Search (requires API key)
"""

import os
import re
import json
import random
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse, quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Domains the browse agent is allowed to visit (can be expanded via env var)
_DEFAULT_ALLOWED_DOMAINS = [
    "support.sap.com", "me.sap.com", "launchpad.support.sap.com", "help.sap.com",
    "community.sap.com",
    "stackoverflow.com", "github.com", "docs.python.org", "developer.mozilla.org",
    "wikipedia.org", "medium.com", "dev.to", "techcommunity.microsoft.com",
]
_ALLOWED_DOMAINS = [
    d.strip()
    for d in os.getenv(
        "BROWSER_ALLOWED_DOMAINS",
        ",".join(_DEFAULT_ALLOWED_DOMAINS),
    ).split(",")
    if d.strip()
]

# Search API keys (all optional - system will use free alternatives)
_GOOGLE_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
_GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
_BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")  # Free tier: 2000 queries/month

# Public SearXNG instances (free, no API key needed)
_SEARXNG_INSTANCES = [
    "https://searx.be",
    "https://search.bus-hit.me",
    "https://searx.tiekoetter.com",
    "https://search.sapti.me",
    "https://searx.org",
]

_REQUEST_TIMEOUT = 15  # seconds
_MAX_CONTENT_LENGTH = 6000  # chars per page to keep LLM context manageable

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _is_domain_allowed(url: str, allow_all: bool = False) -> bool:
    """Check if a URL belongs to an allowed domain."""
    if allow_all:
        return True
    try:
        hostname = urlparse(url).hostname or ""
        return any(hostname.endswith(d) for d in _ALLOWED_DOMAINS)
    except Exception:
        return False


def _build_search_urls(query: str) -> List[str]:
    """Build search URLs for SAP support sites."""
    encoded = quote_plus(query)
    return [
        f"https://search.sap.com/search.html?q={encoded}&src=defaultSourceGroup",
        f"https://me.sap.com/notes/search?q={encoded}",
    ]


def _fetch_with_profile(url: str) -> Optional[Dict]:
    """Try fetching a page using browser-use with the user's Chrome profile.

    This carries all cookies/sessions so SAP Community etc. won't 403.
    Returns None if browser-use is unavailable or fails.
    """
    try:
        import asyncio
        from browser_use import BrowserSession
        from ..agents.browser_agent import _chrome_profile

        async def _do_fetch():
            session = BrowserSession(browser_profile=_chrome_profile())
            await session.start()
            try:
                page = await session.get_current_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                html = await page.content()
                return html
            finally:
                await session.stop()

        loop = asyncio.new_event_loop()
        html = loop.run_until_complete(_do_fetch())
        loop.close()

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        main = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.body
        text = main.get_text(separator="\n", strip=True) if main else ""
        if len(text) > _MAX_CONTENT_LENGTH:
            text = text[:_MAX_CONTENT_LENGTH] + "\n[... truncated]"

        if text.strip():
            return {"url": url, "title": title, "content": text, "status": "ok"}
        return None
    except Exception as exc:
        logger.debug(f"browser-use profile fetch failed for {url}: {exc}")
        return None


def fetch_page(url: str, allow_all_domains: bool = False) -> Dict:
    """Fetch a single page and extract its text content.

    Tries browser-use with the user's Chrome profile first (carries SAP cookies),
    falls back to plain requests.

    Args:
        url: The URL to fetch
        allow_all_domains: If True, bypass domain restrictions

    Returns:
        {url, title, content, status}
    """
    if not _is_domain_allowed(url, allow_all=allow_all_domains):
        return {"url": url, "title": "", "content": "", "status": "blocked_domain"}

    # Try Playwright with user's Chrome profile (has SAP session cookies)
    result = _fetch_with_profile(url)
    if result:
        return result

    # Fallback to plain requests
    try:
        resp = requests.get(
            url,
            timeout=_REQUEST_TIMEOUT,
            headers={
                "User-Agent": _BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        # Prefer main content areas
        main = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.body
        text = main.get_text(separator="\n", strip=True) if main else ""

        # Truncate long pages
        if len(text) > _MAX_CONTENT_LENGTH:
            text = text[:_MAX_CONTENT_LENGTH] + "\n[... truncated]"

        return {"url": url, "title": title, "content": text, "status": "ok"}

    except requests.RequestException as exc:
        logger.warning(f"Failed to fetch {url}: {exc}")
        return {"url": url, "title": "", "content": "", "status": f"error: {exc}"}


def search_sap_docs(query: str, max_results: int = 3) -> List[Dict]:
    """Search SAP documentation sites for a query.

    Returns a list of {url, title, snippet} dicts for the top results.
    """
    results: List[Dict] = []
    search_urls = _build_search_urls(query)

    for search_url in search_urls:
        try:
            resp = requests.get(
                search_url,
                timeout=_REQUEST_TIMEOUT,
                headers={
                    "User-Agent": _BROWSER_UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            # Try to find result links — SAP search pages use various selectors
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if not href or not text or len(text) < 10:
                    continue
                if _is_domain_allowed(href) and href not in [r["url"] for r in results]:
                    results.append({"url": href, "title": text, "snippet": ""})
                    if len(results) >= max_results:
                        break

            if len(results) >= max_results:
                break
        except Exception as exc:
            logger.warning(f"Search failed for {search_url}: {exc}")
            continue

    return results


def search_searxng(query: str, max_results: int = 5) -> List[Dict]:
    """Search using SearXNG public instances (FREE, no API key needed).

    SearXNG is an open-source metasearch engine that aggregates results from
    multiple search engines (Google, Bing, DuckDuckGo, etc.)
    """
    results: List[Dict] = []

    # Try multiple instances in random order
    instances = _SEARXNG_INSTANCES.copy()
    random.shuffle(instances)

    for instance in instances[:3]:  # Try up to 3 instances
        try:
            resp = requests.get(
                f"{instance}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "general",
                },
                timeout=_REQUEST_TIMEOUT,
                headers={"User-Agent": _BROWSER_UA},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", [])[:max_results]:
                    results.append({
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "snippet": item.get("content", "")[:300],
                        "source": "searxng",
                    })
                if results:
                    logger.info(f"SearXNG ({instance}) returned {len(results)} results")
                    return results
        except Exception as exc:
            logger.debug(f"SearXNG {instance} failed: {exc}")
            continue

    return results


def search_brave(query: str, max_results: int = 5) -> List[Dict]:
    """Search using Brave Search API (FREE tier: 2000 queries/month).

    Get your free API key at: https://brave.com/search/api/
    """
    results: List[Dict] = []

    if not _BRAVE_API_KEY:
        return results

    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": _BRAVE_API_KEY,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("web", {}).get("results", [])[:max_results]:
                results.append({
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("description", "")[:300],
                    "source": "brave",
                })
            if results:
                logger.info(f"Brave Search returned {len(results)} results")
    except Exception as exc:
        logger.warning(f"Brave Search failed: {exc}")

    return results


def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict]:
    """Search using DuckDuckGo (FREE, no API key needed).

    Uses DuckDuckGo Instant Answer API + HTML scraping as fallback.
    """
    results: List[Dict] = []

    # Try DuckDuckGo Instant Answer API first
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": _BROWSER_UA},
        )
        if resp.status_code == 200:
            data = resp.json()

            # Get abstract/definition
            abstract = data.get("Abstract", "")
            abstract_url = data.get("AbstractURL", "")
            if abstract and abstract_url:
                results.append({
                    "url": abstract_url,
                    "title": data.get("Heading", "DuckDuckGo Result"),
                    "snippet": abstract[:500],
                    "source": "duckduckgo",
                })

            # Get related topics
            for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                if isinstance(topic, dict) and topic.get("FirstURL"):
                    results.append({
                        "url": topic.get("FirstURL", ""),
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", ""),
                        "source": "duckduckgo",
                    })

            if results:
                logger.info(f"DuckDuckGo API returned {len(results)} results")
                return results
    except Exception as exc:
        logger.warning(f"DuckDuckGo API failed: {exc}")

    # Fallback to scraping DuckDuckGo HTML results
    try:
        encoded = quote_plus(query)
        resp = requests.get(
            f"https://html.duckduckgo.com/html/?q={encoded}",
            timeout=_REQUEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for result in soup.select(".result__a")[:max_results]:
                href = result.get("href", "")
                title = result.get_text(strip=True)
                if href and title:
                    # DuckDuckGo URLs are redirects, extract actual URL
                    if "uddg=" in href:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = parsed.get("uddg", [href])[0]
                    results.append({
                        "url": href,
                        "title": title,
                        "snippet": "",
                        "source": "duckduckgo_html",
                    })
            if results:
                logger.info(f"DuckDuckGo HTML returned {len(results)} results")
    except Exception as exc:
        logger.warning(f"DuckDuckGo HTML failed: {exc}")

    return results


def search_google(query: str, max_results: int = 5) -> List[Dict]:
    """Search using Google Custom Search API (requires API key).

    Get your API key at: https://developers.google.com/custom-search/v1/overview
    """
    results: List[Dict] = []

    if not (_GOOGLE_API_KEY and _GOOGLE_CSE_ID):
        return results

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": _GOOGLE_API_KEY,
                "cx": _GOOGLE_CSE_ID,
                "q": query,
                "num": max_results,
            },
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", [])[:max_results]:
                results.append({
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "google",
                })
            if results:
                logger.info(f"Google Search returned {len(results)} results")
    except Exception as exc:
        logger.warning(f"Google Search failed: {exc}")

    return results


def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Search the web using multiple FREE search engines.

    Priority order:
    1. SearXNG (free, no API key, metasearch)
    2. DuckDuckGo (free, no API key)
    3. Brave Search (free tier with API key)
    4. Google Custom Search (requires API key)

    Returns results from the first engine that works.
    """
    results: List[Dict] = []

    # 1. Try SearXNG first (free metasearch, no API key)
    results = search_searxng(query, max_results)
    if results:
        return results

    # 2. Try DuckDuckGo (free, no API key)
    results = search_duckduckgo(query, max_results)
    if results:
        return results

    # 3. Try Brave Search (if API key configured)
    if _BRAVE_API_KEY:
        results = search_brave(query, max_results)
        if results:
            return results

    # 4. Try Google (if API key configured)
    if _GOOGLE_API_KEY and _GOOGLE_CSE_ID:
        results = search_google(query, max_results)
        if results:
            return results

    logger.warning(f"All search engines failed for query: {query[:50]}...")
    return results


def browse_for_answer(question: str, use_web_search: bool = True) -> Dict:
    """Main entry point: browse web to answer a knowledge question.

    Uses multiple FREE search engines (SearXNG, DuckDuckGo, Brave).
    No API keys required for basic functionality.

    Args:
        question: The question to answer
        use_web_search: If True, search the web (not just SAP docs)

    Returns:
        {
            "answer_context": str,  # concatenated page content for LLM
            "sources": [            # pages that were browsed
                {"url": str, "title": str, "status": str}
            ]
        }
    """
    sources = []
    page_contents = []

    # Step 1: Search SAP docs first
    search_results = search_sap_docs(question, max_results=3)

    # Step 2: Also search web using FREE engines if enabled
    if use_web_search:
        web_results = search_web(question, max_results=5)
        # Add unique results
        existing_urls = {r["url"] for r in search_results}
        for wr in web_results:
            if wr["url"] not in existing_urls:
                search_results.append(wr)
                existing_urls.add(wr["url"])

    # Step 3: Fetch each result page
    for sr in search_results[:6]:  # Limit total pages to fetch
        page = fetch_page(sr["url"], allow_all_domains=use_web_search)
        sources.append({
            "url": page["url"],
            "title": page.get("title") or sr.get("title", ""),
            "status": page["status"],
            "source": sr.get("source", "sap"),
        })
        if page["content"]:
            page_contents.append(
                f"=== Source: {page['title']} ({page['url']}) ===\n{page['content']}"
            )

    # If no search results, try direct SAP note/help URLs as fallback
    if not page_contents:
        fallback_urls = [
            f"https://help.sap.com/docs/search?q={quote_plus(question)}&product=SAP_HANA_PLATFORM",
        ]
        for url in fallback_urls:
            page = fetch_page(url, allow_all_domains=True)
            if page["content"]:
                sources.append({
                    "url": page["url"],
                    "title": page.get("title", "SAP Help"),
                    "status": page["status"],
                })
                page_contents.append(
                    f"=== Source: {page['title']} ({page['url']}) ===\n{page['content']}"
                )

    answer_context = "\n\n".join(page_contents) if page_contents else ""
    return {"answer_context": answer_context, "sources": sources}
