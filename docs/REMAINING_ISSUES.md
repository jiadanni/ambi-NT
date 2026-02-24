# Remaining Issues - Medium Priority

These issues are important but not blocking for production deployment. They should be addressed before scaling to high traffic.

---

## Medium Priority (Recommended for Next Sprint)

### 1. Set up Alembic for Database Migrations
**Severity**: MEDIUM (Ops)
**Status**: ✅ COMPLETED

**Issue**: No database migration tool configured. Schema changes require manual SQL or downtime.

**Impact**: Any model changes in `coordinator/models.py` will fail in production

**Solution**:
```bash
# Install Alembic
pip install alembic

# Initialize
cd coordinator
alembic init migrations

# Configure alembic.ini
sqlalchemy.url = postgresql://user:pass@host/db

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply
alembic upgrade head
```

**Files to Create**:
- `coordinator/migrations/` directory
- `coordinator/alembic.ini`
- Update `coordinator/database.py` to use migrations instead of `create_tables()`

**Priority**: HIGH before any schema changes

---

### 2. Implement Coordinator Resilience with Fallback Support
**Severity**: MEDIUM (Arch)
**Status**: ✅ COMPLETED

**Issue**:
- `node/config.py` has single `COORDINATOR_URL`
- `node/coordinator_resilience.py` exists but never instantiated
- Nodes can't switch to backup coordinators

**Impact**: Any coordinator downtime breaks all new job submissions

**Solution**:
```python
# node/config.py
self.coordinator_urls = os.getenv("COORDINATOR_URLS", "").split(",")

# node/server.py - lifespan
from node.coordinator_resilience import CoordinatorResilientClient

coordinator_client = CoordinatorResilientClient(
    primary_url=config.coordinator_urls[0],
    fallback_urls=config.coordinator_urls[1:],
    retry_attempts=3
)

# Use coordinator_client instead of direct HTTP calls
```

**Files to Modify**:
- `node/config.py` - Change `COORDINATOR_URL` to `COORDINATOR_URLS`
- `node/server.py` - Integrate `CoordinatorResilientClient`
- Update `send_heartbeat()` to use resilient client

**Priority**: HIGH for production

---

### 3. Persist Rate Limiter State to Redis
**Severity**: MEDIUM (Security)
**Status**: Not implemented

**Issue**: In-memory rate limiter resets on node restart - attackers can reset limits by triggering restart

**Impact**: Coordinated attack could bypass rate limiting

**Solution**:
```python
# node/rate_limiter.py
import redis

class RateLimiter:
    def __init__(self, redis_url: Optional[str] = None, ...):
        self.redis = redis.from_url(redis_url) if redis_url else None

    def is_allowed(self, client_pubkey: str) -> Tuple[bool, int, Optional[str]]:
        if self.redis:
            # Use Redis for persistent tracking
            key = f"ratelimit:{key_hash}"
            count = self.redis.incr(key)
            if count == 1:
                self.redis.expire(key, 60)
            return count <= self.max_requests
        else:
            # Fallback to in-memory
            ...
```

**Dependencies**:
- `pip install redis`
- Redis server running
- `REDIS_URL` config option

**Priority**: MEDIUM (nice to have for high-security deployments)

---

### 4. Add Rate Limiting to Coordinator Endpoints
**Severity**: MEDIUM (Security)
**Status**: ✅ COMPLETED

**Issue**:
- `/nodes/discover` - no rate limit
- `/nodes/announce` (heartbeat) - no per-IP limit
- Federation endpoints - no protection

**Impact**: Easy DOS on coordinator

**Solution**:
```python
# coordinator/server.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/nodes/discover")
@limiter.limit("60/minute")  # 60 requests per minute per IP
async def discover_nodes(...):
    ...

@app.post("/nodes/announce")
@limiter.limit("10/minute")  # Heartbeat at most every 6 seconds
async def announce_node(...):
    ...
```

**Dependencies**:
- `pip install slowapi`

**Priority**: HIGH for public deployment

---

### 5. Sign Heartbeats with Node Private Key
**Severity**: MEDIUM (Security)
**Status**: ✅ COMPLETED

**Issue**: Heartbeats contain `node_id` but no signature - any node can impersonate any other node

**Impact**: Attacker can register fake nodes

**Solution**:
```python
# node/server.py - send_heartbeat()
heartbeat_data = {
    "node_id": config.node_id,
    "ip_address": get_public_ip(),
    ...
    "timestamp": int(time.time())
}

# Sign the heartbeat
message = json.dumps(heartbeat_data, sort_keys=True)
signature = crypto.sign(message)
heartbeat_data["signature"] = signature

# coordinator/server.py - announce_node()
@app.post("/nodes/announce")
async def announce_node(data: dict):
    # Verify signature
    node_pubkey = data["public_key"]
    signature = data.pop("signature")
    message = json.dumps(data, sort_keys=True)

    if not verify_signature(message, signature, node_pubkey):
        raise HTTPException(403, "Invalid signature")
    ...
```

**Files to Modify**:
- `node/crypto.py` - Add `sign()` method
- `node/server.py` - Sign heartbeats
- `coordinator/server.py` - Verify signatures

**Priority**: HIGH for federation security

---

### 6. Add Distributed Tracing
**Severity**: MEDIUM (Ops)
**Status**: Not implemented

**Issue**: Cannot trace requests across node → coordinator → other nodes

**Impact**: Debugging federation issues nearly impossible

**Solution**:
```python
# Install OpenTelemetry
pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi

# node/server.py & coordinator/server.py
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

FastAPIInstrumentor.instrument_app(app)

# Use in endpoints
@app.post("/submit")
async def submit_job(request: SubmitJobRequest):
    with tracer.start_as_current_span("submit_job") as span:
        span.set_attribute("job_id", job_id)
        span.set_attribute("client_pubkey_hash", key_hash)
        ...
```

