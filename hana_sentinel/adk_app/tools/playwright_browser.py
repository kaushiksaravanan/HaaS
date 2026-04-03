"""
Playwright Browser Automation Tool — Full browser control with visual feedback.
Creates a real browser session with screenshot capture and cursor tracking.
Designed for Manus-style autonomous web browsing with visual feedback.
"""

import asyncio
import base64
import logging
import os
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from urllib.parse import quote_plus
import time

logger = logging.getLogger(__name__)

# Check if playwright is available
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")


@dataclass
class PageElement:
    """Represents a clickable/interactive element on the page."""
    tag: str  # button, a, input, etc.
    text: str  # visible text
    selector: str  # CSS selector or xpath
    element_type: str  # link, button, input, etc.
    href: Optional[str] = None  # for links
    is_target: bool = False  # True if this is the element being acted on

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BrowserAction:
    """Represents a single browser action with page content."""
    action_type: str  # navigate, click, type, scroll, extract, wait
    target: str  # URL, selector, or description
    description: str
    url: str = ""
    page_title: str = ""
    page_text: str = ""  # Visible text on page (truncated)
    elements: List[PageElement] = field(default_factory=list)  # Interactive elements
    target_element: Optional[PageElement] = None  # Element being clicked/typed into
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None
    extracted_text: Optional[str] = None
    screenshot_base64: Optional[str] = None  # Base64-encoded screenshot
    cursor_x: int = 0  # Cursor X position
    cursor_y: int = 0  # Cursor Y position

    def to_dict(self) -> dict:
        d = asdict(self)
        d['elements'] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in (self.elements or [])]
        d['target_element'] = self.target_element.to_dict() if self.target_element else None
        return d


@dataclass
class BrowserSession:
    """Tracks a complete browser session."""
    session_id: str
    query: str
    actions: List[BrowserAction] = field(default_factory=list)
    status: str = "starting"  # starting, browsing, extracting, complete, error
    final_result: Optional[str] = None
    sources: List[Dict[str, str]] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "query": self.query,
            "actions": [a.to_dict() for a in self.actions],
            "status": self.status,
            "final_result": self.final_result,
            "sources": self.sources,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time or time.time()) - self.start_time,
        }


