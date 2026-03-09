#!/usr/bin/env python3
"""
Test HTTP Command Executor Connection
======================================

Simple test script to verify the HTTP command execution server is working.

Usage:
    python test_http_executor.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_http_executor():
    """Test HTTP command executor connection and basic commands"""

    print("=" * 70)
    print("HTTP Command Executor - Connection Test")
    print("=" * 70)
    print()

    # Check configuration
    url = os.getenv("REMOTE_EXEC_URL", "")
    api_key = os.getenv("REMOTE_EXEC_API_KEY", "")

    print("Configuration Check:")
    print(f"  REMOTE_EXEC_URL: {url if url else '❌ NOT SET'}")
    print(f"  REMOTE_EXEC_API_KEY: {'✓ SET' if api_key else '❌ NOT SET'}")
    print()

    if not url or not api_key:
        print("⚠️  Configuration incomplete!")
        print()
        print("Next steps:")
        print("1. Deploy remote_exec_server.py to vlgdbzo3")
        print("2. Copy the generated API key")
        print("3. Update .env with:")
        print(f"   REMOTE_EXEC_URL={url if url else 'http://10.238.36.146:9999'}")
        print("   REMOTE_EXEC_API_KEY=<your_generated_key>")
        print()
        return False

    # Import HTTP executor
    try:
        from adk_app.tools.http_command_executor import get_http_executor, execute_http_command
        print("✓ HTTP executor module imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import HTTP executor: {e}")
        return False

    print()
    print("-" * 70)
    print("Test 1: Health Check")
    print("-" * 70)

    executor = get_http_executor()

    if not executor.is_configured():
        print("❌ HTTP executor not configured")
        return False

    print("✓ HTTP executor configured")

    # Test health check
    health_result = executor.health_check()
    print(f"Health check result: {health_result.get('status', 'unknown')}")

    if health_result.get('status') == 'success':
        print("✓ Server is healthy!")
        data = health_result.get('data', {})
        print(f"  Hostname: {data.get('hostname', 'unknown')}")
        print(f"  User: {data.get('user', 'unknown')}")
        print(f"  Timestamp: {data.get('timestamp', 'unknown')}")
    elif health_result.get('status') == 'error':
        error = health_result.get('error', 'unknown')
        print(f"❌ Health check failed: {error}")
        if "Connection refused" in error:
            print()
            print("⚠️  Is remote_exec_server.py running on vlgdbzo3?")
            print("   Start it with: python3 remote_exec_server.py")
        elif "Authentication failed" in error or "403" in error:
            print()
            print("⚠️  API key mismatch!")
            print("   Verify the API key in .env matches the server config")
        return False

    print()
    print("-" * 70)
    print("Test 2: Execute Simple Command")
    print("-" * 70)

    # Test simple command
    result = execute_http_command("echo 'Hello from HTTP executor'")
    print(f"Command: echo 'Hello from HTTP executor'")
    print(f"Status: {result.get('status', 'unknown')}")
    print(f"Exit code: {result.get('exit_code', -1)}")
    print(f"Output: {result.get('output', '(empty)')}")

    if result.get('exit_code') == 0:
        print("✓ Command executed successfully!")
    else:
        print(f"❌ Command failed: {result.get('error', 'unknown')}")
        return False

    print()
    print("-" * 70)
    print("Test 3: Execute System Command")
    print("-" * 70)

    # Test system command
    result = execute_http_command("whoami")
    print(f"Command: whoami")
    print(f"Output: {result.get('output', '(empty)')}")

    if result.get('exit_code') == 0:
        print("✓ System command executed successfully!")
    else:
        print(f"❌ Command failed: {result.get('error', 'unknown')}")

    print()
    print("-" * 70)
    print("Test 4: Execute as HANA User")
    print("-" * 70)

    # Test execute as zo3adm user
    result = executor.execute_as_user("whoami", user="zo3adm")
    print(f"Command: whoami (as zo3adm)")
    print(f"Output: {result.get('output', '(empty)')}")

    if result.get('exit_code') == 0 and 'zo3adm' in result.get('output', ''):
        print("✓ Executed as zo3adm user successfully!")
    else:
        print(f"⚠️  Note: {result.get('error', 'May need sudo permissions')}")

    print()
    print("-" * 70)
    print("Test 5: Test SAP Command (Optional)")
    print("-" * 70)

    # Test SAP command if available
    result = executor.execute_as_user("HDB version", user="zo3adm")
    print(f"Command: HDB version (as zo3adm)")

    if result.get('exit_code') == 0:
        print(f"Output: {result.get('output', '(empty)')[:200]}...")
        print("✓ HANA command executed successfully!")
    else:
        print(f"⚠️  HANA command not available or failed: {result.get('error', 'unknown')}")
        print("   (This is OK if HANA environment not set up yet)")

    print()
    print("=" * 70)
    print("✓ HTTP Command Executor is working!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Start HANA Sentinel API: python main.py api")
    print("2. Test instance diagnostics: curl -X POST http://localhost:8000/api/v1/instance/diagnostics")
    print("3. Check API logs for 'Command executed via HTTP API'")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_http_executor()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
