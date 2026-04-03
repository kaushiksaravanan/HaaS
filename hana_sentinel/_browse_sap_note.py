"""Browse SAP Note 0003439888 using headful Chrome with the user's real profile."""
import asyncio
import os
import sys
import subprocess
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))


def _ensure_chrome_debug_mode(port: int = 9222) -> None:
    """Relaunch Chrome with --remote-debugging-port if not already running."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        sock.connect(("127.0.0.1", port))
        sock.close()
        print(f"Chrome already listening on debug port {port}")
        return
    except (ConnectionRefusedError, OSError):
        pass

    # Find Chrome executable
    chrome_paths = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    chrome_exe = next((p for p in chrome_paths if os.path.isfile(p)), None)
    if not chrome_exe:
        raise RuntimeError("Chrome not found. Please launch Chrome manually with --remote-debugging-port=9222")

    chrome_profile = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "Google", "Chrome", "User Data",
    )

    print(f"Launching Chrome with remote debugging on port {port}...")
    print(f"  Chrome: {chrome_exe}")
    print(f"  Profile: {chrome_profile}")

    subprocess.Popen(
        [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={chrome_profile}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for Chrome to start listening
    for _ in range(30):
        time.sleep(1)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            print(f"Chrome is ready on port {port}")
            return
        except (ConnectionRefusedError, OSError):
            continue
    raise RuntimeError("Chrome failed to start with remote debugging")


async def main():
    from browser_use import Agent as BrowserAgent, BrowserProfile
    from adk_app.chat_genaihub import ChatGenAIHub

    DEBUG_PORT = 9222

    # Ensure Chrome is running with debug port
    _ensure_chrome_debug_mode(DEBUG_PORT)

    # Connect to existing Chrome via CDP
    profile = BrowserProfile(
        cdp_url=f"http://127.0.0.1:{DEBUG_PORT}",
        headless=False,
        keep_alive=True,
    )

    llm = ChatGenAIHub()

    task = (
        "Navigate to https://me.sap.com/notes/0003439888 . "
        "Wait for the page to fully load. If there is an authentication/login page, "
        "the cookies and session from the Chrome profile should handle SSO automatically — wait for it. "
        "Once the SAP Note page loads, extract: "
        "1) The SAP Note title, "
        "2) The note number, "
        "3) The description/symptom section, "
        "4) The solution/correction section, "
        "5) Any relevant component or version info. "
        "Return all extracted text."
    )

    agent = BrowserAgent(task=task, llm=llm, browser_profile=profile)
    print("Starting browser agent...")
    result = await agent.run()

    final = result.final_result() if hasattr(result, 'final_result') else str(result)
    print("\n" + "=" * 80)
    print("RESULT:")
    print("=" * 80)
    print(final)
    return final

if __name__ == "__main__":
    asyncio.run(main())
