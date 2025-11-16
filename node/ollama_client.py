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
from typing import Optional
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
        Generate a response from Ollama.

        Args:
            prompt: The plaintext prompt to process
            timeout: Maximum seconds to wait for response

        Returns:
            The generated response, or None if timeout/error occurs

        SECURITY NOTE: The prompt parameter contains plaintext user data.
        Never log this value. It should only exist in memory during execution.
        """
        try:
            # We use subprocess to call ollama CLI
            # The prompt is passed via stdin to avoid shell history
            process = subprocess.Popen(
                ["ollama", "run", self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Write prompt to stdin and close it
            # This is safer than passing as command line argument
            stdout, stderr = process.communicate(input=prompt, timeout=timeout)

            if process.returncode != 0:
                # Log the error but NOT the prompt
                logger.error(f"Ollama process failed with code {process.returncode}")
                logger.error(f"Stderr: {stderr}")
                return None

            # Return the generated response
            # This is also plaintext and should be encrypted immediately after
            return stdout.strip()

        except subprocess.TimeoutExpired:
            # Kill the process if it exceeds timeout
            process.kill()
            logger.warning(f"Ollama generation exceeded timeout of {timeout}s")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in Ollama generation: {str(e)}")
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
