"""
Browser-Use Agent for SAP Web Interface Automation.
Uses SAP AI Core (GenAI Hub proxy) with Claude as the LLM backend.
browser-use is used out of the box — headful, no monkey-patches.
"""

from browser_use import Agent as BrowserUseLibAgent, Controller, BrowserProfile
from browser_use.llm.anthropic.chat import ChatAnthropic
import asyncio
import logging
import os
import shutil
import tempfile
import time as _time
from typing import Optional

logger = logging.getLogger(__name__)


def _safe_copy_chrome_profile() -> Optional[str]:
    """Copy Chrome user-data dir to a temp location to avoid lock conflicts with an open Chrome."""
    if os.name == "nt":
        default_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")
    else:
        default_dir = os.path.expanduser("~/.config/google-chrome")
    chrome_dir = os.getenv("CHROME_USER_DATA_DIR", default_dir)
    if not os.path.isdir(chrome_dir):
        return None
    tmp = os.path.join(tempfile.gettempdir(), "hana_sentinel_chrome_profile")
    if os.path.exists(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        shutil.copytree(
            chrome_dir, tmp, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie",
                "*.ldb", "LOCK",
            ),
        )
    except Exception as exc:
        logger.warning("Failed to copy Chrome profile: %s", exc)
        return None
    return tmp

# Default timeout for browser tasks (seconds)
BROWSER_TASK_TIMEOUT = 180

# Increase browser-use internal watchdog timeout for browser launch (default 30s
# is too short on Windows where Chrome startup can be slow)
os.environ.setdefault("TIMEOUT_BrowserStartEvent", "90")
os.environ.setdefault("TIMEOUT_BrowserLaunchEvent", "90")


def _get_aicore_llm() -> ChatAnthropic:
    """Build a browser-use ChatAnthropic instance pointed at the GenAI Hub local proxy.

    The proxy at localhost:6655 serves Anthropic API at /anthropic/ path.
    """
    proxy_url = os.getenv("GENAIHUB_PROXY_URL", "http://localhost:6655")
    proxy_key = os.getenv("GENAIHUB_PROXY_API_KEY", "d3d25b98-d27a-4d9c-8f95-5d39731e3a3a")
    model_name = os.getenv("BROWSER_LLM_MODEL", "anthropic--claude-4.6-sonnet")

    logger.info("[browser] Using GenAI Hub proxy at %s with model %s", proxy_url, model_name)

    return ChatAnthropic(
        model=model_name,
        api_key=proxy_key,
        base_url=f"{proxy_url}/anthropic",
    )