class PlaywrightBrowser:
    """
    Full-featured Playwright browser automation with screenshots and text extraction.
    Captures screenshots, extracts page content, identifies interactive elements, and streams actions.
    """

    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        on_action: Optional[Callable[[BrowserAction], None]] = None,
    ):
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.on_action = on_action  # Callback for streaming actions
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._cursor_x: int = viewport_width // 2  # Cursor tracking
        self._cursor_y: int = viewport_height // 2

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Start the browser using real Chrome with persistent profile."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        self._playwright = await async_playwright().start()

        # Use real Chrome install with a dedicated persistent profile for cookies/sessions
        user_data_dir = os.path.join(os.path.expanduser("~"), ".hana_sentinel_browser")
        os.makedirs(user_data_dir, exist_ok=True)

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=self.headless,
            viewport={"width": self.viewport_width, "height": self.viewport_height},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        self._browser = None  # persistent context doesn't use separate browser object
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        # Hide automation indicators
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        logger.info("Playwright browser started (Chrome persistent profile)")

    async def close(self):
        """Close the browser."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Playwright browser closed")

    async def _capture_screenshot(self) -> Optional[str]:
        """Capture screenshot and return as base64-encoded string."""
        if not self._page:
            return None
        try:
            screenshot_bytes = await self._page.screenshot(
                type="jpeg",
                quality=75,  # Good quality but reasonable size
                full_page=False,  # Just viewport
            )
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            logger.warning(f"Screenshot capture failed: {e}")
            return None

    async def _extract_page_text(self, max_length: int = 2000) -> str:
        """Extract visible text from the page."""
        if not self._page:
            return ""
        try:
            text = await self._page.evaluate("""
                () => {
                    // Clone body to avoid modifying actual page
                    const clone = document.body.cloneNode(true);

                    // Remove unwanted elements
                    ['script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg', 'iframe'].forEach(tag => {
                        clone.querySelectorAll(tag).forEach(el => el.remove());
                    });

                    return clone.innerText.trim();
                }
            """)
            # Truncate and clean
            text = ' '.join(text.split())  # Normalize whitespace
            return text[:max_length] + ('...' if len(text) > max_length else '')
        except Exception as e:
            logger.warning(f"Text extraction failed: {e}")
            return ""

    async def _extract_interactive_elements(self, max_elements: int = 20) -> List[PageElement]:
        """Extract clickable/interactive elements from the page."""
        if not self._page:
            return []
        try:
            elements_data = await self._page.evaluate("""
                (maxElements) => {
                    const elements = [];

                    // Find buttons
                    document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]').forEach((el, i) => {
                        if (elements.length >= maxElements) return;
                        const text = el.innerText || el.value || el.getAttribute('aria-label') || '';
                        if (text.trim()) {
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                text: text.trim().substring(0, 50),
                                selector: `button:nth-of-type(${i + 1})`,
                                element_type: 'button',
                                href: null
                            });
                        }
                    });

                    // Find links
                    document.querySelectorAll('a[href]').forEach((el, i) => {
                        if (elements.length >= maxElements) return;
                        const text = el.innerText || el.getAttribute('aria-label') || '';
                        if (text.trim() && text.length < 100) {
                            elements.push({
                                tag: 'a',
                                text: text.trim().substring(0, 50),
                                selector: `a:nth-of-type(${i + 1})`,
                                element_type: 'link',
                                href: el.href
                            });
                        }
                    });

                    // Find inputs
                    document.querySelectorAll('input[type="text"], input[type="search"], textarea').forEach((el, i) => {
                        if (elements.length >= maxElements) return;
                        const placeholder = el.placeholder || el.getAttribute('aria-label') || '';
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            text: placeholder.substring(0, 50) || 'Input field',
                            selector: `input:nth-of-type(${i + 1})`,
                            element_type: 'input',
                            href: null
                        });
                    });

                    return elements.slice(0, maxElements);
                }
            """, max_elements)

            return [PageElement(**e) for e in elements_data]
        except Exception as e:
            logger.warning(f"Element extraction failed: {e}")
            return []

    async def _emit_action(self, action: BrowserAction):
        """Emit action to callback if set."""
        if self.on_action:
            try:
                self.on_action(action)
            except Exception as e:
                logger.warning(f"Action callback failed: {e}")

    async def _create_action(
        self,
        action_type: str,
        target: str,
        description: str,
        target_element: Optional[PageElement] = None,
        extracted_text: Optional[str] = None,
    ) -> BrowserAction:
        """Create a BrowserAction with current page state and screenshot."""
        page_text = await self._extract_page_text()
        elements = await self._extract_interactive_elements()
        screenshot = await self._capture_screenshot()

        action = BrowserAction(
            action_type=action_type,
            target=target,
            description=description,
            url=self._page.url if self._page else "",
            page_title=await self._page.title() if self._page else "",
            page_text=page_text,
            elements=elements,
            target_element=target_element,
            extracted_text=extracted_text,
            screenshot_base64=screenshot,
            cursor_x=self._cursor_x,
            cursor_y=self._cursor_y,
        )
        await self._emit_action(action)
        return action

    async def navigate(self, url: str) -> BrowserAction:
        """Navigate to a URL."""
        if not self._page:
            raise RuntimeError("Browser not started")

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(0.5)  # Allow page to settle
            action = await self._create_action(
                "navigate",
                url,
                f"Navigating to {url}",
            )
            return action
        except Exception as e:
            action = BrowserAction(
                action_type="navigate",
                target=url,
                description=f"Navigation failed: {url}",
                success=False,
                error=str(e),
            )
            await self._emit_action(action)
            logger.warning(f"Navigation failed: {e}")
            return action

    async def click(self, selector: str, description: str = "") -> BrowserAction:
        """Click an element."""
        if not self._page:
            raise RuntimeError("Browser not started")

        try:
            # Get element info for target_element
            element = await self._page.query_selector(selector)
            target_el = None
            if element:
                text = await element.inner_text() or ""
                target_el = PageElement(
                    tag=await element.evaluate("el => el.tagName.toLowerCase()"),
                    text=text[:50],
                    selector=selector,
                    element_type="button" if "button" in selector.lower() else "link",
                    is_target=True,
                )
                # Update cursor position based on element location
                box = await element.bounding_box()
                if box:
                    self._cursor_x = int(box["x"] + box["width"] / 2)
                    self._cursor_y = int(box["y"] + box["height"] / 2)

            await self._page.click(selector, timeout=10000)
            await asyncio.sleep(0.3)

            action = await self._create_action(
                "click",
                selector,
                description or f"Clicking: {target_el.text if target_el else selector}",
                target_element=target_el,
            )
            return action

        except Exception as e:
            action = BrowserAction(
                action_type="click",
                target=selector,
                description=description or f"Click failed: {selector}",
                success=False,
                error=str(e),
            )
            await self._emit_action(action)
            return action

    async def move_cursor_to(self, selector: str, description: str = "") -> BrowserAction:
        """Move cursor to an element without clicking — shows hover."""
        if not self._page:
            raise RuntimeError("Browser not started")

        try:
            element = await self._page.query_selector(selector)
            if element:
                box = await element.bounding_box()
                if box:
                    self._cursor_x = int(box["x"] + box["width"] / 2)
                    self._cursor_y = int(box["y"] + box["height"] / 2)

            action = await self._create_action(
                "hover",
                selector,
                description or f"Moving cursor to {selector}",
            )
            return action
        except Exception as e:
            action = BrowserAction(
                action_type="hover",
                target=selector,
                description=description or f"Hover failed: {selector}",
                success=False,
                error=str(e),
            )
            await self._emit_action(action)
            return action

    async def type_text(self, selector: str, text: str, description: str = "") -> BrowserAction:
        """Type text into an input."""
        if not self._page:
            raise RuntimeError("Browser not started")

        try:
            element = await self._page.query_selector(selector)
            target_el = None
            if element:
                placeholder = await element.get_attribute("placeholder") or ""
                target_el = PageElement(
                    tag="input",
                    text=placeholder[:50] or "Input field",
                    selector=selector,
                    element_type="input",
                    is_target=True,
                )
                # Update cursor position to the input element (like click does)
                box = await element.bounding_box()
                if box:
                    self._cursor_x = int(box["x"] + box["width"] / 2)
                    self._cursor_y = int(box["y"] + box["height"] / 2)

            await self._page.fill(selector, text)
            await asyncio.sleep(0.2)

            action = await self._create_action(
                "type",
                selector,
                description or f"Typing '{text[:30]}...' into {target_el.text if target_el else selector}",
                target_element=target_el,
            )
            return action

        except Exception as e:
            action = BrowserAction(
                action_type="type",
                target=selector,
                description=description or f"Type failed: {selector}",
                success=False,
                error=str(e),
            )
            await self._emit_action(action)
            return action

    async def press_key(self, key: str, description: str = "") -> BrowserAction:
        """Press a keyboard key."""
        if not self._page:
            raise RuntimeError("Browser not started")

        try:
            await self._page.keyboard.press(key)
            await asyncio.sleep(0.3)
            action = await self._create_action(
                "key",
                key,
                description or f"Pressing {key}",
            )
            return action
        except Exception as e:
            action = BrowserAction(
                action_type="key",
                target=key,
                description=description or f"Key press failed: {key}",
                success=False,
                error=str(e),
            )
            await self._emit_action(action)
            return action

    async def scroll(self, direction: str = "down", amount: int = 500) -> BrowserAction:
        """Scroll the page."""
        if not self._page:
            raise RuntimeError("Browser not started")

        delta = amount if direction == "down" else -amount

        try:
            await self._page.mouse.wheel(0, delta)
            await asyncio.sleep(0.3)
            action = await self._create_action(
                "scroll",
                direction,
                f"Scrolling {direction} by {amount}px",
            )
            return action
        except Exception as e:
            action = BrowserAction(
                action_type="scroll",
                target=direction,
                description=f"Scroll failed: {direction}",
                success=False,
                error=str(e),
            )
            await self._emit_action(action)
            return action

    async def wait(self, seconds: float, description: str = "") -> BrowserAction:
        """Wait for a specified time."""
        await asyncio.sleep(seconds)
        action = await self._create_action(
            "wait",
            str(seconds),
            description or f"Waiting {seconds}s",
        )
        return action

    async def extract_text(self, selector: str = "body") -> BrowserAction:
        """Extract text content from the page."""
        if not self._page:
            raise RuntimeError("Browser not started")

        try:
            # Remove scripts, styles, nav, footer for cleaner extraction
            text = await self._page.evaluate("""
                (selector) => {
                    const element = document.querySelector(selector);
                    if (!element) return '';

                    // Clone to avoid modifying the actual page
                    const clone = element.cloneNode(true);

                    // Remove unwanted elements
                    ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript'].forEach(tag => {
                        clone.querySelectorAll(tag).forEach(el => el.remove());
                    });

                    return clone.innerText.trim().substring(0, 10000);
                }
            """, selector)

            action = await self._create_action(
                "extract",
                selector,
                f"Extracting text from {selector}",
                extracted_text=text,
            )
            return action

        except Exception as e:
            action = await self._create_action(
                "extract",
                selector,
                f"Extract failed: {selector}",
            )
            action.success = False
            action.error = str(e)
            return action

    async def find_and_click_link(self, text_pattern: str) -> BrowserAction:
        """Find and click a link by text content."""
        if not self._page:
            raise RuntimeError("Browser not started")

        try:
            # Find link by text
            link = await self._page.query_selector(f"a:has-text('{text_pattern}')")
            if not link:
                # Try partial match
                links = await self._page.query_selector_all("a")
                for l in links:
                    link_text = await l.inner_text()
                    if text_pattern.lower() in link_text.lower():
                        link = l
                        break

            if link:
                box = await link.bounding_box()
                if box:
                    self._cursor_x = int(box["x"] + box["width"] / 2)
                    self._cursor_y = int(box["y"] + box["height"] / 2)

                action = await self._create_action(
                    "click",
                    f"link:{text_pattern}",
                    f"Clicking link containing '{text_pattern}'",
                )
                await link.click()
                await asyncio.sleep(0.5)
                action.screenshot_base64 = await self._capture_screenshot()
                action.url = self._page.url
                await self._emit_action(action)
                return action
            else:
                action = await self._create_action(
                    "click",
                    f"link:{text_pattern}",
                    f"Link not found: '{text_pattern}'",
                )
                action.success = False
                action.error = "Link not found"
                return action

        except Exception as e:
            action = await self._create_action(
                "click",
                f"link:{text_pattern}",
                f"Click link failed: {text_pattern}",
            )
            action.success = False
            action.error = str(e)
            return action


class WebSearchAgent:
    """
    Autonomous web search agent using Playwright.
    Performs intelligent web searches and extracts relevant information.
    """

    def __init__(
        self,
        on_action: Optional[Callable[[BrowserAction], None]] = None,
        headless: bool = True,
    ):
        self.on_action = on_action
        self.headless = headless
        self.session: Optional[BrowserSession] = None

    async def search_and_extract(
        self,
        query: str,
        session_id: str = None,
        max_pages: int = 3,
    ) -> BrowserSession:
        """
        Perform a web search and extract relevant information.

        Args:
            query: Search query
            session_id: Optional session ID for tracking
            max_pages: Maximum number of result pages to visit

        Returns:
            BrowserSession with all actions and extracted content
        """
        import uuid
        session_id = session_id or str(uuid.uuid4())
        self.session = BrowserSession(session_id=session_id, query=query)

        async with PlaywrightBrowser(
            headless=self.headless,
            on_action=self.on_action,
        ) as browser:
            try:
                # Step 1: Navigate to Bing search
                self.session.status = "browsing"
                search_url = f"https://www.bing.com/search?q={quote_plus(query)}"
                action = await browser.navigate(search_url)
                self.session.actions.append(action)

                await asyncio.sleep(1)

                # Step 2: Extract search results
                action = await browser.extract_text("main")
                self.session.actions.append(action)
                search_results_text = action.extracted_text or ""

                # Step 3: Extract result links from search page
                self.session.status = "extracting"
                visited_urls = set()
                extracted_contents = []

                # SAP domains to prioritize (visit first if found)
                priority_domains = [
                    "help.sap.com", "me.sap.com",
                    "community.sap.com", "support.sap.com",
                ]

                # Parse search result links from Bing
                result_links = await browser._page.evaluate("""
                    () => {
                        const links = [];
                        // Bing: organic result links (li.b_algo h2 a)
                        document.querySelectorAll('li.b_algo h2 a, .b_algo .b_title a, #b_results .b_algo a[href]').forEach(a => {
                            const href = a.href;
                            if (href && href.startsWith('http') && !href.includes('bing.com') && !href.includes('microsoft.com/bing')) {
                                const title = a.innerText?.substring(0, 80) || '';
                                if (title.trim()) links.push({ url: href, title: title.trim() });
                            }
                        });
                        // Broader fallback: any result link on the page
                        if (links.length === 0) {
                            document.querySelectorAll('#b_results a[href]').forEach(a => {
                                const href = a.href;
                                if (href && href.startsWith('http') && !href.includes('bing.com')
                                    && !href.includes('microsoft.com') && !href.includes('javascript:')) {
                                    const title = a.innerText?.substring(0, 80) || '';
                                    if (title.trim() && title.length > 5) links.push({ url: href, title: title.trim() });
                                }
                            });
                        }
                        // Deduplicate by hostname+pathname
                        const seen = new Set();
                        return links.filter(l => {
                            try {
                                const key = new URL(l.url).hostname + new URL(l.url).pathname;
                                if (seen.has(key)) return false;
                                seen.add(key);
                                return true;
                            } catch { return false; }
                        }).slice(0, 10);
                    }
                """)

                # Sort: SAP domains first, then others
                def link_priority(link):
                    for i, domain in enumerate(priority_domains):
                        if domain in link.get("url", ""):
                            return i
                    return len(priority_domains)

                result_links.sort(key=link_priority)

                # Visit top N result links
                for link_info in result_links[:max_pages]:
                    link_url = link_info.get("url", "")
                    link_title = link_info.get("title", "")
                    if link_url in visited_urls:
                        continue
                    try:
                        # Navigate to the result page
                        action = await browser.navigate(link_url)
                        self.session.actions.append(action)

                        if action.success:
                            visited_urls.add(link_url)
                            await asyncio.sleep(1)

                            # Scroll down to load more content
                            scroll_action = await browser.scroll("down", 400)
                            self.session.actions.append(scroll_action)
                            await asyncio.sleep(0.3)

                            # Extract content
                            extract_action = await browser.extract_text("main, article, .content, #content, body")
                            self.session.actions.append(extract_action)

                            if extract_action.extracted_text:
                                extracted_contents.append({
                                    "url": browser._page.url,
                                    "title": link_title or action.page_title,
                                    "content": extract_action.extracted_text[:3000],
                                })
                                self.session.sources.append({
                                    "url": browser._page.url,
                                    "title": link_title or action.page_title,
                                    "status": "ok",
                                })

                            # Go back to search results
                            back_action = await browser.navigate(search_url)
                            self.session.actions.append(back_action)

                    except Exception as e:
                        logger.warning(f"Failed to visit {link_url}: {e}")
                        # Try to get back to search results
                        try:
                            await browser.navigate(search_url)
                        except Exception:
                            pass
                        continue

                # Compile final result
                self.session.status = "complete"
                self.session.end_time = time.time()

                if extracted_contents:
                    self.session.final_result = "\n\n---\n\n".join(
                        f"### {c['title']}\n**URL:** {c['url']}\n\n{c['content']}"
                        for c in extracted_contents
                    )
                else:
                    # Use search results text as fallback
                    self.session.final_result = search_results_text

            except Exception as e:
                self.session.status = "error"
                self.session.final_result = f"Search failed: {str(e)}"
                logger.error(f"Web search failed: {e}")

        return self.session


async def browse_with_playwright(
    query: str,
    on_action: Optional[Callable[[BrowserAction], None]] = None,
    headless: bool = True,
    max_pages: int = 3,
) -> Dict[str, Any]:
    """
    Main entry point for Playwright-based web browsing.

    Args:
        query: Search query or URL
        on_action: Callback for each browser action (for streaming)
        headless: Run browser in headless mode
        max_pages: Maximum pages to visit

    Returns:
        {
            "response": str,  # Extracted and compiled content
            "sources": list,  # List of source URLs
            "actions": list,  # List of all browser actions
            "session": dict,  # Full session data
        }
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "response": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            "sources": [],
            "actions": [],
            "session": None,
            "error": "playwright_not_installed",
        }

    agent = WebSearchAgent(on_action=on_action, headless=headless)
    session = await agent.search_and_extract(query, max_pages=max_pages)

    return {
        "response": session.final_result or "No content extracted",
        "sources": session.sources,
        "actions": [a.to_dict() for a in session.actions],
        "session": session.to_dict(),
    }


def browse_sync(query: str, headless: bool = True, max_pages: int = 3) -> Dict[str, Any]:
    """Synchronous wrapper for browse_with_playwright."""
    return asyncio.run(browse_with_playwright(query, headless=headless, max_pages=max_pages))


# Test function
if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) or "SAP HANA backup best practices"
    print(f"Searching for: {query}")

    result = browse_sync(query, headless=False)
    print(f"\nFound {len(result['sources'])} sources")
    print(f"Actions taken: {len(result['actions'])}")
    print(f"\nContent preview:\n{result['response'][:500]}...")
