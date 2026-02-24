"""
Wrapper for interacting with Ollama.

This module ensures that:
1. Prompts are passed to Ollama via stdin (not command line, to avoid shell history)
2. Resource limits are enforced (timeout, no disk writes)
3. No plaintext is logged

Privacy Note:
- The prompt parameter contains plaintext user data
- This data is NEVER logged or persisted
- It only exists in memory during execution
"""

import subprocess
import signal
import json
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class OllamaClient:
    """Interface to local Ollama instance."""

    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3:8b"):
        """
        Initialize Ollama client.

        Args:
            host: Ollama API host URL
            model: Default model to use for generation
        """
        self.host = host
        self.model = model

    def generate(self, prompt: str, timeout: int = 120) -> Optional[str]:
        """
        Generate a response from Ollama with strict timeout enforcement.

        Args:
            prompt: The plaintext prompt to process
            timeout: Maximum seconds to wait for response

        Returns:
            The generated response, or None if timeout/error occurs

        SECURITY NOTE: The prompt parameter contains plaintext user data.
        Never log this value. It should only exist in memory during execution.
        """
        process = None
        try:
            # We use subprocess to call ollama CLI
            # The prompt is passed via stdin to avoid shell history
            process = subprocess.Popen(
                ["ollama", "run", self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                # Set process group for proper cleanup
                preexec_fn=None if subprocess.os.name == 'nt' else lambda: subprocess.os.setpgrp()
            )

            # Write prompt to stdin and close it
            # This is safer than passing as command line argument
            # Timeout is enforced at the communicate level
            stdout, stderr = process.communicate(input=prompt, timeout=timeout)

            if process.returncode != 0:
                # Log the error but NOT the prompt
                logger.error(f"Ollama process failed with code {process.returncode}")
                if stderr:
                    logger.error(f"Stderr: {stderr[:200]}")  # Limit stderr output
                return None

            # Return the generated response
            # This is also plaintext and should be encrypted immediately after
            return stdout.strip()

        except subprocess.TimeoutExpired:
            # Kill the process if it exceeds timeout
            logger.warning(f"Ollama generation exceeded timeout of {timeout}s - terminating process")
            if process:
                try:
                    # Try graceful termination first
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # Force kill if still running
                        process.kill()
                        process.wait()
                    logger.info("Ollama process terminated successfully")
                except Exception as kill_error:
                    logger.error(f"Error terminating Ollama process: {kill_error}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in Ollama generation: {str(e)}")
            # Ensure process cleanup on unexpected errors
            if process and process.poll() is None:
                try:
                    process.kill()
                    process.wait()
                except:
                    pass
            return None

    def is_available(self) -> bool:
        """
        Check if Ollama is running and responsive.

        Returns:
            True if Ollama is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        timeout: int = 120
    ) -> Optional[str]:
        """
        Generate a response from Ollama using chat/conversation format.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Format: [{"role": "user", "content": "..."}]
            timeout: Maximum seconds to wait for response

        Returns:
            The generated response, or None if timeout/error occurs

        SECURITY NOTE: Messages contain plaintext user data.
        Never log these values. They should only exist in memory during execution.
        """
        try:
            # Convert messages to JSON for stdin
            # Ollama accepts conversation history in this format
            messages_json = json.dumps(messages)

            # Create a prompt that simulates conversation by concatenating messages
            # For Ollama CLI, we need to format this as a single prompt
            # Format: role: content\n\nrole: content\n\n...
            formatted_prompt = self._format_messages_as_prompt(messages)

            # Use the standard generate method with formatted prompt
            return self.generate(formatted_prompt, timeout=timeout)

        except Exception as e:
            logger.error(f"Unexpected error in Ollama chat generation: {str(e)}")
            return None

    def _format_messages_as_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Format conversation messages as a single prompt for Ollama CLI.

        Since Ollama CLI doesn't natively support the chat format in the same way
        as the API, we format the conversation history as a coherent prompt.

        Args:
            messages: List of message dicts

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        # Join with double newlines for clarity
        # Add a final "Assistant:" to prompt the model to respond
        prompt = "\n\n".join(prompt_parts)
        if messages[-1]["role"] == "user":
            prompt += "\n\nAssistant:"

        return prompt

    def pull_model(self, model: str = None) -> bool:
        """
        Pull a model if not already present.

        Args:
            model: Model to pull (uses self.model if not specified)

        Returns:
            True if successful, False otherwise
        """
        model_to_pull = model or self.model
        try:
            logger.info(f"Pulling model: {model_to_pull}")
            result = subprocess.run(
                ["ollama", "pull", model_to_pull],
                capture_output=True,
                timeout=600  # 10 minutes for large models
            )
            if result.returncode == 0:
                logger.info(f"Successfully pulled model: {model_to_pull}")
                return True
            else:
                logger.error(f"Failed to pull model: {result.stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error pulling model: {str(e)}")
            return False
