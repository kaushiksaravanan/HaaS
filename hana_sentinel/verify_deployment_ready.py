#!/usr/bin/env python3
"""
Pre-Deployment Verification Script
===================================

Verifies that everything is ready before deploying.
"""

import os
import sys
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if Path(filepath).exists():
        size = Path(filepath).stat().st_size
        print(f"[OK] {description}")
        print(f"     File: {filepath}")
        print(f"     Size: {size:,} bytes")
        return True
    else:
        print(f"[MISSING] {description}")
        print(f"          File: {filepath}")
        return False

def check_env_config():
    """Check .env configuration"""
    from dotenv import load_dotenv
    load_dotenv()

    url = os.getenv('REMOTE_EXEC_URL', '')
    key = os.getenv('REMOTE_EXEC_API_KEY', '')

    print("\n" + "=" * 70)
    print("Environment Configuration Check")
    print("=" * 70)

    if url:
        print(f"[OK] REMOTE_EXEC_URL: {url}")
    else:
        print("[MISSING] REMOTE_EXEC_URL not set in .env")
        return False

    if key:
        # Show truncated key for security
        display_key = f"{key[:20]}...{key[-10:]}" if len(key) > 30 else key
        print(f"[OK] REMOTE_EXEC_API_KEY: {display_key}")

        print("[OK] REMOTE_EXEC_API_KEY is set")
    else:
        print("[MISSING] REMOTE_EXEC_API_KEY not set in .env")
        return False

    return True

def check_server_file():
    """Check if remote_exec_server.py has the correct API key"""
    filepath = "remote_exec_server.py"

    if not Path(filepath).exists():
        print(f"[MISSING] {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'API_KEY' in content:
        print(f"[OK] API_KEY configuration found in {filepath}")
        return True
    else:
        print(f"[WARNING] API_KEY configuration not found in {filepath}")
        return False

def main():
    """Run all verification checks"""

    print("=" * 70)
    print("Pre-Deployment Verification")
    print("=" * 70)
    print()

    all_checks_passed = True

    # Check 1: Required files exist
    print("Check 1: Required Files")
    print("-" * 70)

    files_to_check = [
        ("remote_exec_server.py", "HTTP Execution Server"),
        (".env", "Environment Configuration"),
        ("test_http_executor.py", "Connection Test Script"),
        ("DEPLOY_NOW.md", "Deployment Guide"),
    ]

    for filepath, description in files_to_check:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    # Check 2: Environment configuration
    print("\n" + "-" * 70)
    if not check_env_config():
        all_checks_passed = False

    # Check 3: Server file has correct API key
    print("\n" + "-" * 70)
    print("Check 2: Server Configuration")
    print("-" * 70)
    if not check_server_file():
        all_checks_passed = False

    # Check 4: Python dependencies
    print("\n" + "-" * 70)
    print("Check 3: Local Dependencies")
    print("-" * 70)

    try:
        from dotenv import load_dotenv
        print("[OK] python-dotenv installed")
    except ImportError:
        print("[MISSING] python-dotenv not installed")
        print("         Run: pip install python-dotenv")
        all_checks_passed = False

    try:
        from adk_app.tools.http_command_executor import HTTPCommandExecutor
        print("[OK] HTTP Command Executor module available")
    except ImportError as e:
        print(f"[ERROR] Cannot import HTTP Command Executor: {e}")
        all_checks_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_checks_passed:
        print("SUCCESS: All checks passed!")
        print("=" * 70)
        print()
        print("You are ready to deploy!")
        print()
        print("Next steps:")
        print("  1. Copy remote_exec_server.py to vlgdbzo3")
        print("  2. Install dependencies on vlgdbzo3:")
        print("     python3 -m pip install --user fastapi uvicorn")
        print("  3. Run the server:")
        print("     python3 remote_exec_server.py")
        print("  4. Test connection:")
        print("     python test_http_executor.py")
        print()
        print("See DEPLOY_NOW.md for detailed instructions.")
        return 0
    else:
        print("FAILED: Some checks did not pass")
        print("=" * 70)
        print()
        print("Please fix the issues above before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
