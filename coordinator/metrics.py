"""
Privacy-Preserving Metrics Module

Implements metrics collection that respects user privacy:
- NO user IDs tracked
- NO prompt/response content
- NO IP addresses in logs
- Only aggregate statistics
- Hashed node IDs for debugging

Metrics exposed via Prometheus format for monitoring tools.
"""

import logging
import hashlib
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# Prometheus metrics (optional if library available)
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.warning("prometheus_client not installed - metrics disabled")


class PrivacyPreservingMetrics:
    """
    Metrics collector that preserves user privacy.
    
    Design principles:
    1. Never log user identifiers (IPs, session IDs, etc.)
    2. Never log prompt or response content
    3. Hash node IDs before recording
    4. Only aggregate statistics
    5. Time-series data only for performance optimization
    """
    
    def __init__(self):
        """Initialize metrics collectors."""
        if not METRICS_ENABLED:
            logger.warning("Metrics disabled - prometheus_client not available")
            self._init_noop()
            return
        
        # Job metrics - aggregate only
        self.jobs_routed_total = Counter(
            "coordinator_jobs_routed_total",
            "Total jobs routed to nodes",
            ["model"]  # Only model type, no user data
        )
        
        self.job_duration_seconds = Histogram(
            "coordinator_job_duration_seconds",
            "Job processing duration",
            ["model"],
            buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600]
        )
        
        # Node health metrics - hashed IDs only
        self.active_nodes_gauge = Gauge(
            "coordinator_active_nodes",
            "Number of active nodes in network"
        )
        
        self.node_health_gauge = Gauge(
            "coordinator_node_health",
            "Node health status (1=healthy, 0=unhealthy)",
            ["node_hash", "model"]  # Hashed node ID
        )
        
        self.node_load_gauge = Gauge(
            "coordinator_node_load",
            "Current node load percentage",
            ["node_hash"]
        )
        
        # Network metrics
        self.network_capacity_gauge = Gauge(
            "coordinator_network_capacity",
            "Total network processing capacity",
            ["model"]
        )
        
        self.heartbeat_failures_total = Counter(
            "coordinator_heartbeat_failures_total",
            "Total heartbeat failures (indicates node issues)"
        )
        
        # Federation metrics
        self.federation_syncs_total = Counter(
            "coordinator_federation_syncs_total",
            "Federation peer sync attempts",
            ["peer_hash", "status"]  # Hashed peer URL, success/failure
        )
        
        self.federation_nodes_synced = Histogram(
            "coordinator_federation_nodes_synced",
            "Number of nodes synced from peers",
            ["peer_hash"],
            buckets=[0, 1, 5, 10, 50, 100, 500, 1000]
        )
        
        # Session metrics - NO session IDs, only counts
        self.active_sessions_gauge = Gauge(
            "coordinator_active_sessions",
            "Number of active conversation sessions"
        )
        
        self.session_duration_seconds = Histogram(
            "coordinator_session_duration_seconds",
            "Session lifespan",
            buckets=[60, 300, 600, 1800, 3600, 7200]
        )
        
        logger.info("Privacy-preserving metrics initialized")
    
    def _init_noop(self):
        """Initialize no-op metrics for when Prometheus is unavailable."""
        class NoOp:
            def labels(self, *args, **kwargs):
                return self
            def inc(self, *args, **kwargs):
                pass
            def set(self, *args, **kwargs):
                pass
            def observe(self, *args, **kwargs):
                pass
            def dec(self, *args, **kwargs):
                pass
        
        noop = NoOp()
        self.jobs_routed_total = noop
        self.job_duration_seconds = noop
        self.active_nodes_gauge = noop
        self.node_health_gauge = noop
        self.node_load_gauge = noop
        self.network_capacity_gauge = noop
        self.heartbeat_failures_total = noop
        self.federation_syncs_total = noop
        self.federation_nodes_synced = noop
        self.active_sessions_gauge = noop
        self.session_duration_seconds = noop
    
    @staticmethod
    def hash_identifier(identifier: str, prefix: str = "") -> str:
        """
        Hash an identifier for privacy.
        
        Args:
            identifier: The ID to hash (node_id, IP, URL, etc.)
            prefix: Optional prefix for readability
            
        Returns:
            Hashed identifier (first 8 chars for readability)
        """
        hashed = hashlib.sha256(identifier.encode()).hexdigest()[:8]
        return f"{prefix}{hashed}" if prefix else hashed
    
    def record_job(self, model: str, duration: float):
        """
        Record job metrics.
        
        Args:
            model: Model name (e.g., "llama3:8b")
            duration: Job duration in seconds
        """
        self.jobs_routed_total.labels(model=model).inc()
        self.job_duration_seconds.labels(model=model).observe(duration)
        logger.debug(f"Recorded job: model={model}, duration={duration:.2f}s")
    
    def record_node_health(self, node_id: str, is_healthy: bool, models: Optional[list] = None):
        """
        Record node health status.
        
        Args:
            node_id: Node identifier (will be hashed)
            is_healthy: Whether node is healthy
            models: List of supported models
        """
        node_hash = self.hash_identifier(node_id, prefix="node_")
        
        # Record health for each model
        if models:
            for model in models:
                self.node_health_gauge.labels(
                    node_hash=node_hash,
                    model=model
                ).set(1 if is_healthy else 0)
        else:
            # Generic health without model info
            self.node_health_gauge.labels(
                node_hash=node_hash,
                model="unknown"
            ).set(1 if is_healthy else 0)
    
    def record_node_load(self, node_id: str, load: float):
        """
        Record node load.
        
        Args:
            node_id: Node identifier (will be hashed)
            load: Current load (0.0 to 1.0)
        """
        node_hash = self.hash_identifier(node_id, prefix="node_")
        self.node_load_gauge.labels(node_hash=node_hash).set(load)
    
    def record_active_nodes(self, count: int):
        """
        Record total active nodes.
        
        Args:
            count: Number of active nodes
        """
        self.active_nodes_gauge.set(count)
    
    def record_network_capacity(self, model: str, capacity: int):
        """
        Record network capacity for a model.
        
        Args:
            model: Model name
            capacity: Total available slots
        """
        self.network_capacity_gauge.labels(model=model).set(capacity)
    
    def record_heartbeat_failure(self):
        """Record a heartbeat failure."""
        self.heartbeat_failures_total.inc()
    
    def record_federation_sync(self, peer_url: str, success: bool, nodes_count: int = 0):
        """
        Record federation sync metrics.
        
        Args:
            peer_url: Peer coordinator URL (will be hashed)
            success: Whether sync succeeded
            nodes_count: Number of nodes synced
        """
        peer_hash = self.hash_identifier(peer_url, prefix="peer_")
        status = "success" if success else "failure"
        
        self.federation_syncs_total.labels(
            peer_hash=peer_hash,
            status=status
        ).inc()
        
        if success and nodes_count > 0:
            self.federation_nodes_synced.labels(peer_hash=peer_hash).observe(nodes_count)
    
    def record_active_sessions(self, count: int):
        """
        Record active session count.
        
        Args:
            count: Number of active sessions
        """
        self.active_sessions_gauge.set(count)
    
    def record_session_duration(self, duration_seconds: float):
        """
        Record session duration.
        
        Args:
            duration_seconds: How long the session lasted
        """
        self.session_duration_seconds.observe(duration_seconds)
    
    def get_metrics_text(self) -> str:
        """
        Get metrics in Prometheus text format.
        
        Returns:
            Metrics as text (empty string if metrics disabled)
        """
        if not METRICS_ENABLED:
            return ""
        
        try:
            return generate_latest().decode('utf-8')
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return ""


# Global instance
_metrics_instance: Optional[PrivacyPreservingMetrics] = None


def get_metrics() -> PrivacyPreservingMetrics:
    """Get the global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = PrivacyPreservingMetrics()
    return _metrics_instance
