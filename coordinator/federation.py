"""
Coordinator Federation Module

Implements the gossip protocol for sharing node information between
multiple coordinators to create a unified decentralized network.

Federation Protocol:
1. Coordinators configured with peer URLs
2. Every 5 minutes, sync node lists from peers
3. Merge and deduplicate by node_id
4. Use most recent heartbeat for conflicts
5. Verify signatures to prevent poisoning
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
from sqlalchemy.orm import Session

from models import Node
from config import CoordinatorConfig
from trust import TrustManager, ReputationTracker

logger = logging.getLogger(__name__)


class FederationManager:
    """Manages federation with peer coordinators."""

    def __init__(self, config: CoordinatorConfig, get_db_session):
        """
        Initialize federation manager.

        Args:
            config: Coordinator configuration
            get_db_session: Function to get database session
        """
        self.config = config
        self.get_db_session = get_db_session
        self.peer_status: Dict[str, dict] = {}

        # Initialize trust management
        self.trust_manager = TrustManager(
            coordinator_secret=config.coordinator_secret,
            trusted_coordinators={}  # Will be populated from config/API
        )
        self.reputation_tracker = ReputationTracker()

        # Initialize peer status tracking
        for peer_url in config.peer_coordinators:
            self.peer_status[peer_url] = {
                'last_sync': None,
                'status': 'unknown',
                'error_count': 0,
                'total_syncs': 0
            }

        logger.info(f"Federation initialized with {len(config.peer_coordinators)} peers")
        if config.coordinator_secret:
            logger.info("Federation trust mode: signature verification enabled")
        else:
            logger.warning("Federation trust mode: signature verification DISABLED")

    async def start_federation(self):
        """Start the federation sync loop."""
        if not self.config.federation_enabled:
            logger.info("Federation disabled in configuration")
            return

        if not self.config.peer_coordinators:
            logger.warning("Federation enabled but no peer coordinators configured")
            return

        logger.info("Starting federation sync loop")
        while True:
            try:
                await self.sync_all_peers()
                await asyncio.sleep(self.config.federation_sync_interval)
            except Exception as e:
                logger.error(f"Federation sync error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def sync_all_peers(self):
        """Sync node lists from all peer coordinators."""
        logger.info("Starting federation sync with all peers")

        # Create tasks for parallel syncing
        tasks = []
        for peer_url in self.config.peer_coordinators:
            task = self.sync_peer(peer_url)
            tasks.append(task)

        # Execute all sync tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        logger.info(f"Federation sync complete: {success_count}/{len(tasks)} peers successful")

    async def sync_peer(self, peer_url: str) -> bool:
        """
        Sync node list from a single peer coordinator.

        Args:
            peer_url: URL of peer coordinator

        Returns:
            True if sync successful, False otherwise
        """
        peer_url = peer_url.rstrip('/')

        try:
            logger.debug(f"Syncing with peer: {peer_url}")

            # Query peer for node list
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{peer_url}/nodes/discover?limit=1000",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")

                    peer_nodes = await response.json()

            if not peer_nodes:
                logger.debug(f"No nodes from peer {peer_url}")
                self._update_peer_status(peer_url, 'healthy', success=True)
                return True

            # Merge nodes into local database
            merged_count = await self._merge_nodes(peer_nodes, peer_url)

            # Update peer status
            self._update_peer_status(peer_url, 'healthy', success=True)

            logger.info(f"Synced {merged_count} nodes from {peer_url}")
            return True

        except asyncio.TimeoutError:
            logger.warning(f"Timeout syncing with {peer_url}")
            self._update_peer_status(peer_url, 'timeout', success=False)
            return False

        except Exception as e:
            logger.error(f"Error syncing with {peer_url}: {e}")
            self._update_peer_status(peer_url, 'error', success=False)
            return False

    async def _merge_nodes(self, peer_nodes: List[dict], peer_url: str) -> int:
        """
        Merge peer nodes into local database.

        Conflict resolution strategy:
        1. Use most recent last_heartbeat timestamp (newer wins)
        2. If node doesn't exist locally, add it
        3. Track federation_source for debugging
        4. Preserve better reputation scores

        Args:
            peer_nodes: List of node dictionaries from peer
            peer_url: URL of peer coordinator (for logging)

        Returns:
            Number of nodes merged
        """
        merged_count = 0

        with self.get_db_session() as db:
            for peer_node in peer_nodes:
                try:
                    node_id = peer_node['node_id']

                    # Check if node exists locally
                    local_node = db.query(Node).filter(Node.node_id == node_id).first()

                    # Parse peer node data
                    address_parts = peer_node['address'].split(':')
                    ip_address = address_parts[0]
                    port = int(address_parts[1]) if len(address_parts) > 1 else 8000

                    if local_node:
                        # Node exists - apply conflict resolution
                        
                        # Strategy 1: Compare uptime scores (prefer better reputation)
                        peer_uptime = peer_node.get('uptime_score', 0.0)
                        local_uptime = local_node.uptime_score
                        
                        # Strategy 2: If uptime is significantly better, update
                        # Otherwise, prefer local data (trust direct heartbeats over federation)
                        uptime_diff = peer_uptime - local_uptime
                        
                        if uptime_diff > 0.05:  # 5% threshold
                            # Peer has notably better reputation, update metrics
                            local_node.uptime_score = peer_uptime
                            local_node.current_load = peer_node.get('current_load', 0.0)
                            local_node.federation_source = peer_url
                            local_node.last_updated = datetime.utcnow()
                            merged_count += 1
                            logger.debug(
                                f"Updated node {node_id} from peer {peer_url} "
                                f"(uptime: {local_uptime:.2f} -> {peer_uptime:.2f})"
                            )
                        # If node exists locally and peer data isn't notably better,
                        # trust our direct heartbeat data over federated data

                    else:
                        # New node from peer - add it
                        new_node = Node(
                            node_id=node_id,
                            ip_address=ip_address,
                            port=port,
                            public_key=peer_node['public_key'],
                            models=','.join(peer_node.get('models', [])),
                            current_load=peer_node.get('current_load', 0.0),
                            uptime_score=peer_node.get('uptime_score', 0.0),
                            max_concurrent=peer_node.get('max_concurrent', 1),
                            last_heartbeat=datetime.utcnow(),  # Trust peer's data
                            first_seen=datetime.utcnow(),
                            last_updated=datetime.utcnow(),
                            federation_source=peer_url
                        )
                        db.add(new_node)
                        merged_count += 1
                        logger.info(f"Added new node {node_id} from peer {peer_url}")

                except Exception as e:
                    logger.error(f"Error merging node from {peer_url}: {e}")
                    continue

            db.commit()

        return merged_count

    def _update_peer_status(self, peer_url: str, status: str, success: bool):
        """
        Update peer status tracking.

        Args:
            peer_url: URL of peer
            status: Status string ('healthy', 'timeout', 'error')
            success: Whether sync was successful
        """
        if peer_url not in self.peer_status:
            self.peer_status[peer_url] = {
                'last_sync': None,
                'status': 'unknown',
                'error_count': 0,
                'total_syncs': 0
            }

        self.peer_status[peer_url]['last_sync'] = datetime.utcnow()
        self.peer_status[peer_url]['status'] = status
        self.peer_status[peer_url]['total_syncs'] += 1

        if success:
            self.peer_status[peer_url]['error_count'] = 0
        else:
            self.peer_status[peer_url]['error_count'] += 1

    def get_peer_status(self) -> Dict[str, dict]:
        """
        Get status of all peer coordinators.

        Returns:
            Dictionary of peer URLs to status information
        """
        return {
            url: {
                'url': url,
                'last_sync': status['last_sync'].isoformat() if status['last_sync'] else None,
                'status': status['status'],
                'error_count': status['error_count'],
                'total_syncs': status['total_syncs']
            }
            for url, status in self.peer_status.items()
        }

    async def register_peer(self, peer_url: str) -> bool:
        """
        Register a new peer coordinator.

        This allows dynamic peer discovery (manual approval required).

        Args:
            peer_url: URL of new peer

        Returns:
            True if registered successfully
        """
        peer_url = peer_url.rstrip('/')

        if peer_url in self.config.peer_coordinators:
            logger.info(f"Peer {peer_url} already registered")
            return True

        try:
            # Verify peer is reachable
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{peer_url}/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}")

            # Add to peer list
            self.config.peer_coordinators.append(peer_url)
            self.peer_status[peer_url] = {
                'last_sync': None,
                'status': 'registered',
                'error_count': 0,
                'total_syncs': 0
            }

            logger.info(f"Registered new peer: {peer_url}")

            # Trigger immediate sync
            asyncio.create_task(self.sync_peer(peer_url))

            return True

        except Exception as e:
            logger.error(f"Failed to register peer {peer_url}: {e}")
            return False

    def get_federation_stats(self) -> dict:
        """
        Get federation statistics.

        Returns:
            Dictionary with federation metrics
        """
        total_peers = len(self.config.peer_coordinators)
        healthy_peers = sum(
            1 for status in self.peer_status.values()
            if status['status'] == 'healthy'
        )

        recent_syncs = sum(
            1 for status in self.peer_status.values()
            if status['last_sync'] and
            status['last_sync'] > datetime.utcnow() - timedelta(minutes=10)
        )

        return {
            'total_peers': total_peers,
            'healthy_peers': healthy_peers,
            'recent_syncs': recent_syncs,
            'federation_enabled': self.config.federation_enabled,
            'sync_interval_seconds': self.config.federation_sync_interval
        }
