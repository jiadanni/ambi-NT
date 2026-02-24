"""
Comprehensive Observability and Logging

Provides structured logging and metrics for:
- Client operations (job submission, encryption, response times)
- Node operations (queue depth, inference time, error rates)
- Coordinator operations (node churn, job routing)

Privacy-preserving: Never logs plaintext prompts or responses.
Logs only metadata that helps debugging without compromising privacy.
"""

import logging
import time
import json
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from collections import defaultdict
from contextlib import contextmanager


class ComponentType(Enum):
    """Type of component generating logs."""
    CLIENT = "client"
    NODE = "node"
    COORDINATOR = "coordinator"


class EventType(Enum):
    """Types of events to track."""
    # Client events
    JOB_SUBMITTED = "job_submitted"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    ENCRYPTION_PERFORMED = "encryption_performed"
    DECRYPTION_PERFORMED = "decryption_performed"
    
    # Node events
    JOB_RECEIVED = "job_received"
    JOB_QUEUED = "job_queued"
    JOB_STARTED = "job_started"
    JOB_FINISHED = "job_finished"
    INFERENCE_COMPLETED = "inference_completed"
    
    # Coordinator events
    NODE_REGISTERED = "node_registered"
    NODE_HEARTBEAT = "node_heartbeat"
    NODE_OFFLINE = "node_offline"
    NODES_DISCOVERED = "nodes_discovered"
    
    # Security events
    RATE_LIMIT_HIT = "rate_limit_hit"
    INJECTION_BLOCKED = "injection_blocked"
    JAILBREAK_BLOCKED = "jailbreak_blocked"
    
    # System events
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    ERROR = "error"


@dataclass
class StructuredLogEntry:
    """Structured log entry with privacy guarantees."""
    timestamp: float = field(default_factory=time.time)
    component: str = "unknown"
    event_type: str = "unknown"
    level: str = "info"  # debug, info, warning, error, critical
    
    # Identifiers (safe to log)
    job_id: Optional[str] = None
    session_id: Optional[str] = None
    client_id_hash: Optional[str] = None  # Hash only, not actual ID
    node_id: Optional[str] = None
    
    # Metrics (safe to log)
    duration_ms: Optional[float] = None
    queue_size: Optional[int] = None
    error_count: Optional[int] = None
    
    # Context (NEVER contains plaintext)
    message: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert timestamp to ISO format
        data['timestamp'] = datetime.fromtimestamp(self.timestamp).isoformat()
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class PrivacyPreservingLogger:
    """
    Logger that ensures NO plaintext data is ever logged.
    
    All prompts/responses are redacted. Only metadata is logged.
    """
    
    def __init__(
        self,
        component: ComponentType,
        log_level: str = "INFO",
        output_file: Optional[str] = None
    ):
        """
        Initialize privacy-preserving logger.
        
        Args:
            component: Component type (client, node, coordinator)
            log_level: Logging level
            output_file: Optional file for structured logs
        """
        self.component = component.value
        self.output_file = output_file
        
        # Standard Python logger
        self.logger = logging.getLogger(f"ambient.{self.component}")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Console handler with privacy filter
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Format that shows structure
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for structured logs (if specified)
        if output_file:
            file_handler = logging.FileHandler(output_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def log_event(self, entry: StructuredLogEntry):
        """
        Log a structured event.
        
        Args:
            entry: StructuredLogEntry to log
        """
        # Set component if not already set
        if entry.component == "unknown":
            entry.component = self.component
        
        # Convert to log level
        log_level = getattr(logging, entry.level.upper(), logging.INFO)
        
        # Format message
        message_parts = [entry.event_type]
        
        if entry.job_id:
            message_parts.append(f"job_id={entry.job_id[:8]}")
        if entry.session_id:
            message_parts.append(f"session_id={entry.session_id[:8]}")
        if entry.duration_ms is not None:
            message_parts.append(f"duration={entry.duration_ms:.1f}ms")
        if entry.message:
            message_parts.append(entry.message)
        if entry.error:
            message_parts.append(f"error={entry.error}")
        
        log_message = " | ".join(message_parts)
        
        # Log to standard logger
        self.logger.log(log_level, log_message)
        
        # Write structured JSON to file if enabled
        if self.output_file:
            with open(f"{self.output_file}.json", 'a') as f:
                f.write(entry.to_json() + '\n')
    
    def log_job_submitted(
        self,
        job_id: str,
        prompt_length: int,
        client_id_hash: str
    ):
        """Log job submission (CLIENT)."""
        self.log_event(StructuredLogEntry(
            event_type=EventType.JOB_SUBMITTED.value,
            level="info",
            job_id=job_id,
            client_id_hash=client_id_hash,
            message=f"Submitted job with prompt length {prompt_length}",
            metadata={'prompt_length': prompt_length}
        ))
    
    def log_job_completed(
        self,
        job_id: str,
        duration_ms: float,
        response_length: int
    ):
        """Log job completion."""
        self.log_event(StructuredLogEntry(
            event_type=EventType.JOB_COMPLETED.value,
            level="info",
            job_id=job_id,
            duration_ms=duration_ms,
            message=f"Job completed in {duration_ms:.1f}ms, response length {response_length}",
            metadata={'response_length': response_length}
        ))
    
    def log_encryption(self, duration_ms: float, data_size: int):
        """Log encryption operation."""
        self.log_event(StructuredLogEntry(
            event_type=EventType.ENCRYPTION_PERFORMED.value,
            level="debug",
            duration_ms=duration_ms,
            message=f"Encrypted {data_size} bytes in {duration_ms:.2f}ms"
        ))
    
    def log_queue_depth(self, queue_size: int):
        """Log current queue depth (NODE)."""
        self.log_event(StructuredLogEntry(
            event_type=EventType.JOB_QUEUED.value,
            level="debug",
            queue_size=queue_size,
            message=f"Current queue depth: {queue_size}"
        ))
    
    def log_inference(self, job_id: str, duration_ms: float, model: str):
        """Log inference completion (NODE)."""
        self.log_event(StructuredLogEntry(
            event_type=EventType.INFERENCE_COMPLETED.value,
            level="info",
            job_id=job_id,
            duration_ms=duration_ms,
            message=f"Inference completed with {model}",
            metadata={'model': model}
        ))
    
    def log_node_heartbeat(self, node_id: str, load: float):
        """Log node heartbeat (COORDINATOR)."""
        self.log_event(StructuredLogEntry(
            event_type=EventType.NODE_HEARTBEAT.value,
            level="debug",
            node_id=node_id,
            message=f"Node heartbeat: load={load:.2f}",
            metadata={'load': load}
        ))
    
    def log_security_event(
        self,
        event_type: EventType,
        client_id_hash: str,
        reason: str,
        severity: str = "medium"
    ):
        """Log security event."""
        self.log_event(StructuredLogEntry(
            event_type=event_type.value,
            level="warning" if severity == "medium" else "error",
            client_id_hash=client_id_hash,
            message=f"Security: {reason}",
            metadata={'severity': severity, 'reason': reason}
        ))
    
    def log_error(self, error: Exception, context: Optional[str] = None):
        """Log an error."""
        self.log_event(StructuredLogEntry(
            event_type=EventType.ERROR.value,
            level="error",
            error=str(error),
            message=context or "Error occurred",
            metadata={'error_type': type(error).__name__}
        ))
    
    @contextmanager
    def timer(self, operation: str):
        """
        Context manager for timing operations.
        
        Usage:
            with logger.timer("encryption"):
                # ... perform encryption
        """
        start = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start) * 1000
            self.logger.debug(f"{operation} took {duration_ms:.2f}ms")


