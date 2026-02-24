"""
Context window management for conversation support.

Implements smart truncation to keep conversations within token limits
while preserving important context.
"""

import json
import logging
from typing import List, Tuple, Optional
from node.models import Message

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context with smart truncation."""

    def __init__(self, max_tokens: int = 4096):
        """
        Initialize context manager.

        Args:
            max_tokens: Maximum tokens to allow in context window
        """
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses improved heuristic that accounts for:
        - Average token length varies by language and content type
        - Code/technical text: ~3.5 chars/token
        - Natural language: ~4 chars/token
        - Most words are 1-2 tokens

        For production accuracy, consider using tiktoken library.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Count words and characters
        words = text.split()
        chars = len(text)

        # Character-based estimate: average 3.5 chars/token
        # This is more accurate than 4 for typical LLM tokenization
        char_based = int(chars / 3.5)

        # Word-based estimate: average 1.3 tokens/word
        # Accounts for multi-token words and punctuation
        word_based = int(len(words) * 1.3)

        # Use maximum for conservative estimate (prevents context overflow)
        return max(char_based, word_based)

    def estimate_message_tokens(self, message: Message) -> int:
        """
        Estimate tokens for a single message including role overhead.

        Args:
            message: Message to estimate

        Returns:
            Estimated token count
        """
        # Role overhead: ~4 tokens per message for formatting
        # <|im_start|>role\ncontent<|im_end|>
        role_overhead = 4
        content_tokens = self.estimate_tokens(message.content)
        return role_overhead + content_tokens

    def estimate_conversation_tokens(self, messages: List[Message]) -> int:
        """
        Estimate total tokens for a conversation.

        Args:
            messages: List of messages

        Returns:
            Total estimated token count
        """
        total = sum(self.estimate_message_tokens(msg) for msg in messages)
        # Add a small buffer for the response
        response_buffer = 50
        return total + response_buffer

    def truncate_smart(
        self,
        messages: List[Message],
        max_tokens: Optional[int] = None
    ) -> Tuple[List[Message], int]:
        """
        Smart truncation strategy:
        1. Keep system prompts (if any)
        2. Keep the most recent user message
        3. Fill remaining space with recent conversation history
        4. If needed, summarize old context (for future enhancement)

        Args:
            messages: Full conversation history
            max_tokens: Token limit (defaults to self.max_tokens)

        Returns:
            Tuple of (truncated_messages, estimated_tokens)
        """
        if not messages:
            return [], 0

        limit = max_tokens or self.max_tokens

        # Separate system messages from conversation
        system_messages = [msg for msg in messages if msg.role == "system"]
        conversation_messages = [msg for msg in messages if msg.role != "system"]

        # Calculate system message tokens
        system_tokens = sum(
            self.estimate_message_tokens(msg) for msg in system_messages
        )

        # Reserve tokens for system messages
        available_tokens = limit - system_tokens

        if available_tokens <= 0:
            logger.warning(f"System messages exceed token limit: {system_tokens} > {limit}")
            # Truncate system messages if they're too long
            return self._truncate_simple(system_messages, limit)

        # If no conversation yet, just return system messages
        if not conversation_messages:
            return system_messages, system_tokens

        # Build from most recent backwards
        truncated_conversation = []
        current_tokens = 0

        # Always keep the most recent user message
        last_user_idx = None
        for i in range(len(conversation_messages) - 1, -1, -1):
            if conversation_messages[i].role == "user":
                last_user_idx = i
                break

        if last_user_idx is not None:
            # Add messages from the end, working backwards
            for i in range(len(conversation_messages) - 1, -1, -1):
                msg = conversation_messages[i]
                msg_tokens = self.estimate_message_tokens(msg)

                if current_tokens + msg_tokens <= available_tokens:
                    truncated_conversation.insert(0, msg)
                    current_tokens += msg_tokens
                else:
                    # Can't fit more messages
                    if i <= last_user_idx:
                        # We must include the last user message
                        logger.warning(
                            f"Last user message too large: {msg_tokens} tokens "
                            f"(available: {available_tokens - current_tokens})"
                        )
                        # Force include it, removing older messages if needed
                        while truncated_conversation and current_tokens + msg_tokens > available_tokens:
                            removed = truncated_conversation.pop(0)
                            current_tokens -= self.estimate_message_tokens(removed)
                        truncated_conversation.insert(0, msg)
                        current_tokens += msg_tokens
                    break
        else:
            # No user messages? Just take what fits
            truncated_conversation, current_tokens = self._truncate_simple(
                conversation_messages, available_tokens
            )

        # Combine system messages + truncated conversation
        result = system_messages + truncated_conversation
        total_tokens = system_tokens + current_tokens

        if len(result) < len(messages):
            logger.info(
                f"Truncated conversation: {len(messages)} → {len(result)} messages "
                f"({self.estimate_conversation_tokens(messages)} → {total_tokens} tokens)"
            )

        return result, total_tokens

    def _truncate_simple(
        self,
        messages: List[Message],
        max_tokens: int
    ) -> Tuple[List[Message], int]:
        """
        Simple truncation: keep most recent messages that fit.

        Args:
            messages: Messages to truncate
            max_tokens: Token limit

        Returns:
            Tuple of (truncated_messages, estimated_tokens)
        """
        result = []
        current_tokens = 0

        for msg in reversed(messages):
            msg_tokens = self.estimate_message_tokens(msg)
            if current_tokens + msg_tokens <= max_tokens:
                result.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break

        return result, current_tokens

    def parse_conversation_json(self, json_str: str) -> List[Message]:
        """
        Parse conversation from JSON string.

        Args:
            json_str: JSON string containing conversation

        Returns:
            List of Message objects

        Raises:
            ValueError: If JSON is invalid or doesn't match expected format
        """
        try:
            data = json.loads(json_str)

            if not isinstance(data, list):
                raise ValueError("Conversation must be a JSON array")

            messages = []
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError("Each message must be a JSON object")

                if "role" not in item or "content" not in item:
                    raise ValueError("Each message must have 'role' and 'content'")

                messages.append(Message(
                    role=item["role"],
                    content=item["content"]
                ))

            return messages

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")

    def format_for_ollama(self, messages: List[Message]) -> List[dict]:
        """
        Format messages for Ollama API.

        Ollama expects: [{"role": "user", "content": "..."}, ...]

        Args:
            messages: List of Message objects

        Returns:
            List of dicts formatted for Ollama
        """
        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in messages
        ]

    def validate_conversation(self, messages: List[Message]) -> Tuple[bool, Optional[str]]:
        """
        Validate conversation structure.

        Checks:
        - No empty messages
        - System messages come first
        - First conversation message is from user
        - At least one user message exists

        Args:
            messages: Messages to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not messages:
            return False, "Conversation is empty"

        # Check for empty content
        for i, msg in enumerate(messages):
            if not msg.content or not msg.content.strip():
                return False, f"Message {i} has empty content"

        # Validate role sequence
        # System messages should be at the start
        seen_non_system = False
        for i, msg in enumerate(messages):
            if msg.role == "system":
                if seen_non_system:
                    return False, f"System message at position {i} must come before conversation"
            else:
                seen_non_system = True

        # Get conversation messages (non-system)
        conversation = [msg for msg in messages if msg.role != "system"]

        if not conversation:
            return True, None  # Only system messages is valid

        # First conversation message should be from user
        if conversation[0].role != "user":
            return False, "First conversation message must be from user"

        # Must have at least one user message
        has_user_message = any(msg.role == "user" for msg in conversation)
        if not has_user_message:
            return False, "Conversation must contain at least one user message"

        return True, None
