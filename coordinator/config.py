"""
Configuration management for Ambient Intelligence Coordinator.

Loads configuration from environment variables with sensible defaults.
"""

import os
from typing import Optional, List


class CoordinatorConfig:
    """Coordinator configuration loaded from environment variables."""

    def __init__(self):
        # Server configuration
        self.coordinator_port = int(os.getenv("COORDINATOR_PORT", "5000"))
        self.host = os.getenv("COORDINATOR_HOST", "0.0.0.0")

        # Database
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://ambient:ambient@localhost:5432/ambient"
        )

        # Redis (for caching and rate limiting - Phase 2+)
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Node management
        self.node_heartbeat_timeout = int(os.getenv("NODE_HEARTBEAT_TIMEOUT", "90"))  # seconds
        self.node_cleanup_interval = int(os.getenv("NODE_CLEANUP_INTERVAL", "300"))  # seconds
        self.min_uptime_for_discovery = float(os.getenv("MIN_UPTIME_FOR_DISCOVERY", "10.0"))

        # Priority tokens
        self.priority_token_multiplier = float(os.getenv("PRIORITY_TOKEN_MULTIPLIER", "2.0"))
        self.tokens_per_minute_compute = int(os.getenv("TOKENS_PER_MINUTE_COMPUTE", "10"))

        # Abuse detection
        self.abuse_report_threshold = int(os.getenv("ABUSE_REPORT_THRESHOLD", "3"))
        self.abuse_block_duration_hours = int(os.getenv("ABUSE_BLOCK_DURATION_HOURS", "24"))
        self.max_requests_per_minute = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
        self.require_node_signature = os.getenv("REQUIRE_NODE_SIGNATURE", "true").lower() == "true"
        self.node_signature_max_age_seconds = int(os.getenv("NODE_SIGNATURE_MAX_AGE_SECONDS", "300"))

        # Federation (Phase 3)
        self.peer_coordinators = self._parse_peer_coordinators()
        self.federation_enabled = os.getenv("FEDERATION_ENABLED", "false").lower() == "true"
        self.federation_sync_interval = int(os.getenv("FEDERATION_SYNC_INTERVAL", "300"))  # seconds
        self.coordinator_secret = os.getenv("COORDINATOR_SECRET", "")  # For signing node announcements
        self.federation_trust_mode = os.getenv("FEDERATION_TRUST_MODE", "permissive")  # permissive or strict
        self.trusted_coordinators = self._parse_trusted_coordinators()
        self.coordinator_public_url = os.getenv("COORDINATOR_PUBLIC_URL", "")

        # Security
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "")
        self.admin_token = os.getenv("ADMIN_TOKEN", "")
        self.enable_cors = os.getenv("ENABLE_CORS", "true").lower() == "true"
        self.cors_origins = self._parse_cors_origins()

        # Logging
        self.enable_debug_logs = os.getenv("ENABLE_DEBUG_LOGS", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        # Features
        self.enable_priority_tokens = os.getenv("ENABLE_PRIORITY_TOKENS", "true").lower() == "true"
        self.enable_abuse_detection = os.getenv("ENABLE_ABUSE_DETECTION", "true").lower() == "true"

    def _parse_peer_coordinators(self) -> List[str]:
        """Parse comma-separated list of peer coordinator URLs."""
        peers = os.getenv("PEER_COORDINATORS", "")
        if not peers:
            return []
        return [url.strip() for url in peers.split(",") if url.strip()]

    def _parse_trusted_coordinators(self) -> dict:
        """Parse trusted coordinators in url=secret format."""
        raw = os.getenv("TRUSTED_COORDINATORS", "")
        if not raw:
            return {}
        trusted = {}
        for pair in raw.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                continue
            url, secret = pair.split("=", 1)
            url = url.strip()
            secret = secret.strip()
            if url and secret:
                trusted[url] = secret
        return trusted

    def _parse_cors_origins(self) -> List[str]:
        """Parse comma-separated list of allowed CORS origins."""
        origins = os.getenv("CORS_ORIGINS", "*")
        if origins == "*":
            return ["*"]
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if not self.database_url:
            return False, "DATABASE_URL is required"

        if self.coordinator_port < 1 or self.coordinator_port > 65535:
            return False, f"Invalid COORDINATOR_PORT: {self.coordinator_port}"

        if self.node_heartbeat_timeout < 10:
            return False, "NODE_HEARTBEAT_TIMEOUT must be at least 10 seconds"

        if self.enable_priority_tokens and not self.jwt_secret_key:
            return False, "JWT_SECRET_KEY is required when priority tokens are enabled"

        return True, None

    def __repr__(self) -> str:
        """String representation (without sensitive data)."""
        return (
            f"CoordinatorConfig(port={self.coordinator_port}, "
            f"db=***masked***, "
            f"priority_tokens={self.enable_priority_tokens})"
        )
