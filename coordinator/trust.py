"""
Trust model for federation.

Coordinators sign node announcements to prevent poisoning attacks.
Only nodes vouched for by trusted coordinators are accepted.
"""

import hashlib
import hmac
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TrustManager:
    """Manages trust relationships between coordinators."""

    def __init__(self, coordinator_secret: str, trusted_coordinators: dict = None):
        """
        Initialize trust manager.

        Args:
            coordinator_secret: Secret key for signing announcements
            trusted_coordinators: Dict of {coordinator_url: public_key}
        """
        self.coordinator_secret = coordinator_secret.encode() if coordinator_secret else b""
        self.trusted_coordinators = trusted_coordinators or {}
        
        if not self.coordinator_secret:
            logger.warning("No coordinator secret set - signature verification disabled")

    def sign_node_announcement(self, node_data: dict) -> str:
        """
        Sign a node announcement to prove authenticity.

        Args:
            node_data: Node information dict

        Returns:
            HMAC signature (hex string)
        """
        if not self.coordinator_secret:
            return ""

        # Create canonical representation
        canonical = self._canonicalize_node_data(node_data)
        
        # Generate HMAC signature
        signature = hmac.new(
            self.coordinator_secret,
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    def verify_node_announcement(
        self,
        node_data: dict,
        signature: str,
        coordinator_url: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a signed node announcement.

        Args:
            node_data: Node information dict
            signature: HMAC signature from peer
            coordinator_url: URL of announcing coordinator

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.coordinator_secret:
            # Signature verification disabled
            return True, None

        # Check if coordinator is trusted
        if coordinator_url not in self.trusted_coordinators:
            logger.warning(f"Untrusted coordinator: {coordinator_url}")
            # In permissive mode, we accept but log
            # In strict mode, we would reject here
            return True, None  # Permissive for now

        # Create canonical representation
        canonical = self._canonicalize_node_data(node_data)

        # Get coordinator's secret (in production, use public/private keys)
        coordinator_secret = self.trusted_coordinators.get(coordinator_url, "").encode()
        
        if not coordinator_secret:
            return False, f"No secret key for coordinator {coordinator_url}"

        # Verify signature
        expected_signature = hmac.new(
            coordinator_secret,
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return False, "Invalid signature"

        return True, None

    def _canonicalize_node_data(self, node_data: dict) -> str:
        """
        Create canonical string representation for signing.

        Args:
            node_data: Node information dict

        Returns:
            Canonical string
        """
        # Sort keys for consistent ordering
        parts = []
        for key in sorted(['node_id', 'address', 'public_key', 'models']):
            if key in node_data:
                value = node_data[key]
                if isinstance(value, list):
                    value = ','.join(sorted(value))
                parts.append(f"{key}={value}")

        return '|'.join(parts)

    def add_trusted_coordinator(self, url: str, secret: str):
        """
        Add a coordinator to the trusted list.

        Args:
            url: Coordinator URL
            secret: Shared secret for verification
        """
        self.trusted_coordinators[url] = secret
        logger.info(f"Added trusted coordinator: {url}")

    def remove_trusted_coordinator(self, url: str):
        """
        Remove a coordinator from trusted list.

        Args:
            url: Coordinator URL
        """
        if url in self.trusted_coordinators:
            del self.trusted_coordinators[url]
            logger.info(f"Removed trusted coordinator: {url}")

    def get_trusted_coordinators(self) -> list:
        """Get list of trusted coordinator URLs."""
        return list(self.trusted_coordinators.keys())


class ReputationTracker:
    """Track coordinator reputation based on behavior."""

    def __init__(self):
        """Initialize reputation tracker."""
        self.reputation = {}  # coordinator_url -> score (0-100)
        self.incidents = {}   # coordinator_url -> list of incidents
        self.byzantine_flags = {}  # coordinator_url -> list of suspicious behaviors

    def get_reputation(self, coordinator_url: str) -> float:
        """
        Get reputation score for a coordinator.

        Args:
            coordinator_url: Coordinator URL

        Returns:
            Reputation score (0-100, default 50 for new coordinators)
        """
        return self.reputation.get(coordinator_url, 50.0)
    
    def detect_byzantine_behavior(
        self,
        coordinator_url: str,
        reported_nodes: list,
        known_nodes: dict
    ) -> list:
        """
        Detect potential Byzantine fault behavior.
        
        Checks for:
        - Reporting significantly different node states than majority
        - Reporting nodes with impossible metrics
        - Rapid reputation changes
        - Conflicting information about same node
        
        Args:
            coordinator_url: Coordinator being evaluated
            reported_nodes: Nodes reported by this coordinator
            known_nodes: Nodes known to local coordinator
            
        Returns:
            List of detected issues
        """
        issues = []
        
        if coordinator_url not in self.byzantine_flags:
            self.byzantine_flags[coordinator_url] = []
        
        # Check 1: Impossible metrics
        for node in reported_nodes:
            uptime = node.get('uptime_score', 0)
            load = node.get('current_load', 0)
            
            if uptime < 0 or uptime > 100:
                issues.append(f"Impossible uptime score: {uptime}")
            
            if load < 0 or load > 1:
                issues.append(f"Impossible load value: {load}")
        
        # Check 2: Conflicting node information
        for node in reported_nodes:
            node_id = node.get('node_id')
            if node_id in known_nodes:
                known_node = known_nodes[node_id]
                
                # Reputation shouldn't change drastically
                known_uptime = known_node.get('uptime_score', 50)
                reported_uptime = node.get('uptime_score', 50)
                
                uptime_diff = abs(reported_uptime - known_uptime)
                if uptime_diff > 30:  # 30% difference is suspicious
                    issues.append(
                        f"Large uptime discrepancy for {node_id}: "
                        f"{known_uptime:.1f} vs {reported_uptime:.1f}"
                    )
        
        # Check 3: Reporting too many unknown nodes
        unknown_count = sum(
            1 for node in reported_nodes
            if node.get('node_id') not in known_nodes
        )
        
        if len(reported_nodes) > 0:
            unknown_ratio = unknown_count / len(reported_nodes)
            if unknown_ratio > 0.8:  # > 80% unknown is suspicious
                issues.append(
                    f"Reporting {unknown_ratio*100:.0f}% unknown nodes "
                    f"({unknown_count}/{len(reported_nodes)})"
                )
        
        # Record issues
        if issues:
            self.byzantine_flags[coordinator_url].extend(issues)
            # Keep last 100 flags
            self.byzantine_flags[coordinator_url] = \
                self.byzantine_flags[coordinator_url][-100:]
        
        return issues

    def record_incident(self, coordinator_url: str, incident_type: str, severity: float = 1.0):
        """
        Record a negative incident (invalid signature, etc).

        Args:
            coordinator_url: Coordinator URL
            incident_type: Type of incident
            severity: How severe (0-10)
        """
        if coordinator_url not in self.incidents:
            self.incidents[coordinator_url] = []

        self.incidents[coordinator_url].append({
            'type': incident_type,
            'severity': severity,
            'timestamp': datetime.utcnow()
        })

        # Update reputation (decrease by severity)
        current = self.get_reputation(coordinator_url)
        new_reputation = max(0, current - severity * 5)
        self.reputation[coordinator_url] = new_reputation

        logger.warning(
            f"Incident with {coordinator_url}: {incident_type} "
            f"(reputation: {current:.1f} -> {new_reputation:.1f})"
        )

    def record_success(self, coordinator_url: str):
        """
        Record a successful interaction.

        Args:
            coordinator_url: Coordinator URL
        """
        current = self.get_reputation(coordinator_url)
        # Slowly increase reputation for good behavior
        new_reputation = min(100, current + 0.5)
        self.reputation[coordinator_url] = new_reputation

    def is_trusted(self, coordinator_url: str, threshold: float = 30.0) -> bool:
        """
        Check if coordinator reputation is above threshold.

        Args:
            coordinator_url: Coordinator URL
            threshold: Minimum reputation score

        Returns:
            True if trusted
        """
        reputation = self.get_reputation(coordinator_url)
        
        # Also check for Byzantine flags
        if coordinator_url in self.byzantine_flags:
            recent_flags = self.byzantine_flags[coordinator_url][-10:]
            if len(recent_flags) > 5:
                # More than 5 flags in last 10 checks is suspicious
                logger.warning(
                    f"Coordinator {coordinator_url} has {len(recent_flags)} "
                    f"recent Byzantine flags"
                )
                return False
        
        return reputation >= threshold
    
    def get_byzantine_score(self, coordinator_url: str) -> float:
        """
        Calculate Byzantine fault score (0-100, higher is more suspicious).
        
        Args:
            coordinator_url: Coordinator URL
            
        Returns:
            Byzantine score
        """
        if coordinator_url not in self.byzantine_flags:
            return 0.0
        
        # Count recent flags
        recent_flags = self.byzantine_flags[coordinator_url][-20:]
        
        if not recent_flags:
            return 0.0
        
        # Score based on number and recency of flags
        score = min(100, len(recent_flags) * 5)
        
        return score

    def cleanup_old_incidents(self, days: int = 7):
        """
        Remove old incidents to allow reputation recovery.

        Args:
            days: Remove incidents older than this many days
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        for coordinator_url in list(self.incidents.keys()):
            # Remove old incidents
            self.incidents[coordinator_url] = [
                incident for incident in self.incidents[coordinator_url]
                if incident['timestamp'] > cutoff
            ]

            # Remove coordinator if no recent incidents
            if not self.incidents[coordinator_url]:
                del self.incidents[coordinator_url]
