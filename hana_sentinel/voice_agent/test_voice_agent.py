"""
Test suite for the HANA Sentinel voice agent.
Tests the custom LLM adapter, markdown stripping, and integration.
"""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_agent.agent import (
    SentinelLLM,
    SentinelLLMStream,
    _call_sentinel_chat,
    _strip_markdown_for_speech,
    SENTINEL_API_URL,
)
from livekit.agents.llm import ChatContext, ChatChunk, ChatMessage


def _run(coro):
    """Helper to run an async coroutine in tests."""
    return asyncio.run(coro)


class TestMarkdownStripping(unittest.TestCase):
    """Test that markdown is properly cleaned for TTS."""

    def test_code_blocks_removed(self):
        text = "Here is the output:\n```\nroot      1234  0.0  0.1\n```\nDone."
        result = _strip_markdown_for_speech(text)
        self.assertNotIn("```", result)
        self.assertNotIn("root", result)  # code block content should be gone

    def test_inline_code_cleaned(self):
        text = "Run `df -h` to check disk."
        result = _strip_markdown_for_speech(text)
        self.assertNotIn("`", result)
        self.assertIn("df -h", result)

    def test_bold_italic_removed(self):
        text = "**Status:** *OK* and running"
        result = _strip_markdown_for_speech(text)
        self.assertNotIn("**", result)
        self.assertNotIn("*", result)
        self.assertIn("Status:", result)
        self.assertIn("OK", result)

    def test_headers_removed(self):
        text = "### System Health\nAll good."
        result = _strip_markdown_for_speech(text)
        self.assertNotIn("###", result)
        self.assertIn("System Health", result)

    def test_newlines_collapsed(self):
        text = "Line one.\n\n\nLine two.\nLine three."
        result = _strip_markdown_for_speech(text)
        # Should not have multiple spaces or newlines
        self.assertNotIn("\n", result)

    def test_empty_string(self):
        self.assertEqual(_strip_markdown_for_speech(""), "")

    def test_complex_output(self):
        text = (
            "**Command:** `uptime`\n\n"
            "**Output:**\n```\n 14:32:01 up 45 days, 3:21, 2 users, "
            "load average: 0.15, 0.10, 0.08\n```"
        )
        result = _strip_markdown_for_speech(text)
        self.assertNotIn("```", result)
        self.assertNotIn("**", result)
        # "Command:" label is stripped by _strip_markdown_for_speech
        self.assertIn("uptime", result)


