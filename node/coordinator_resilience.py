"""
Coordinator Resilience and Gossip Protocol

Addresses coordinator as single point of failure:
1. Coordinator fallback (multiple coordinators)
2. Client-side node list caching
3. Gossip protocol foundation for node discovery
4. Degraded mode operation when coordinator unavailable

This ensures the network can operate even if the coordinator is down.
"""

import asyncio
import json
import time
import random
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CoordinatorEndpoint:
    """Information about a coordinator."""
    url: str
    priority: int = 1  # Lower = higher priority
    is_healthy: bool = True
    last_check: float = 0
    consecutive_failures: int = 0
    
    def mark_failure(self):
        """Record a failed health check."""
        self.is_healthy = False
        self.consecutive_failures += 1
        self.last_check = time.time()
    
    def mark_success(self):
        """Record a successful health check."""
        self.is_healthy = True
        self.consecutive_failures = 0
        self.last_check = time.time()


class CoordinatorFallbackManager:
    """
    Manages multiple coordinator endpoints with automatic failover.
    
    Clients can configure multiple coordinators. If primary fails,
    automatically falls back to secondaries.
    """
    
    def __init__(
        self,
        coordinators: List[str],
        health_check_interval: int = 60,
        unhealthy_threshold: int = 3
    ):
        """
        Initialize coordinator fallback manager.
        
        Args:
            coordinators: List of coordinator URLs
            health_check_interval: Seconds between health checks
            unhealthy_threshold: Failures before marking unhealthy
        """
        self.endpoints = [
            CoordinatorEndpoint(url=url, priority=i)
            for i, url in enumerate(coordinators)
        ]
        self.health_check_interval = health_check_interval
        self.unhealthy_threshold = unhealthy_threshold
        
        self._health_check_task: Optional[asyncio.Task] = None
    
    def get_active_coordinator(self) -> Optional[str]:
        """
        Get the highest priority healthy coordinator.
        
        Returns:
            Coordinator URL or None if all unhealthy
        """
        # Sort by priority (lower = better), then by health
        healthy = [e for e in self.endpoints if e.is_healthy]
        
        if not healthy:
            # All coordinators unhealthy - try least-failed one
            self.endpoints.sort(key=lambda e: e.consecutive_failures)
            return self.endpoints[0].url if self.endpoints else None
        
        healthy.sort(key=lambda e: e.priority)
        return healthy[0].url
    
    async def execute_with_fallback(self, operation, *args, **kwargs):
        """
        Execute operation with automatic coordinator fallback.
        
        Tries each coordinator in priority order until one succeeds.
        
        Args:
            operation: Async function to execute
            *args, **kwargs: Arguments for operation
            
        Returns:
            Operation result
            
        Raises:
            Exception: If all coordinators fail
        """
        # Try healthy coordinators first
        healthy = sorted(
            [e for e in self.endpoints if e.is_healthy],
            key=lambda e: e.priority
        )
        
        # Then unhealthy ones as last resort
        unhealthy = sorted(
            [e for e in self.endpoints if not e.is_healthy],
            key=lambda e: (e.consecutive_failures, e.priority)
        )
        
        endpoints_to_try = healthy + unhealthy
        
        last_error = None
        
        for endpoint in endpoints_to_try:
            try:
                result = await operation(endpoint.url, *args, **kwargs)
                endpoint.mark_success()
                return result
                
            except Exception as e:
                last_error = e
                endpoint.mark_failure()
                continue
        
        # All failed
        raise Exception(f"All coordinators failed. Last error: {last_error}")
    
    async def check_health(self, http_client=None):
        """Check health of all coordinators."""
        for endpoint in self.endpoints:
            try:
                # In real implementation:
                # response = await http_client.get(f"{endpoint.url}/health", timeout=5)
                # if response.status_code == 200:
                #     endpoint.mark_success()
                # else:
                #     endpoint.mark_failure()
                
                # Mock for now
                endpoint.mark_success()
                
            except Exception:
                endpoint.mark_failure()
    
    async def start_health_monitoring(self):
        """Start background health check task."""
        async def monitor():
            while True:
                await self.check_health()
                await asyncio.sleep(self.health_check_interval)
        
        self._health_check_task = asyncio.create_task(monitor())
    
    def stop_health_monitoring(self):
        """Stop background health check task."""
        if self._health_check_task:
            self._health_check_task.cancel()


