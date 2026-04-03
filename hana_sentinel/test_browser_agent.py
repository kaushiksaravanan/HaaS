"""
Test browser-use agent with GenAI Hub proxy (Claude) - headful mode.
Run: python test_browser_agent.py
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from adk_app.agents.browser_agent import BrowserUseAgent

    query = (
        "SAP HANA system freeze/hung/unresponsive on daily basis in same time\n"
        "browse the web"
    )

    logger.info("Creating BrowserUseAgent (headful)...")
    agent = BrowserUseAgent(headless=False)

    logger.info("Running query: %s", query[:80])
    result = await agent.navigate_and_extract(task=query, timeout=180)

    print("\n" + "=" * 60)
    print("RESULT LENGTH:", len(result))
    print("=" * 60)
    print(result[:2000])
    print("=" * 60)

    if result and not result.startswith("Browser task failed"):
        print("\n✅ SUCCESS")
        return 0
    else:
        print("\n❌ FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