class TestSentinelChatCaller(unittest.TestCase):
    """Test the HTTP call to Sentinel API."""

    @patch("voice_agent.agent.requests.post")
    def test_successful_call(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "conversation_id": "conv-123",
            "response": "System health is OK.",
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = _call_sentinel_chat("check health", "conv-123")

        self.assertEqual(result["response"], "System health is OK.")
        self.assertEqual(result["conversation_id"], "conv-123")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("/api/v1/agent/chat", call_args[0][0])

    @patch("voice_agent.agent.requests.post")
    def test_api_failure_returns_error_message(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")

        result = _call_sentinel_chat("check health")

        self.assertIn("couldn't reach", result["response"])
        self.assertIn("Connection refused", result["response"])

    @patch("voice_agent.agent.requests.post")
    def test_no_conversation_id(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "Hello!",
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = _call_sentinel_chat("hello")
        self.assertEqual(result["response"], "Hello!")


class TestSentinelLLM(unittest.TestCase):
    """Test the custom LLM class."""

    def test_properties(self):
        llm = SentinelLLM()
        self.assertEqual(llm.model, "sentinel-proxy")
        self.assertEqual(llm.provider, "hana-sentinel")

    def test_chat_returns_stream(self):
        async def _test():
            llm = SentinelLLM()
            ctx = ChatContext()
            ctx.add_message(role="user", content="check disk usage")
            stream = llm.chat(chat_ctx=ctx)
            self.assertIsInstance(stream, SentinelLLMStream)
        _run(_test())

    def test_chat_extracts_user_message(self):
        async def _test():
            llm = SentinelLLM()
            ctx = ChatContext()
            ctx.add_message(role="system", content="You are an assistant.")
            ctx.add_message(role="user", content="hello sentinel")
            stream = llm.chat(chat_ctx=ctx)
            self.assertEqual(stream._user_msg, "hello sentinel")
        _run(_test())

    def test_chat_empty_context(self):
        async def _test():
            llm = SentinelLLM()
            ctx = ChatContext()
            stream = llm.chat(chat_ctx=ctx)
            self.assertEqual(stream._user_msg, "")
        _run(_test())


class TestSentinelLLMStream(unittest.TestCase):
    """Test the LLM stream response emission."""

    @patch("voice_agent.agent._call_sentinel_chat")
    def test_stream_emits_response(self, mock_chat):
        mock_chat.return_value = {
            "conversation_id": "conv-abc",
            "response": "Disk usage is at 45%.",
        }

        async def _test():
            llm_instance = SentinelLLM()
            ctx = ChatContext()
            ctx.add_message(role="user", content="check disk")
            stream = llm_instance.chat(chat_ctx=ctx)

            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            self.assertTrue(len(chunks) > 0, "Should emit at least one chunk")
            # First chunk is a filler phrase (e.g. "On it. "), actual content follows
            all_content = "".join(c.delta.content or "" for c in chunks)
            self.assertIn("Disk usage is at 45 percent", all_content)
            self.assertEqual(chunks[0].delta.role, "assistant")

        _run(_test())

    @patch("voice_agent.agent._call_sentinel_chat")
    def test_stream_persists_conversation_id(self, mock_chat):
        mock_chat.return_value = {
            "conversation_id": "conv-xyz",
            "response": "OK",
        }

        async def _test():
            llm_instance = SentinelLLM()
            self.assertIsNone(llm_instance._conversation_id)

            ctx = ChatContext()
            ctx.add_message(role="user", content="test")
            stream = llm_instance.chat(chat_ctx=ctx)

            async for _ in stream:
                pass

            self.assertEqual(llm_instance._conversation_id, "conv-xyz")

        _run(_test())

    @patch("voice_agent.agent._call_sentinel_chat")
    def test_stream_strips_markdown(self, mock_chat):
        mock_chat.return_value = {
            "conversation_id": "c1",
            "response": "**Status:** `OK`\n\n```\nsome output\n```",
        }

        async def _test():
            llm_instance = SentinelLLM()
            ctx = ChatContext()
            ctx.add_message(role="user", content="status")
            stream = llm_instance.chat(chat_ctx=ctx)

            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            all_content = "".join(c.delta.content or "" for c in chunks)
            self.assertNotIn("```", all_content)
            self.assertNotIn("**", all_content)
            self.assertIn("Status", all_content)

        _run(_test())


class TestSentinelAPIIntegration(unittest.TestCase):
    """Integration test: calls the real Sentinel API (if running)."""

    def setUp(self):
        """Skip if Sentinel API is not reachable."""
        import requests
        try:
            resp = requests.get(f"{SENTINEL_API_URL}/api/v1/health", timeout=5)
            if resp.status_code != 200:
                self.skipTest("Sentinel API not healthy")
        except Exception:
            self.skipTest("Sentinel API not reachable")

    def test_real_chat_health(self):
        result = _call_sentinel_chat("What is your status?")
        self.assertIn("response", result)
        self.assertTrue(len(result["response"]) > 0)

    def test_real_chat_conversation_continuity(self):
        r1 = _call_sentinel_chat("Hello, who are you?")
        conv_id = r1.get("conversation_id")
        self.assertIsNotNone(conv_id)

        r2 = _call_sentinel_chat("What did I just ask?", conv_id)
        self.assertIn("response", r2)

    def test_real_llm_stream(self):
        """Full pipeline: SentinelLLM -> stream -> collect response."""
        async def _test():
            llm_instance = SentinelLLM()
            ctx = ChatContext()
            ctx.add_message(role="user", content="check disk usage")
            stream = llm_instance.chat(chat_ctx=ctx)

            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            self.assertTrue(len(chunks) > 0)
            self.assertIsNotNone(chunks[0].delta.content)
            print(f"\n  [Integration] Agent response: {chunks[0].delta.content[:200]}...")

        _run(_test())


if __name__ == "__main__":
    unittest.main(verbosity=2)