class NodeListCache:
    """
    Client-side cache of node list from coordinator.
    
    Allows degraded operation when coordinator is unavailable.
    """
    
    def __init__(
        self,
        cache_file: Optional[Path] = None,
        ttl: int = 300  # 5 minutes
    ):
        """
        Initialize node list cache.
        
        Args:
            cache_file: Optional file to persist cache
            ttl: Cache time-to-live in seconds
        """
        self.cache_file = cache_file or Path.home() / ".ambient" / "node_cache.json"
        self.ttl = ttl
        
        self._nodes: List[dict] = []
        self._last_update: float = 0
        self._coordinator_source: Optional[str] = None
    
    def update(self, nodes: List[dict], source: str):
        """
        Update cache with fresh node list.
        
        Args:
            nodes: List of node dictionaries
            source: Coordinator URL that provided nodes
        """
        self._nodes = nodes
        self._last_update = time.time()
        self._coordinator_source = source
        
        # Persist to disk
        self._save_to_disk()
    
    def get_nodes(self) -> List[dict]:
        """
        Get cached nodes.
        
        Returns fresh cache if valid, or stale cache if coordinator unavailable.
        """
        return self._nodes.copy()
    
    def is_fresh(self) -> bool:
        """Check if cache is fresh (within TTL)."""
        if not self._nodes:
            return False
        
        age = time.time() - self._last_update
        return age < self.ttl
    
    def is_stale(self) -> bool:
        """Check if cache is stale but still usable."""
        return bool(self._nodes) and not self.is_fresh()
    
    def get_age(self) -> float:
        """Get cache age in seconds."""
        return time.time() - self._last_update
    
    def _save_to_disk(self):
        """Persist cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'nodes': self._nodes,
                'last_update': self._last_update,
                'coordinator_source': self._coordinator_source,
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            # Fail silently - cache persistence is optional
            pass
    
    def load_from_disk(self):
        """Load cache from disk on startup."""
        try:
            if not self.cache_file.exists():
                return
            
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            self._nodes = data.get('nodes', [])
            self._last_update = data.get('last_update', 0)
            self._coordinator_source = data.get('coordinator_source')
            
        except Exception:
            # Fail silently - cache loading is optional
            pass


class GossipProtocol:
    """
    Foundation for gossip-based node discovery.
    
    Nodes share their peer lists with each other, allowing discovery
    even when coordinator is unavailable.
    
    This is a simplified implementation. Full gossip would include:
    - Periodic peer list exchange
    - Conflict resolution
    - Anti-entropy mechanisms
    - Sybil attack prevention
    """
    
    def __init__(
        self,
        node_id: str,
        gossip_interval: int = 60,
        gossip_fanout: int = 3  # Share with N random peers
    ):
        """
        Initialize gossip protocol.
        
        Args:
            node_id: This node's ID
            gossip_interval: Seconds between gossip rounds
            gossip_fanout: Number of peers to gossip with
        """
        self.node_id = node_id
        self.gossip_interval = gossip_interval
        self.gossip_fanout = gossip_fanout
        
        self._known_peers: Dict[str, dict] = {}  # node_id -> peer_info
        self._gossip_task: Optional[asyncio.Task] = None
    
    def add_peer(self, peer_info: dict):
        """
        Add a peer to known peers list.
        
        Args:
            peer_info: Dictionary with node_id, address, public_key, etc.
        """
        node_id = peer_info.get('node_id')
        if node_id and node_id != self.node_id:
            peer_info['last_updated'] = time.time()
            self._known_peers[node_id] = peer_info
    
    def get_peers(self) -> List[dict]:
        """Get all known peers."""
        return list(self._known_peers.values())
    
    def select_gossip_targets(self) -> List[dict]:
        """
        Select random peers to gossip with.
        
        Returns:
            List of peer info dictionaries
        """
        peers = list(self._known_peers.values())
        
        if len(peers) <= self.gossip_fanout:
            return peers
        
        return random.sample(peers, self.gossip_fanout)
    
    async def gossip_round(self, http_client=None):
        """
        Perform one round of gossip.
        
        Sends our peer list to random peers and receives theirs.
        """
        targets = self.select_gossip_targets()
        
        for target in targets:
            try:
                # In real implementation:
                # 1. Send our peer list to target
                # payload = {'peers': self.get_peers(), 'from': self.node_id}
                # response = await http_client.post(
                #     f"http://{target['address']}/gossip",
                #     json=payload
                # )
                # 2. Merge their peer list into ours
                # their_peers = response.json()['peers']
                # for peer in their_peers:
                #     self.add_peer(peer)
                
                pass
                
            except Exception as e:
                # Gossip is best-effort - failures are OK
                pass
    
    async def start_gossip(self):
        """Start background gossip task."""
        async def gossip_loop():
            while True:
                await self.gossip_round()
                await asyncio.sleep(self.gossip_interval)
        
        self._gossip_task = asyncio.create_task(gossip_loop())
    
    def stop_gossip(self):
        """Stop background gossip task."""
        if self._gossip_task:
            self._gossip_task.cancel()


class DegradedModeManager:
    """
    Manages operation in degraded mode when coordinator is unavailable.
    
    Degraded mode uses:
    1. Cached node list
    2. Manual peer discovery file
    3. Gossip protocol (if implemented)
    """
    
    def __init__(
        self,
        cache: NodeListCache,
        fallback_coordinators: List[str]
    ):
        """
        Initialize degraded mode manager.
        
        Args:
            cache: Node list cache
            fallback_coordinators: List of coordinator URLs to try
        """
        self.cache = cache
        self.coordinator_fallback = CoordinatorFallbackManager(fallback_coordinators)
        self._degraded_mode = False
    
    def is_degraded(self) -> bool:
        """Check if currently in degraded mode."""
        return self._degraded_mode
    
    async def get_nodes(self) -> List[dict]:
        """
        Get node list with fallback strategy.
        
        Strategy:
        1. Try active coordinator
        2. Try fallback coordinators
        3. Use cached node list (even if stale)
        4. Use manual peer discovery file
        
        Returns:
            List of node dictionaries
        """
        # Try coordinator(s)
        try:
            async def fetch_nodes(coordinator_url):
                # In real implementation:
                # response = await http_client.get(f"{coordinator_url}/nodes")
                # return response.json()['nodes']
                return []
            
            nodes = await self.coordinator_fallback.execute_with_fallback(fetch_nodes)
            
            # Update cache with fresh data
            coordinator_url = self.coordinator_fallback.get_active_coordinator()
            self.cache.update(nodes, coordinator_url)
            
            self._degraded_mode = False
            return nodes
            
        except Exception:
            # Coordinator unavailable - enter degraded mode
            self._degraded_mode = True
        
        # Use cached nodes
        if self.cache.is_stale():
            # Log warning about using stale cache
            pass
        
        cached_nodes = self.cache.get_nodes()
        if cached_nodes:
            return cached_nodes
        
        # Last resort: empty list (client should check peer discovery file)
        return []
    
    def get_status(self) -> dict:
        """Get degraded mode status."""
        return {
            'degraded_mode': self._degraded_mode,
            'cache_age': self.cache.get_age(),
            'cache_fresh': self.cache.is_fresh(),
            'active_coordinator': self.coordinator_fallback.get_active_coordinator(),
        }


# Example usage
async def example_usage():
    """Demonstrate coordinator resilience features."""
    
    print("=== Coordinator Fallback ===")
    
    # Multiple coordinators
    coordinators = [
        "http://coordinator1.example.com:8000",
        "http://coordinator2.example.com:8000",
        "http://coordinator3.example.com:8000",
    ]
    
    fallback = CoordinatorFallbackManager(coordinators)
    
    print(f"Active coordinator: {fallback.get_active_coordinator()}")
    
    # Simulate coordinator failure
    fallback.endpoints[0].mark_failure()
    fallback.endpoints[0].mark_failure()
    fallback.endpoints[0].mark_failure()
    
    print(f"After primary failure: {fallback.get_active_coordinator()}")
    
    print("\n=== Node List Cache ===")
    
    cache = NodeListCache()
    
    # Update cache
    nodes = [
        {'node_id': 'node1', 'address': '10.0.0.1:8000'},
        {'node_id': 'node2', 'address': '10.0.0.2:8000'},
    ]
    
    cache.update(nodes, coordinators[0])
    print(f"Cache fresh: {cache.is_fresh()}")
    print(f"Cached nodes: {len(cache.get_nodes())}")
    
    print("\n=== Degraded Mode ===")
    
    degraded = DegradedModeManager(cache, coordinators)
    status = degraded.get_status()
    
    print(f"Degraded mode: {status['degraded_mode']}")
    print(f"Cache age: {status['cache_age']:.1f}s")


if __name__ == "__main__":
    asyncio.run(example_usage())