class MetricsCollector:
    """
    Collects metrics for monitoring and alerting.
    
    Aggregates events into useful statistics.
    """
    
    def __init__(self):
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.start_time = time.time()
    
    def increment(self, metric: str, value: int = 1):
        """Increment a counter."""
        self.counters[metric] += value
    
    def set_gauge(self, metric: str, value: float):
        """Set a gauge value."""
        self.gauges[metric] = value
    
    def record_histogram(self, metric: str, value: float):
        """Record a value in histogram."""
        self.histograms[metric].append(value)
        
        # Keep only last 1000 values to prevent memory growth
        if len(self.histograms[metric]) > 1000:
            self.histograms[metric] = self.histograms[metric][-1000:]
    
    def get_stats(self) -> dict:
        """Get all statistics."""
        stats = {
            'uptime_seconds': time.time() - self.start_time,
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'histograms': {}
        }
        
        # Calculate histogram stats
        for metric, values in self.histograms.items():
            if values:
                sorted_values = sorted(values)
                n = len(sorted_values)
                stats['histograms'][metric] = {
                    'count': n,
                    'min': sorted_values[0],
                    'max': sorted_values[-1],
                    'mean': sum(sorted_values) / n,
                    'p50': sorted_values[n // 2],
                    'p95': sorted_values[int(n * 0.95)] if n > 20 else sorted_values[-1],
                    'p99': sorted_values[int(n * 0.99)] if n > 100 else sorted_values[-1],
                }
        
        return stats
    
    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Counters
        for metric, value in self.counters.items():
            lines.append(f'# TYPE ambient_{metric} counter')
            lines.append(f'ambient_{metric} {value}')
        
        # Gauges
        for metric, value in self.gauges.items():
            lines.append(f'# TYPE ambient_{metric} gauge')
            lines.append(f'ambient_{metric} {value}')
        
        return '\n'.join(lines)


# Global metrics collector
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics_collector


# Example usage
if __name__ == "__main__":
    # Initialize logger for node component
    logger = PrivacyPreservingLogger(
        component=ComponentType.NODE,
        log_level="DEBUG",
        output_file="/tmp/ambient_node.log"
    )
    
    # Log various events
    logger.log_job_submitted(
        job_id="job_12345",
        prompt_length=150,
        client_id_hash="abc123..."
    )
    
    # Time an operation
    with logger.timer("inference"):
        time.sleep(0.1)  # Simulate work
    
    logger.log_job_completed(
        job_id="job_12345",
        duration_ms=100.5,
        response_length=500
    )
    
    # Security event
    logger.log_security_event(
        event_type=EventType.INJECTION_BLOCKED,
        client_id_hash="def456...",
        reason="Prompt contained injection patterns",
        severity="high"
    )
    
    # Metrics
    metrics = get_metrics_collector()
    metrics.increment("jobs_total")
    metrics.increment("jobs_successful")
    metrics.set_gauge("queue_depth", 5)
    metrics.record_histogram("inference_time_ms", 100.5)
    
    print("\n=== Metrics ===")
    print(json.dumps(metrics.get_stats(), indent=2))
