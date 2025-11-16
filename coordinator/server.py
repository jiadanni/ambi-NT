"""
Ambient Intelligence Coordinator Service

This is a minimal discovery service that:
1. Maintains a list of online nodes (via heartbeats)
2. Serves this list to clients for node discovery
3. Manages a simple priority token economy
4. Handles abuse reporting and IP blocking
5. (Phase 3) Federates with other coordinators

Privacy Guarantee:
- Coordinator NEVER sees encrypted prompts or responses
- Only sees metadata: node status, IP addresses, reputation
"""

import os
import sys
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel, Field

from coordinator.config import CoordinatorConfig
from coordinator.database import Database, get_db
from coordinator.models import Node, Blocklist, AbuseReport, PriorityTokenLedger, CoordinatorStats
from coordinator.federation import FederationManager

# Configure logging
config = CoordinatorConfig()
log_level = logging.DEBUG if config.enable_debug_logs else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
database = Database(config.database_url)

# Initialize federation manager
federation_manager = FederationManager(config, database.get_session)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the FastAPI application."""
    # Startup
    logger.info("Starting Ambient Intelligence Coordinator...")

    # Validate configuration
    is_valid, error = config.validate()
    if not is_valid:
        logger.error(f"Configuration error: {error}")
        sys.exit(1)

    # Create database tables
    try:
        database.create_tables()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

    logger.info(f"Coordinator listening on {config.host}:{config.coordinator_port}")
    logger.info(f"Node heartbeat timeout: {config.node_heartbeat_timeout}s")
    logger.info(f"Priority tokens enabled: {config.enable_priority_tokens}")
    logger.info(f"Abuse detection enabled: {config.enable_abuse_detection}")

    # Start background tasks
    asyncio.create_task(cleanup_stale_nodes())
    asyncio.create_task(update_statistics())

    # Start federation if enabled
    if config.federation_enabled and config.peer_coordinators:
        logger.info(f"Federation enabled with {len(config.peer_coordinators)} peers")
        asyncio.create_task(federation_manager.start_federation())

    yield

    # Shutdown
    logger.info("Shutting down Ambient Intelligence Coordinator...")
    database.close()


# Initialize FastAPI app
app = FastAPI(
    title="Ambient Intelligence Coordinator",
    description="Decentralized node discovery and coordination service",
    version="0.2.0",
    lifespan=lifespan
)

# Enable CORS
if config.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============================================
# Request/Response Models
# ============================================

class NodeHeartbeat(BaseModel):
    """Heartbeat message sent by nodes."""
    node_id: str = Field(..., description="Unique node identifier (UUID)")
    ip_address: str = Field(..., description="Node's IP address")
    port: int = Field(8000, description="Node's port")
    public_key: str = Field(..., description="Node's public encryption key")
    models: List[str] = Field(..., description="Supported AI models")
    max_concurrent: int = Field(1, description="Max concurrent jobs")
    current_load: float = Field(0.0, description="Current load (0.0-1.0)")
    version: Optional[str] = Field(None, description="Node software version")


class NodeInfo(BaseModel):
    """Node information returned by discovery."""
    node_id: str
    address: str  # ip:port
    public_key: str
    models: List[str]
    current_load: float
    uptime_score: float
    max_concurrent: int
    success_rate: float


class ReportAbuseRequest(BaseModel):
    """Abuse report from a node."""
    ip_address: str
    reason: str
    reporter_node_id: str
    severity: str = "medium"  # low, medium, high, critical


class TokenBalanceResponse(BaseModel):
    """Priority token balance."""
    user_id: str
    balance: int
    total_earned: int
    total_spent: int
    is_node_operator: bool


# ============================================
# Endpoints
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/nodes/announce")
async def announce_node(
    heartbeat: NodeHeartbeat,
    db: Session = Depends(lambda: database.get_session_direct())
):
    """
    Nodes call this every 60 seconds to stay in the active pool.

    This is the only way nodes become discoverable. If they stop
    sending heartbeats, they're automatically removed after timeout.
    """
    try:
        # Check if node exists
        node = db.query(Node).filter(Node.node_id == heartbeat.node_id).first()

        if node:
            # Update existing node
            node.ip_address = heartbeat.ip_address
            node.port = heartbeat.port
            node.public_key = heartbeat.public_key
            node.models = ','.join(heartbeat.models)
            node.max_concurrent = heartbeat.max_concurrent
            node.current_load = heartbeat.current_load
            node.last_heartbeat = datetime.utcnow()
            if heartbeat.version:
                node.version = heartbeat.version

            # Update uptime score (increases over time)
            node.uptime_score = min(100.0, node.uptime_score + 0.1)

            logger.debug(f"Updated node {heartbeat.node_id}")
        else:
            # Register new node
            node = Node(
                node_id=heartbeat.node_id,
                ip_address=heartbeat.ip_address,
                port=heartbeat.port,
                public_key=heartbeat.public_key,
                models=','.join(heartbeat.models),
                max_concurrent=heartbeat.max_concurrent,
                current_load=heartbeat.current_load,
                uptime_score=0.0,
                last_heartbeat=datetime.utcnow(),
                version=heartbeat.version
            )
            db.add(node)

            # If priority tokens enabled, create ledger entry
            if config.enable_priority_tokens:
                token_entry = PriorityTokenLedger(
                    user_id=heartbeat.node_id,
                    balance=0,
                    is_node_operator=True
                )
                db.add(token_entry)

            logger.info(f"New node registered: {heartbeat.node_id}")

        db.commit()

        return {"status": "ok", "node_id": heartbeat.node_id}

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing heartbeat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/nodes/discover", response_model=List[NodeInfo])
async def discover_nodes(
    model: Optional[str] = None,
    min_uptime: float = 0.0,
    limit: int = 10,
    db: Session = Depends(lambda: database.get_session_direct())
):
    """
    Clients call this to find available nodes.

    Returns nodes that:
    - Have sent a heartbeat in the last timeout period
    - Match the requested model (if specified)
    - Have uptime score above threshold
    - Are not overloaded (current_load < 0.9)

    Results are sorted by: uptime score DESC, current load ASC
    """
    try:
        # Find nodes that are still alive
        cutoff = datetime.utcnow() - timedelta(seconds=config.node_heartbeat_timeout)

        query = db.query(Node).filter(
            and_(
                Node.last_heartbeat >= cutoff,
                Node.current_load < 0.9,
                Node.uptime_score >= min_uptime
            )
        )

        # Filter by model if specified
        if model:
            query = query.filter(Node.models.contains(model))

        # Sort by reputation, then by load
        nodes = query.order_by(
            Node.uptime_score.desc(),
            Node.current_load.asc()
        ).limit(limit).all()

        # Convert to response format
        result = []
        for node in nodes:
            result.append(NodeInfo(
                node_id=node.node_id,
                address=f"{node.ip_address}:{node.port}",
                public_key=node.public_key,
                models=node.models.split(',') if node.models else [],
                current_load=node.current_load,
                uptime_score=node.uptime_score,
                max_concurrent=node.max_concurrent,
                success_rate=node._calculate_success_rate()
            ))

        logger.debug(f"Discovery returned {len(result)} nodes")
        return result

    except Exception as e:
        logger.error(f"Discovery error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/abuse/report")
async def report_abuse(
    report: ReportAbuseRequest,
    db: Session = Depends(lambda: database.get_session_direct())
):
    """
    Nodes can report abusive IPs.

    If an IP gets reported by multiple nodes (threshold), it's auto-blocked.
    This is gossip-based reputation without central authority.
    """
    if not config.enable_abuse_detection:
        raise HTTPException(status_code=404, detail="Abuse detection not enabled")

    try:
        # Check if already blocked
        existing_block = db.query(Blocklist).filter(
            Blocklist.ip_address == report.ip_address
        ).first()

        if existing_block:
            return {"status": "already_blocked"}

        # Verify reporter is a known node
        reporter = db.query(Node).filter(
            Node.node_id == report.reporter_node_id
        ).first()

        if not reporter or reporter.uptime_score < config.min_uptime_for_discovery:
            logger.warning(f"Abuse report from untrusted node: {report.reporter_node_id}")
            return {"status": "reporter_not_trusted"}

        # Create abuse report
        abuse_report = AbuseReport(
            ip_address=report.ip_address,
            reporter_node_id=report.reporter_node_id,
            reason=report.reason,
            severity=report.severity
        )
        db.add(abuse_report)

        # Count total reports for this IP
        report_count = db.query(AbuseReport).filter(
            and_(
                AbuseReport.ip_address == report.ip_address,
                AbuseReport.is_resolved == False
            )
        ).count()

        # If threshold reached, block the IP
        if report_count >= config.abuse_report_threshold:
            blocklist_entry = Blocklist(
                ip_address=report.ip_address,
                reason=f"Multiple abuse reports: {report.reason}",
                reporter_node_id=report.reporter_node_id,
                report_count=report_count,
                blocked_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=config.abuse_block_duration_hours)
            )
            db.add(blocklist_entry)

            logger.warning(f"IP {report.ip_address} auto-blocked after {report_count} reports")

        db.commit()

        return {
            "status": "reported",
            "total_reports": report_count,
            "threshold": config.abuse_report_threshold
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing abuse report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/abuse/check/{ip_address}")
async def check_blocklist(
    ip_address: str,
    db: Session = Depends(lambda: database.get_session_direct())
):
    """Check if an IP is currently blocked."""
    try:
        blocked = db.query(Blocklist).filter(
            and_(
                Blocklist.ip_address == ip_address,
                or_(
                    Blocklist.is_permanent == True,
                    Blocklist.expires_at > datetime.utcnow()
                )
            )
        ).first()

        if blocked:
            return {
                "blocked": True,
                "reason": blocked.reason,
                "expires_at": blocked.expires_at.isoformat() if blocked.expires_at else None,
                "is_permanent": blocked.is_permanent
            }

        return {"blocked": False}

    except Exception as e:
        logger.error(f"Error checking blocklist: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/tokens/{user_id}", response_model=TokenBalanceResponse)
async def get_token_balance(
    user_id: str,
    db: Session = Depends(lambda: database.get_session_direct())
):
    """Get priority token balance for a user."""
    if not config.enable_priority_tokens:
        raise HTTPException(status_code=404, detail="Priority tokens not enabled")

    try:
        ledger = db.query(PriorityTokenLedger).filter(
            PriorityTokenLedger.user_id == user_id
        ).first()

        if not ledger:
            # Create new ledger entry
            ledger = PriorityTokenLedger(
                user_id=user_id,
                balance=0,
                is_node_operator=False
            )
            db.add(ledger)
            db.commit()

        return TokenBalanceResponse(**ledger.to_dict())

    except Exception as e:
        logger.error(f"Error getting token balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/stats")
async def get_statistics(db: Session = Depends(lambda: database.get_session_direct())):
    """Get network statistics."""
    try:
        # Count active nodes
        cutoff = datetime.utcnow() - timedelta(seconds=config.node_heartbeat_timeout)
        active_nodes = db.query(Node).filter(
            Node.last_heartbeat >= cutoff
        ).count()

        # Total nodes ever
        total_nodes_ever = db.query(Node).count()

        # Total jobs processed
        total_jobs = db.query(Node).with_entities(
            Node.total_jobs_completed,
            Node.total_jobs_failed
        ).all()

        total_completed = sum(j[0] for j in total_jobs)
        total_failed = sum(j[1] for j in total_jobs)

        return {
            "active_nodes": active_nodes,
            "total_nodes_ever": total_nodes_ever,
            "total_jobs_completed": total_completed,
            "total_jobs_failed": total_failed,
            "success_rate": total_completed / (total_completed + total_failed) if (total_completed + total_failed) > 0 else 0,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============================================
# Federation Endpoints (Phase 3)
# ============================================

@app.get("/federation/peers")
async def get_federation_peers():
    """Get list of peer coordinators and their status."""
    if not config.federation_enabled:
        raise HTTPException(status_code=404, detail="Federation not enabled")

    peer_status = federation_manager.get_peer_status()
    fed_stats = federation_manager.get_federation_stats()

    return {
        "peers": list(peer_status.values()),
        "stats": fed_stats
    }


@app.post("/federation/register")
async def register_federation_peer(request: dict):
    """
    Register a new peer coordinator.

    Requires manual approval (admin token).
    """
    if not config.federation_enabled:
        raise HTTPException(status_code=404, detail="Federation not enabled")

    peer_url = request.get('url')
    if not peer_url:
        raise HTTPException(status_code=400, detail="URL required")

    # Verify admin token if configured
    if config.admin_token:
        auth_header = request.get('admin_token')
        if auth_header != config.admin_token:
            raise HTTPException(status_code=403, detail="Invalid admin token")

    success = await federation_manager.register_peer(peer_url)

    if success:
        return {"status": "registered", "peer_url": peer_url}
    else:
        raise HTTPException(status_code=500, detail="Failed to register peer")


@app.get("/federation/stats")
async def get_federation_stats():
    """Get federation statistics."""
    if not config.federation_enabled:
        raise HTTPException(status_code=404, detail="Federation not enabled")

    return federation_manager.get_federation_stats()


# ============================================
# Background Tasks
# ============================================

async def cleanup_stale_nodes():
    """Periodically remove nodes that haven't sent heartbeats."""
    while True:
        try:
            await asyncio.sleep(config.node_cleanup_interval)

            with database.get_session() as db:
                cutoff = datetime.utcnow() - timedelta(seconds=config.node_heartbeat_timeout)
                deleted = db.query(Node).filter(
                    Node.last_heartbeat < cutoff
                ).delete()

                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} stale nodes")

        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


async def update_statistics():
    """Periodically record network statistics."""
    while True:
        try:
            await asyncio.sleep(3600)  # Every hour

            with database.get_session() as db:
                cutoff = datetime.utcnow() - timedelta(seconds=config.node_heartbeat_timeout)
                active_nodes = db.query(Node).filter(
                    Node.last_heartbeat >= cutoff
                ).count()

                total_nodes_ever = db.query(Node).count()

                total_jobs = db.query(Node).with_entities(
                    Node.total_jobs_completed,
                    Node.total_jobs_failed
                ).all()

                total_completed = sum(j[0] for j in total_jobs)
                total_failed = sum(j[1] for j in total_jobs)

                stats = CoordinatorStats(
                    total_nodes_ever=total_nodes_ever,
                    active_nodes=active_nodes,
                    total_jobs_processed=total_completed + total_failed
                )
                db.add(stats)

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")


async def federate_node_lists():
    """Periodically sync node lists with peer coordinators (Phase 3)."""
    # TODO: Implement in Phase 3
    pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=config.host,
        port=config.coordinator_port,
        log_level="debug" if config.enable_debug_logs else "info"
    )
