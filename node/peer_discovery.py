"""
Peer Discovery and Health Monitoring

Implements:
1. Peer discovery file (~/.ambient/peers.json) for manual node management
2. Health check endpoints and monitoring
3. Node status tracking and reporting
4. Automatic node list updates

This allows clients/nodes to operate without hardcoded addresses.
"""

import os
import json
import asyncio
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class PeerNode:
    """Information about a peer node."""
    node_id: str
    address: str  # host:port
    public_key: str
    models: List[str] = field(default_factory=list)
    
    # Health metrics
    last_seen: float = field(default_factory=time.time)
    is_healthy: bool = True
    load: float = 0.0  # 0.0 to 1.0
    uptime_score: float = 1.0
    
    # Discovery metadata
    discovered_from: str = "manual"  # manual, coordinator, gossip
    verified: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'node_id': self.node_id,
            'address': self.address,
            'public_key': self.public_key,
            'models': self.models,
            'last_seen': self.last_seen,
            'is_healthy': self.is_healthy,
            'load': self.load,
            'uptime_score': self.uptime_score,
            'discovered_from': self.discovered_from,
            'verified': self.verified,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PeerNode':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PeerDiscoveryFile:
    """
    Manages ~/.ambient/peers.json for peer discovery.
    
    This file allows users to manually add/remove nodes without rebuilding.
    Format:
    {
        "nodes": [
            {
                "node_id": "alice",
                "address": "100.64.0.1:8080",
                "public_key": "base64...",
                "models": ["llama3:8b"]
            }
        ]
    }
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize peer discovery file manager.
        
        Args:
            config_dir: Custom config directory, or None for default (~/.ambient)
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".ambient"
        
        self.peers_file = self.config_dir / "peers.json"
        self._ensure_config_dir()
    
    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_peers(self) -> List[PeerNode]:
        """
        Load peers from file.
        
        Returns:
            List of PeerNode objects
        """
        if not self.peers_file.exists():
            return []
        
        try:
            with open(self.peers_file, 'r') as f:
                data = json.load(f)
            
            peers = []
            for node_data in data.get('nodes', []):
                try:
                    peer = PeerNode.from_dict(node_data)
                    peers.append(peer)
                except Exception as e:
                    # Skip invalid entries
                    print(f"Warning: Skipping invalid peer entry: {e}")
            
            return peers
            
        except json.JSONDecodeError as e:
            print(f"Error parsing peers file: {e}")
            return []
        except Exception as e:
            print(f"Error loading peers: {e}")
            return []
    
    def save_peers(self, peers: List[PeerNode]):
        """
        Save peers to file.
        
        Args:
            peers: List of PeerNode objects
        """
        try:
            data = {
                'version': '1.0',
                'updated_at': datetime.utcnow().isoformat(),
                'nodes': [peer.to_dict() for peer in peers]
            }
            
            # Write atomically (write to temp file, then rename)
            temp_file = self.peers_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            temp_file.replace(self.peers_file)
            
        except Exception as e:
            print(f"Error saving peers: {e}")
            raise
    
    def add_peer(self, peer: PeerNode) -> bool:
        """
        Add a peer to the file.
        
        Returns:
            True if added, False if already exists
        """
        peers = self.load_peers()
        
        # Check if already exists
        for existing in peers:
            if existing.node_id == peer.node_id:
                # Update existing
                existing.address = peer.address
                existing.public_key = peer.public_key
                existing.models = peer.models
                existing.last_seen = time.time()
                self.save_peers(peers)
                return False
        
        # Add new peer
        peer.discovered_from = "manual"
        peers.append(peer)
        self.save_peers(peers)
        return True
    
    def remove_peer(self, node_id: str) -> bool:
        """
        Remove a peer from the file.
        
        Returns:
            True if removed, False if not found
        """
        peers = self.load_peers()
        original_count = len(peers)
        peers = [p for p in peers if p.node_id != node_id]
        
        if len(peers) < original_count:
            self.save_peers(peers)
            return True
        return False
    
    def get_peer(self, node_id: str) -> Optional[PeerNode]:
        """Get a specific peer by ID."""
        peers = self.load_peers()
        for peer in peers:
            if peer.node_id == node_id:
                return peer
        return None
    
    def update_health(self, node_id: str, is_healthy: bool, load: float = 0.0):
        """Update health status for a peer."""
        peers = self.load_peers()
        for peer in peers:
            if peer.node_id == node_id:
                peer.is_healthy = is_healthy
                peer.load = load
                peer.last_seen = time.time()
                break
        self.save_peers(peers)


@dataclass
class HealthStatus:
    """Health check response."""
    status: str  # "ok", "degraded", "unhealthy"
    load: float  # 0.0 to 1.0
    queue_size: int
    models: List[str]
    uptime_seconds: float
    version: str = "0.3.0"
    
    # Optional details
    memory_mb: Optional[int] = None
    active_jobs: Optional[int] = None
    completed_jobs: Optional[int] = None
    failed_jobs: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class HealthChecker:
    """
    Monitors health of nodes.
    
    Periodically checks nodes and updates their health status.
    """
    
    def __init__(
        self,
        check_interval: int = 30,  # Check every 30 seconds
        timeout: int = 5,  # 5 second timeout
        unhealthy_threshold: int = 3  # Mark unhealthy after 3 failures
    ):
        """
        Initialize health checker.
        
        Args:
            check_interval: Seconds between health checks
            timeout: Timeout for health check requests
            unhealthy_threshold: Failed checks before marking unhealthy
        """
        self.check_interval = check_interval
        self.timeout = timeout
        self.unhealthy_threshold = unhealthy_threshold
        
        self._failure_counts: Dict[str, int] = {}
        self._last_check: Dict[str, float] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def check_node_health(
        self,
        address: str,
        http_client = None
    ) -> Optional[HealthStatus]:
        """
        Check health of a single node.
        
        Args:
            address: Node address (host:port)
            http_client: Optional HTTP client (for actual implementation)
            
        Returns:
            HealthStatus or None if unreachable
        """
        try:
            # In real implementation, would make HTTP request:
            # response = await http_client.get(f"http://{address}/health", timeout=self.timeout)
            # data = response.json()
            # return HealthStatus(**data)
            
            # Mock for now
            return HealthStatus(
                status="ok",
                load=0.3,
                queue_size=5,
                models=["llama3:8b"],
                uptime_seconds=3600.0
            )
            
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            print(f"Health check failed for {address}: {e}")
            return None
    
    async def check_all_peers(
        self,
        peers: List[PeerNode],
        discovery: PeerDiscoveryFile
    ):
        """
        Check health of all peers and update discovery file.
        
        Args:
            peers: List of peers to check
            discovery: PeerDiscoveryFile to update
        """
        for peer in peers:
            health = await self.check_node_health(peer.address)
            
            if health is None:
                # Failed health check
                self._failure_counts[peer.node_id] = self._failure_counts.get(peer.node_id, 0) + 1
                
                if self._failure_counts[peer.node_id] >= self.unhealthy_threshold:
                    peer.is_healthy = False
            else:
                # Successful health check
                self._failure_counts[peer.node_id] = 0
                peer.is_healthy = True
                peer.load = health.load
                peer.models = health.models
            
            peer.last_seen = time.time()
            self._last_check[peer.node_id] = time.time()
        
        # Save updated health status
        discovery.save_peers(peers)
    
    async def start_monitoring(self, discovery: PeerDiscoveryFile):
        """
        Start background health monitoring.
        
        Args:
            discovery: PeerDiscoveryFile to monitor
        """
        self._running = True
        
        while self._running:
            try:
                peers = discovery.load_peers()
                await self.check_all_peers(peers, discovery)
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in health monitoring: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop background health monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()


class NodeSelector:
    """
    Select best node for job submission based on health and load.
    """
    
    @staticmethod
    def select_best_node(
        peers: List[PeerNode],
        required_model: Optional[str] = None,
        prefer_low_load: bool = True
    ) -> Optional[PeerNode]:
        """
        Select best node from peer list.
        
        Args:
            peers: Available peers
            required_model: Optional model requirement
            prefer_low_load: Prefer nodes with lower load
            
        Returns:
            Selected PeerNode or None
        """
        # Filter healthy nodes
        candidates = [p for p in peers if p.is_healthy]
        
        if not candidates:
            return None
        
        # Filter by model if required
        if required_model:
            candidates = [
                p for p in candidates
                if required_model in p.models
            ]
        
        if not candidates:
            return None
        
        # Sort by load (lower is better) and uptime score (higher is better)
        if prefer_low_load:
            candidates.sort(key=lambda p: (p.load, -p.uptime_score))
        else:
            # Random selection for load balancing
            import random
            return random.choice(candidates)
        
        return candidates[0]


# Example usage
async def example_usage():
    """Demonstrate peer discovery and health checking."""
    
    # Initialize discovery
    discovery = PeerDiscoveryFile()
    
    # Add some peers
    peer1 = PeerNode(
        node_id="alice",
        address="100.64.0.1:8080",
        public_key="pubkey1",
        models=["llama3:8b"]
    )
    
    peer2 = PeerNode(
        node_id="bob",
        address="100.64.0.2:8080",
        public_key="pubkey2",
        models=["llama3:8b", "mixtral:8x7b"]
    )
    
    discovery.add_peer(peer1)
    discovery.add_peer(peer2)
    
    print("Peers saved to:", discovery.peers_file)
    
    # Load and display
    peers = discovery.load_peers()
    print(f"\nLoaded {len(peers)} peers:")
    for peer in peers:
        print(f"  - {peer.node_id} @ {peer.address} (models: {peer.models})")
    
    # Health checking
    checker = HealthChecker(check_interval=30)
    
    print("\nChecking health...")
    await checker.check_all_peers(peers, discovery)
    
    # Select best node
    best = NodeSelector.select_best_node(peers, required_model="llama3:8b")
    if best:
        print(f"\nBest node: {best.node_id} @ {best.address} (load: {best.load:.2f})")


if __name__ == "__main__":
    asyncio.run(example_usage())
