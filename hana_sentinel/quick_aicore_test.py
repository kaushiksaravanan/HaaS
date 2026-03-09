#!/usr/bin/env python3
"""Quick test with logging enabled"""
import sys
import os
import logging

# Enable debug logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
from adk_app.aicore_client import get_aicore_client

load_dotenv()

print("Testing gpt-4o deployment...")
client = get_aicore_client()
print(f"Endpoint will be: {client.base_url}/inference/deployments/{client.deployment_id}/chat/completions")
print()

try:
    response = client.generate_text(
        prompt="Say hello",
        temperature=0.0,
        max_tokens=50
    )
    print(f"SUCCESS: {response}")
except Exception as e:
    print(f"FAILED: {e}")
