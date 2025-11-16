"""
Configuration management for Ambient Intelligence node.

Loads configuration from environment variables with sensible defaults.
"""

import os
import uuid
from typing import Optional


class Config:
    """Node configuration loaded from environment variables."""

    def __init__(self):
        # Node identity
        self.node_id = os.getenv("NODE_ID", str(uuid.uuid4()))
        self.node_port = int(os.getenv("NODE_PORT", "8000"))

        # Ollama configuration
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3:8b")

        # Performance settings
        self.max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))
        self.job_timeout_seconds = int(os.getenv("JOB_TIMEOUT_SECONDS", "120"))

        # Cryptography
        self.node_private_key = os.getenv("NODE_PRIVATE_KEY")
        self.node_public_key = os.getenv("NODE_PUBLIC_KEY")

        # Coordinator (Phase 2+)
        self.coordinator_url = os.getenv("COORDINATOR_URL", "")
        self.heartbeat_interval_seconds = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60"))

        # Debugging
        self.enable_debug_logs = os.getenv("ENABLE_DEBUG_LOGS", "false").lower() == "true"

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if not self.node_id:
            return False, "NODE_ID is required"

        if self.node_port < 1 or self.node_port > 65535:
            return False, f"Invalid NODE_PORT: {self.node_port}"

        if self.max_concurrent_jobs < 1:
            return False, "MAX_CONCURRENT_JOBS must be at least 1"

        if self.job_timeout_seconds < 10:
            return False, "JOB_TIMEOUT_SECONDS must be at least 10"

        return True, None

    def __repr__(self) -> str:
        """String representation (without sensitive data)."""
        return (
            f"Config(node_id={self.node_id[:8]}..., "
            f"port={self.node_port}, "
            f"model={self.ollama_model}, "
            f"max_concurrent={self.max_concurrent_jobs})"
        )