**Priority**: LOW (useful for debugging at scale)

---

### 7. Comprehensive Integration Tests
**Severity**: MEDIUM (Testing)
**Status**: ✅ COMPLETED (Implemented tests for heartbeats, failover, and E2E encryption)

**Issue**:
- `tests/test_phase0_5_smoke.py` only tests encryption
- No federation tests
- No conversation flow tests
- No failure scenario tests

**Solution**:
```python
# tests/test_integration.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_multi_coordinator_federation():
    """Test 3 coordinators syncing nodes"""
    coord1 = start_coordinator(port=5001)
    coord2 = start_coordinator(port=5002, peers=["http://localhost:5001"])
    coord3 = start_coordinator(port=5003, peers=["http://localhost:5001"])

    # Register node on coord1
    node1 = register_node(coord1, "node1")

    # Wait for sync
    await asyncio.sleep(10)

    # Verify node visible on all coordinators
    assert get_nodes(coord2) contains "node1"
    assert get_nodes(coord3) contains "node1"

@pytest.mark.asyncio
async def test_conversation_flow():
    """Test multi-turn conversation"""
    messages = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "Now multiply by 3"}
    ]

    response = await submit_conversation(messages)
    assert "12" in response

@pytest.mark.asyncio
async def test_coordinator_failover():
    """Test node switches to fallback coordinator"""
    coord1 = start_coordinator(port=5001)
    coord2 = start_coordinator(port=5002)

    node = start_node(coordinators=["http://localhost:5001", "http://localhost:5002"])

    # Kill primary coordinator
    coord1.kill()

    # Verify node sends heartbeat to fallback
    await asyncio.sleep(10)
    assert get_nodes(coord2) contains node.id
```

**Priority**: HIGH before major release

---

### 8. Add Health Check for Database Connection
**Severity**: MEDIUM (Ops)
**Status**: ✅ COMPLETED

**Issue**: Coordinator `/health` doesn't verify database connectivity

**Impact**: Coordinator might accept requests with dead DB

**Solution**:
```python
# coordinator/server.py
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        # Simple query to verify DB connection
        db.execute("SELECT 1")
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_healthy = False

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "pool_stats": database.get_pool_status()
    }
```

**Priority**: MEDIUM

---

### 9. Configuration Validation Enhancement
**Severity**: MEDIUM (Ops)
**Status**: ✅ COMPLETED

**Issue**: Many configs not validated, no check for sensible combinations

**Example**:
```python
# This is currently allowed but makes no sense:
job_timeout_seconds = 60
job_cleanup_interval_seconds = 300  # Cleanup runs AFTER timeout would've killed it

# Or:
max_concurrent_jobs = 1
rate_limit_per_client = 100  # Why allow 100 reqs/min if you can only handle 1 at a time?
```

**Solution**:
```python
# node/config.py
def validate(self) -> Tuple[bool, str]:
    # Existing validations...

    # New validations
    if self.job_cleanup_interval_seconds < self.job_ttl_seconds:
        return False, "job_cleanup_interval must be >= job_ttl_seconds"

    if self.rate_limit_per_client > self.max_concurrent_jobs * 10:
        logger.warning("Rate limit much higher than concurrency - may queue many jobs")

    if self.heartbeat_interval_seconds > 60 and self.coordinator_url:
        return False, "Heartbeat interval too long (max 60s)"

    return True, None
```

**Priority**: LOW (nice to have)

---

### 10. API Documentation (Swagger/OpenAPI)
**Severity**: MEDIUM (Ops)
**Status**: ✅ COMPLETED (Default FastAPI docs enabled)

**Issue**: FastAPI has built-in Swagger but not enabled

**Solution**:
```python
# node/server.py & coordinator/server.py
app = FastAPI(
    title="Ambient Intelligence Node",
    description="Privacy-first AI inference node",
    version="0.3.0",
    docs_url="/docs",  # Enable Swagger UI
    redoc_url="/redoc"  # Enable ReDoc
)
```

Access at: `http://localhost:8000/docs`

**Priority**: LOW (documentation improvement)

---

## Summary Table

| Issue | Severity | Priority | Estimated Effort | Blocking |
|-------|----------|----------|------------------|----------|
| Alembic migrations | MEDIUM | HIGH | 2-4 hours | Before schema changes |
| Coordinator resilience | MEDIUM | HIGH | 4-6 hours | For production HA |
| Rate limiter Redis | MEDIUM | MEDIUM | 2-3 hours | For high security |
| Coordinator rate limiting | MEDIUM | HIGH | 1-2 hours | Before public deploy |
| Heartbeat signing | MEDIUM | HIGH | 3-4 hours | For federation security |
| Distributed tracing | MEDIUM | LOW | 6-8 hours | For scale debugging |
| Integration tests | MEDIUM | HIGH | 8-12 hours | Before major release |
| DB health check | MEDIUM | MEDIUM | 1 hour | Nice to have |
| Config validation | MEDIUM | LOW | 2-3 hours | Quality of life |
| API docs | MEDIUM | LOW | 30 mins | Quality of life |

**Total Effort**: ~30-45 hours
**Recommend**: Address HIGH priority items (17-25 hours) before production

---

## Quick Wins (< 2 hours each)

1. ✅ Enable Swagger docs (30 mins)
2. ✅ Add DB health check (1 hour)
3. ✅ Add coordinator rate limiting (1-2 hours)

These can be done in a single day for quick security improvements.

---

**Updated**: 2025-12-27
**Next Review**: After staging deployment testing
