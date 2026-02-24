"""
Database models for the Ambient Intelligence Coordinator.

The coordinator maintains minimal state:
- List of online nodes (with heartbeat tracking)
- Blocklist of abusive IPs
- Priority token balances

Privacy Note:
- Coordinator NEVER sees encrypted prompts or responses
- Only metadata: node status, IP addresses, reputation scores
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Node(Base):
    """
    Represents an active node in the network.

    Nodes send heartbeats every 60 seconds. If no heartbeat for 90 seconds,
    they're considered offline and removed from discovery.
    """
    __tablename__ = 'nodes'

    # Identity
    node_id = Column(String(36), primary_key=True)  # UUID
    ip_address = Column(String(45))  # IPv6 compatible
    port = Column(Integer, default=8000)
    public_key = Column(String(100), nullable=False)

    # Capabilities
    models = Column(String(500))  # Comma-separated list of supported models
    max_concurrent = Column(Integer, default=1)

    # Status
    current_load = Column(Float, default=0.0)  # 0.0 to 1.0 (percentage)
    uptime_score = Column(Float, default=0.0)  # Reputation metric (0-100)
    total_jobs_completed = Column(Integer, default=0)
    total_jobs_failed = Column(Integer, default=0)

    # Heartbeat signature key (Ed25519 public key)
    signature_public_key = Column(String(100))

    # Timing
    last_heartbeat = Column(DateTime, default=datetime.utcnow, nullable=False)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Federation tracking
    federation_source = Column(String(200))  # URL of coordinator that reported this node

    # Metadata
    version = Column(String(20))  # Node software version

    # Indexes for fast queries
    __table_args__ = (
        Index('idx_last_heartbeat', 'last_heartbeat'),
        Index('idx_uptime_score', 'uptime_score'),
        Index('idx_current_load', 'current_load'),
        Index('idx_models', 'models'),  # For model-based discovery
    )

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'node_id': self.node_id,
            'address': f"{self.ip_address}:{self.port}",
            'public_key': self.public_key,
            'models': self.models.split(',') if self.models else [],
            'current_load': self.current_load,
            'uptime_score': self.uptime_score,
            'max_concurrent': self.max_concurrent,
            'total_jobs': self.total_jobs_completed + self.total_jobs_failed,
            'success_rate': self._calculate_success_rate(),
        }

    def _calculate_success_rate(self):
        """Calculate job success rate."""
        total = self.total_jobs_completed + self.total_jobs_failed
        if total == 0:
            return 1.0
        return self.total_jobs_completed / total


class Blocklist(Base):
    """
    IPs that have been blocked for abuse.

    Nodes can report abusive IPs. Multiple reports trigger automatic blocking.
    Blocks expire after a set time period.
    """
    __tablename__ = 'blocklist'

    ip_address = Column(String(45), primary_key=True)
    reason = Column(String(200), nullable=False)
    reporter_node_id = Column(String(36))
    report_count = Column(Integer, default=1)

    # Timing
    blocked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime)  # Temporary blocks expire

    # Severity
    is_permanent = Column(Boolean, default=False)

    # Indexes
    __table_args__ = (
        Index('idx_blocklist_expires_at', 'expires_at'),
        Index('idx_blocklist_blocked_at', 'blocked_at'),
    )


class PriorityTokenLedger(Base):
    """
    Tracks priority token balances.

    Users earn tokens by contributing compute (running nodes).
    Users spend tokens to get priority processing.

    Phase 2: Basic implementation
    Phase 3: More sophisticated economics
    """
    __tablename__ = 'priority_tokens'

    # Identity (can be node_id for operators, or unique client ID)
    user_id = Column(String(36), primary_key=True)

    # Balances
    balance = Column(Integer, default=0)
    total_earned = Column(Integer, default=0)
    total_spent = Column(Integer, default=0)

    # Timing
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Metadata
    is_node_operator = Column(Boolean, default=False)

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'user_id': self.user_id,
            'balance': self.balance,
            'total_earned': self.total_earned,
            'total_spent': self.total_spent,
            'is_node_operator': self.is_node_operator,
        }


class AbuseReport(Base):
    """
    Individual abuse reports before they trigger a block.

    Allows tracking of patterns and preventing false positives.
    """
    __tablename__ = 'abuse_reports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(45), nullable=False)
    reporter_node_id = Column(String(36), nullable=False)
    reason = Column(Text, nullable=False)
    severity = Column(String(20), default='low')  # low, medium, high, critical

    # Timing
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Status
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)

    # Indexes
    __table_args__ = (
        Index('idx_ip_address', 'ip_address'),
        Index('idx_reported_at', 'reported_at'),
        Index('idx_is_resolved', 'is_resolved'),
    )


class SessionMetadata(Base):
    """
    Lightweight session tracking for node affinity routing.
    
    Coordinator doesn't see session content (encrypted), but tracks:
    - Which node is handling a session
    - Session lifespan for cleanup
    - Basic metrics for optimization
    
    This enables consistent routing for multi-turn conversations.
    """
    __tablename__ = 'sessions'
    
    # Identity
    session_id = Column(String(36), primary_key=True)  # UUID from client
    client_id_hash = Column(String(64), nullable=False)  # SHA256 of client pubkey
    
    # Node affinity
    assigned_node_id = Column(String(36), nullable=False, index=True)
    
    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    # Metrics (for optimization, no privacy leak)
    message_count = Column(Integer, default=0)
    
    # Indexes
    __table_args__ = (
        Index('idx_sessions_expires_at', 'expires_at'),
        Index('idx_client_id_hash', 'client_id_hash'),
        Index('idx_last_activity', 'last_activity'),
    )
    
    def is_expired(self):
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'session_id': self.session_id,
            'assigned_node_id': self.assigned_node_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'message_count': self.message_count,
        }


class CoordinatorStats(Base):
    """
    Aggregate statistics for the coordinator.

    Tracks network health and growth over time.
    """
    __tablename__ = 'coordinator_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Network metrics
    total_nodes_ever = Column(Integer, default=0)
    active_nodes = Column(Integer, default=0)
    total_jobs_processed = Column(Integer, default=0)
    active_sessions = Column(Integer, default=0)

    # Timing
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_recorded_at', 'recorded_at'),
    )