class BrowserUseAgent:
    """Browser automation agent using SAP AI Core as the LLM backend."""

    def __init__(self, headless: bool = False):
        self.name = "BrowserUseAgent"
        self.description = "Automates interaction with SAP web interfaces."
        self.headless = headless
        self.controller = Controller()

    async def navigate_and_extract(
        self, task: str, timeout: int = BROWSER_TASK_TIMEOUT,
        step_callback=None,
    ) -> str:
        """
        Uses browser-use to perform a task with a timeout.

        Args:
            task: Description of the browser task to perform
            timeout: Maximum seconds to wait for the browser task
            step_callback: Optional async/sync callback(browser_state, agent_output, step_num)

        Returns:
            Result text from the browser automation
        """
        t0 = _time.monotonic()
        agent: Optional[BrowserUseLibAgent] = None

        try:
            logger.info("[browser] Creating agent (headless=%s)...", self.headless)
            llm = _get_aicore_llm()

            # Prepend cookie-accept instruction so the agent handles consent banners automatically
            full_task = (
                "IMPORTANT: If you encounter any cookie consent banner, privacy popup, or "
                "accept/agree button on any page, ALWAYS click Accept/Agree/OK immediately "
                "before doing anything else.\n\n"
                + task
            )

            browser_profile = BrowserProfile(
                headless=self.headless,
                disable_security=False,
            )

            agent = BrowserUseLibAgent(
                task=full_task,
                llm=llm,
                controller=self.controller,
                browser_profile=browser_profile,
                max_steps=8,
                register_new_step_callback=step_callback,
            )

            logger.info("[browser] Starting agent.run() with %ds timeout...", timeout)
            history = await asyncio.wait_for(agent.run(), timeout=timeout)

            result = history.final_result()
            logger.info("[browser] Done (%.1fs), result length: %d", _time.monotonic() - t0, len(result or ""))
            return result if result else "Task completed but no text returned."
        except asyncio.TimeoutError:
            logger.error("[browser] Task timed out after %ds — extracting partial results", timeout)
            return self._extract_partial_results(agent, timeout)
        except asyncio.CancelledError:
            logger.warning("[browser] Task was cancelled — extracting partial results")
            return self._extract_partial_results(agent, timeout, reason="cancelled")
        except Exception as e:
            logger.error("[browser] Task failed: %s", e, exc_info=True)
            partial = self._extract_partial_results(agent, timeout, reason=f"error: {e}")
            if partial and not partial.startswith("[Browser"):
                return partial
            return f"Browser task failed: {e}"
        finally:
            if agent is not None:
                try:
                    if hasattr(agent, 'browser') and agent.browser:
                        await asyncio.wait_for(agent.browser.close(), timeout=10)
                except Exception as close_err:
                    logger.warning("[browser] Browser close failed: %s", close_err)

    def run_task(self, task_description: str) -> str:
        """
        Synchronous wrapper for async browser task.

        Args:
            task_description: Description of the browser task

        Returns:
            Result from the browser automation
        """
        return asyncio.run(self.navigate_and_extract(task_description))

    @staticmethod
    def _extract_partial_results(
        agent: Optional[BrowserUseLibAgent],
        timeout: int,
        reason: str = "timed out",
    ) -> str:
        """Extract whatever the agent has gathered so far from its history.

        Even when a timeout / cancel / error interrupts ``agent.run()``, the
        ``agent.history`` object still contains every step that completed before
        the interruption.  We harvest URLs visited, extracted page content and
        model thoughts so the caller can build a useful (partial) answer.
        """
        if agent is None or not hasattr(agent, "history") or not agent.history.history:
            return f"[Browser {reason} after {timeout}s with no results collected.]"

        history = agent.history

        # Collect all content fragments the agent managed to extract
        extracted = history.extracted_content() or []
        urls = [u for u in (history.urls() or []) if u]
        thoughts = []
        try:
            for brain in history.model_thoughts():
                if hasattr(brain, "evaluation_previous_goal") and brain.evaluation_previous_goal:
                    thoughts.append(brain.evaluation_previous_goal)
                if hasattr(brain, "memory") and brain.memory:
                    thoughts.append(brain.memory)
        except Exception:
            pass

        steps_done = len(history.history)

        # De-duplicate
        seen_urls = list(dict.fromkeys(urls))
        seen_content = list(dict.fromkeys(extracted))

        parts: list[str] = []
        parts.append(
            f"**Note:** The browser agent {reason} after {timeout}s "
            f"({steps_done} step{'s' if steps_done != 1 else ''} completed).  "
            "The information below is based on what was gathered before interruption.\n"
        )

        if seen_content:
            parts.append("### Gathered Content\n")
            for fragment in seen_content:
                parts.append(fragment.strip())

        if thoughts:
            parts.append("\n### Agent Observations\n")
            for t in thoughts:
                parts.append(f"- {t}")

        if seen_urls:
            parts.append("\n### Pages Visited\n")
            for u in seen_urls:
                parts.append(f"- {u}")

        result = "\n".join(parts)
        logger.info(
            "[browser] Partial results extracted: %d content fragments, %d URLs, %d thoughts",
            len(seen_content), len(seen_urls), len(thoughts),
        )
        return result
