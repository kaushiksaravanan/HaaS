#!/usr/bin/env python3
"""
Test SAP AI Core (GenAIHub) Connection
========================================

Tests connection to SAP AI Core and gpt-4o model.
"""

import sys
import os

# Add adk_app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from adk_app.aicore_client import get_aicore_client, test_aicore_connection

load_dotenv()

print("=" * 70)
print("Testing SAP AI Core (GenAIHub) Connection")
print("=" * 70)
print()

# Test 1: Check configuration
print("-" * 70)
print("Test 1: Check AI Core Configuration")
print("-" * 70)
try:
    client = get_aicore_client()
    print(f"Base URL: {client.base_url}")
    print(f"Resource Group: {client.resource_group}")
    print(f"Model: {client.model_name}")
    print(f"Deployment ID: {client.deployment_id or '(auto-detect)'}")
    print(f"Configured: {client.is_configured()}")
    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 2: Get access token
print("-" * 70)
print("Test 2: Get OAuth Access Token")
print("-" * 70)
try:
    client = get_aicore_client()
    token = client._get_access_token()
    print(f"Token obtained: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")
    print(f"Token expiry: {client._token_expiry}")
    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 3: Simple text generation
print("-" * 70)
print("Test 3: Text Generation with gpt-4o")
print("-" * 70)
try:
    client = get_aicore_client()
    response = client.generate_text(
        prompt="Say 'Hello from SAP AI Core!' in one sentence.",
        temperature=0.0,
        max_tokens=50
    )
    print(f"Response: {response}")
    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 4: Chat completion with system prompt
print("-" * 70)
print("Test 4: Chat Completion with System Prompt")
print("-" * 70)
try:
    client = get_aicore_client()
    result = client.chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful SAP HANA expert assistant."},
            {"role": "user", "content": "What is SAP HANA?"}
        ],
        temperature=0.7,
        max_tokens=100
    )
    print(f"Response: {result['content'][:200]}...")
    print(f"Model: {result['model']}")
    print(f"Tokens used: {result['usage']}")
    print("[PASS]")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 5: Full connection test (convenience function)
print("-" * 70)
print("Test 5: Full Connection Test")
print("-" * 70)
try:
    result = test_aicore_connection()
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        print(f"Model: {result['model']}")
        print(f"Response: {result['response']}")
        print("[PASS]")
    else:
        print(f"Error: {result['error']}")
        print("[FAIL]")
except Exception as e:
    print(f"[FAIL] {e}")

print()
print("=" * 70)
print("SAP AI Core Connection Tests Complete!")
print("=" * 70)
