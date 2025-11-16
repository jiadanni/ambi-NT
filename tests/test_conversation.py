"""
Tests for conversation/multi-turn functionality
"""

import pytest
import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from context_manager import ContextManager
from node.models import Message


class TestContextManager:
    """Test context manager functionality."""

    def test_token_estimation(self):
        """Test token count estimation."""
        manager = ContextManager()

        short_text = "Hello world"
        long_text = "This is a much longer text with many more words " * 10

        short_tokens = manager.estimate_tokens(short_text)
        long_tokens = manager.estimate_tokens(long_text)

        assert short_tokens > 0
        assert long_tokens > short_tokens
        assert short_tokens < 50  # Should be small
        assert long_tokens > 100  # Should be larger

    def test_message_token_estimation(self):
        """Test token estimation for messages."""
        manager = ContextManager()

        msg = Message(role="user", content="What is Python?")
        tokens = manager.estimate_message_tokens(msg)

        # Should include content tokens + role overhead
        assert tokens > len(msg.content.split())
        assert tokens < len(msg.content.split()) + 20  # Small overhead

    def test_conversation_token_estimation(self):
        """Test token estimation for full conversations."""
        manager = ContextManager()

        messages = [
            Message(role="user", content="What is Python?"),
            Message(role="assistant", content="Python is a programming language."),
            Message(role="user", content="Show me an example"),
        ]

        total_tokens = manager.estimate_conversation_tokens(messages)

        # Should be reasonable estimate
        total_text_length = sum(len(m.content) for m in messages)
        assert total_tokens > total_text_length // 10  # At least this much
        assert total_tokens < total_text_length * 2  # Not more than this

    def test_simple_truncation(self):
        """Test simple truncation strategy."""
        manager = ContextManager(max_tokens=100)

        # Create messages that exceed token limit
        messages = [
            Message(role="user", content="x" * 50),
            Message(role="assistant", content="y" * 50),
            Message(role="user", content="z" * 50),
        ]

        truncated, token_count = manager.truncate_smart(messages, max_tokens=100)

        # Should keep messages within token limit
        assert token_count <= 100
        assert len(truncated) > 0  # Should keep at least something

    def test_smart_truncation_keeps_recent(self):
        """Test that smart truncation keeps most recent messages."""
        manager = ContextManager(max_tokens=200)

        messages = []
        for i in range(10):
            messages.append(Message(role="user", content=f"Question {i}"))
            messages.append(Message(role="assistant", content=f"Answer {i}"))

        truncated, token_count = manager.truncate_smart(messages, max_tokens=200)

        # Should keep most recent messages
        # Check that recent content is present (either last question or answer)
        last_content = " ".join([m.content for m in truncated[-2:]])
        assert "9" in last_content  # Should have messages from iteration 9

    def test_smart_truncation_keeps_system_prompt(self):
        """Test that system prompts are preserved."""
        manager = ContextManager(max_tokens=150)

        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="x" * 50),
            Message(role="assistant", content="y" * 50),
            Message(role="user", content="z" * 50),
        ]

        truncated, token_count = manager.truncate_smart(messages, max_tokens=150)

        # System message should be kept
        assert truncated[0].role == "system"
        assert truncated[0].content == "You are a helpful assistant."

    def test_smart_truncation_enforces_last_user_message(self):
        """Test that the most recent user message is always kept."""
        manager = ContextManager(max_tokens=50)

        messages = [
            Message(role="user", content="Important question"),
            Message(role="assistant", content="Previous answer"),
        ]

        truncated, token_count = manager.truncate_smart(messages, max_tokens=50)

        # Should keep what fits - at least one message
        assert len(truncated) >= 1
        assert token_count <= 50
        # Should include the user message
        user_contents = [m.content for m in truncated if m.role == "user"]
        assert "Important question" in user_contents

    def test_parse_conversation_json(self):
        """Test JSON conversation parsing."""
        manager = ContextManager()

        conversation_json = json.dumps([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ])

        messages = manager.parse_conversation_json(conversation_json)

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Hi there"

    def test_parse_invalid_json(self):
        """Test that invalid JSON raises ValueError."""
        manager = ContextManager()

        with pytest.raises(ValueError, match="Invalid JSON"):
            manager.parse_conversation_json("{invalid json")

    def test_parse_invalid_format(self):
        """Test that invalid format raises ValueError."""
        manager = ContextManager()

        # Not an array
        with pytest.raises(ValueError, match="must be a JSON array"):
            manager.parse_conversation_json('{"not": "array"}')

        # Missing fields
        with pytest.raises(ValueError, match="must have 'role' and 'content'"):
            manager.parse_conversation_json('[{"role": "user"}]')

    def test_format_for_ollama(self):
        """Test formatting for Ollama API."""
        manager = ContextManager()

        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]

        formatted = manager.format_for_ollama(messages)

        assert len(formatted) == 2
        assert formatted[0] == {"role": "user", "content": "Hello"}
        assert formatted[1] == {"role": "assistant", "content": "Hi"}

    def test_validate_conversation_valid(self):
        """Test conversation validation with valid conversation."""
        manager = ContextManager()

        messages = [
            Message(role="user", content="Question"),
            Message(role="assistant", content="Answer"),
            Message(role="user", content="Follow-up"),
        ]

        is_valid, error = manager.validate_conversation(messages)
        assert is_valid
        assert error is None

    def test_validate_conversation_with_system(self):
        """Test validation with system prompt."""
        manager = ContextManager()

        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Question"),
        ]

        is_valid, error = manager.validate_conversation(messages)
        assert is_valid
        assert error is None

    def test_validate_conversation_empty(self):
        """Test that empty conversations are invalid."""
        manager = ContextManager()

        is_valid, error = manager.validate_conversation([])
        assert not is_valid
        assert "empty" in error.lower()

    def test_validate_conversation_empty_content(self):
        """Test that empty content is invalid."""
        manager = ContextManager()

        messages = [Message(role="user", content="")]

        is_valid, error = manager.validate_conversation(messages)
        assert not is_valid
        assert "empty" in error.lower()

    def test_validate_conversation_system_after_conversation(self):
        """Test that system messages after conversation are invalid."""
        manager = ContextManager()

        messages = [
            Message(role="user", content="Question"),
            Message(role="system", content="System prompt after conversation"),
        ]

        is_valid, error = manager.validate_conversation(messages)
        assert not is_valid
        assert "system" in error.lower()

    def test_validate_conversation_must_start_with_user(self):
        """Test that conversations must start with user message."""
        manager = ContextManager()

        messages = [
            Message(role="assistant", content="I'll start the conversation"),
        ]

        is_valid, error = manager.validate_conversation(messages)
        assert not is_valid
        assert "user" in error.lower()

    def test_validate_conversation_allows_assistant_last(self):
        """Test that conversations can end with assistant message."""
        manager = ContextManager()

        messages = [
            Message(role="user", content="Question"),
            Message(role="assistant", content="Answer"),
        ]

        is_valid, error = manager.validate_conversation(messages)
        assert is_valid  # This is now allowed
        assert error is None

    def test_truncation_with_very_long_system_prompt(self):
        """Test handling of system prompts that exceed token limit."""
        manager = ContextManager(max_tokens=100)

        messages = [
            Message(role="system", content="x" * 200),  # Very long
            Message(role="user", content="Question"),
        ]

        truncated, token_count = manager.truncate_smart(messages, max_tokens=100)

        # Should still return something (truncated system message)
        assert len(truncated) > 0
        # Token count should be close to limit
        assert token_count <= 150  # Allow some overflow for system

    def test_context_window_with_4096_tokens(self):
        """Test realistic scenario with 4096 token window."""
        manager = ContextManager(max_tokens=4096)

        # Create a long conversation
        messages = []
        for i in range(50):
            messages.append(Message(
                role="user",
                content=f"This is question {i} with some additional context " * 5
            ))
            messages.append(Message(
                role="assistant",
                content=f"This is answer {i} with detailed explanation " * 10
            ))

        truncated, token_count = manager.truncate_smart(messages, max_tokens=4096)

        # Should be under limit
        assert token_count <= 4096
        # Should keep at least some messages
        assert len(truncated) > 0
        # Should keep recent messages (from high numbered iterations)
        last_messages_text = " ".join([m.content for m in truncated[-3:]])
        # Should have content from later iterations
        assert any(str(i) in last_messages_text for i in range(45, 50))


class TestConversationIntegration:
    """Integration tests for conversation flow."""

    def test_conversation_json_round_trip(self):
        """Test that conversations can be serialized and parsed."""
        manager = ContextManager()

        original_messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
            Message(role="user", content="How are you?"),
        ]

        # Convert to JSON
        formatted = manager.format_for_ollama(original_messages)
        json_str = json.dumps(formatted)

        # Parse back
        parsed_messages = manager.parse_conversation_json(json_str)

        # Should match
        assert len(parsed_messages) == len(original_messages)
        for orig, parsed in zip(original_messages, parsed_messages):
            assert orig.role == parsed.role
            assert orig.content == parsed.content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
