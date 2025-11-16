# Ambient Intelligence - API Documentation

**Version**: 1.0.0
**Protocol**: v1.0.0
**Last Updated**: 2025-01-16

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Node API](#node-api)
4. [Coordinator API](#coordinator-api)
5. [Federation API](#federation-api)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Examples](#examples)

---

## Overview

The Ambient Intelligence Protocol defines two types of services:

- **Nodes**: Process encrypted AI inference requests
- **Coordinators**: Discovery services for finding nodes

All APIs use **JSON** for request/response bodies and **HTTP/HTTPS** for transport.

### Base URLs

```
Node:        http://{node_ip}:{port}     (default: port 8000)
Coordinator: http://{coordinator_ip}:{port} (default: port 5000)
```

### Common Headers

```http
Content-Type: application/json
Accept: application/json
```

---

## Authentication

### Node API

**No authentication required** for job submission. Privacy is guaranteed through encryption, not authentication.

### Coordinator API

Most endpoints are **public** and require no authentication.

**Admin endpoints** require a Bearer token:

```http
Authorization: Bearer {ADMIN_TOKEN}
```

**Priority token endpoints** require JWT:

```http
Authorization: Bearer {JWT_TOKEN}
```

---

## Node API

### Health Check

Check if node is healthy and operational.

**Endpoint**: `GET /health`

**Request**: None

**Response**: `200 OK`

```json
{
  "status": "healthy",
  "ollama_available": true,
  "active_jobs": 5,
  "uptime_seconds": 86400
}
```

**Status Values**:
- `healthy`: All systems operational
- `degraded`: Ollama unavailable or high load
- `unhealthy`: Critical errors

**Example**:

```bash
curl http://localhost:8000/health
```

---

### Get Public Key

Retrieve node's public key for encryption.

**Endpoint**: `GET /pubkey`

**Request**: None

**Response**: `200 OK`

```json
{
  "public_key": "base64-encoded-nacl-public-key"
}
```

**Example**:

```bash
curl http://localhost:8000/pubkey
```

**Usage**: Clients encrypt prompts with this key.

---

### Submit Job

Submit an encrypted inference job.

**Endpoint**: `POST /submit`

**Request Body**:

```json
{
  "encrypted_prompt": "base64-encoded-ciphertext",
  "client_pubkey": "base64-encoded-client-public-key",
  "model": "llama3:8b"
}
```

**Fields**:
- `encrypted_prompt` (required): Base64-encoded NaCl encrypted prompt
- `client_pubkey` (required): Base64-encoded client public key for response encryption
- `model` (optional): Model name (defaults to node's default model)

**Response**: `200 OK`

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "estimated_wait_seconds": 15
}
```

**Error Responses**:

- `400 Bad Request`: Invalid request format
  ```json
  {"detail": "Missing required field: encrypted_prompt"}
  ```

- `413 Payload Too Large`: Encrypted prompt exceeds 100KB
  ```json
  {"detail": "Encrypted prompt exceeds maximum size"}
  ```

- `503 Service Unavailable`: Node at capacity
  ```json
  {"detail": "Node at maximum capacity"}
  ```

**Example**:

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "encrypted_prompt": "base64_encrypted_data...",
    "client_pubkey": "base64_public_key...",
    "model": "llama3:8b"
  }'
```

---

### Get Job Status

Poll for job completion and retrieve encrypted response.

**Endpoint**: `GET /status/{job_id}`

**Path Parameters**:
- `job_id`: UUID of the job

**Response**: `200 OK`

```json
{
  "status": "complete",
  "encrypted_response": "base64-encoded-ciphertext",
  "node_pubkey": "base64-encoded-node-public-key"
}
```

**Status Values**:
- `pending`: Job queued, not yet processing
- `running`: Job currently processing
- `complete`: Job finished, response available
- `failed`: Job failed, error message available

**Response for Failed Jobs**:

```json
{
  "status": "failed",
  "error_message": "Model not available"
}
```

**Error Responses**:

- `404 Not Found`: Job ID not found
  ```json
  {"detail": "Job not found"}
  ```

**Example**:

```bash
curl http://localhost:8000/status/550e8400-e29b-41d4-a716-446655440000
```

**Polling Recommendations**:
- Poll every 2-5 seconds
- Implement exponential backoff
- Stop polling after 5 minutes

---

### Get Metrics

Retrieve node operational metrics (no user data).

**Endpoint**: `GET /metrics`

**Request**: None

**Response**: `200 OK`

```json
{
  "total_jobs": 1000,
  "completed_jobs": 950,
  "failed_jobs": 50,
  "success_rate": 0.95,
  "ollama_available": true,
  "uptime_seconds": 86400
}
```

**Example**:

```bash
curl http://localhost:8000/metrics
```

---

## Coordinator API

### Health Check

Check coordinator health.

**Endpoint**: `GET /health`

**Request**: None

**Response**: `200 OK`

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "active_nodes": 50
}
```

**Example**:

```bash
curl http://localhost:5000/health
```

---

### Node Announcement (Heartbeat)

Nodes send heartbeats to stay discoverable.

**Endpoint**: `POST /nodes/announce`

**Request Body**:

```json
{
  "node_id": "550e8400-e29b-41d4-a716-446655440000",
  "ip_address": "203.0.113.10",
  "port": 8000,
  "public_key": "base64-encoded-public-key",
  "models": ["llama3:8b", "codellama:13b"],
  "max_concurrent": 2,
  "current_load": 0.3,
  "version": "0.3.0"
}
```

**Fields**:
- `node_id` (required): Unique UUID for this node
- `ip_address` (required): Public IP address
- `port` (required): Port number
- `public_key` (required): NaCl public key
- `models` (required): List of available models
- `max_concurrent` (optional): Maximum concurrent jobs
- `current_load` (optional): Current load (0.0 to 1.0)
- `version` (optional): Node software version

**Response**: `200 OK`

```json
{
  "status": "ok",
  "node_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Example**:

```bash
curl -X POST http://localhost:5000/nodes/announce \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "550e8400-e29b-41d4-a716-446655440000",
    "ip_address": "203.0.113.10",
    "port": 8000,
    "public_key": "base64key...",
    "models": ["llama3:8b"],
    "max_concurrent": 2,
    "current_load": 0.3
  }'
```

**Note**: Nodes must send heartbeats every 60 seconds. Nodes missing heartbeats for 90+ seconds are removed.

---

### Discover Nodes

Query for available nodes.

**Endpoint**: `GET /nodes/discover`

**Query Parameters**:
- `model` (optional): Filter by model name
- `min_uptime` (optional): Minimum uptime score (0-100)
- `limit` (optional): Maximum results (default: 10, max: 1000)

**Response**: `200 OK`

```json
[
  {
    "node_id": "550e8400-e29b-41d4-a716-446655440000",
    "address": "203.0.113.10:8000",
    "public_key": "base64-encoded-public-key",
    "models": ["llama3:8b", "codellama:13b"],
    "current_load": 0.3,
    "uptime_score": 75.5,
    "max_concurrent": 2,
    "success_rate": 0.95
  }
]
```

**Sorting**: Results are sorted by:
1. Uptime score (descending)
2. Current load (ascending)

**Example**:

```bash
# Get 5 nodes with llama3:8b
curl "http://localhost:5000/nodes/discover?model=llama3:8b&limit=5"

# Get nodes with high uptime
curl "http://localhost:5000/nodes/discover?min_uptime=50&limit=10"
```

---

### Report Abuse

Report abusive IP addresses.

**Endpoint**: `POST /abuse/report`

**Request Body**:

```json
{
  "ip_address": "203.0.113.100",
  "reason": "excessive requests",
  "reporter_node_id": "550e8400-e29b-41d4-a716-446655440000",
  "severity": "medium"
}
```

**Fields**:
- `ip_address` (required): IP to report
- `reason` (required): Description of abuse
- `reporter_node_id` (required): Your node ID
- `severity` (optional): `low`, `medium`, `high`

**Response**: `200 OK`

```json
{
  "status": "reported",
  "report_id": "123",
  "action": "recorded"
}
```

**Auto-blocking**: IPs with 3+ reports are automatically blocked for 24 hours.

**Example**:

```bash
curl -X POST http://localhost:5000/abuse/report \
  -H "Content-Type: application/json" \
  -d '{
    "ip_address": "203.0.113.100",
    "reason": "excessive requests",
    "reporter_node_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

---

### Check IP Block Status

Check if an IP is blocked.

**Endpoint**: `GET /abuse/check/{ip_address}`

**Path Parameters**:
- `ip_address`: IP address to check

**Response**: `200 OK`

```json
{
  "blocked": true,
  "reason": "multiple abuse reports",
  "expires_at": "2025-01-17T12:00:00Z",
  "is_permanent": false
}
```

**Example**:

```bash
curl http://localhost:5000/abuse/check/203.0.113.100
```

---

### Network Statistics

Get network-wide statistics.

**Endpoint**: `GET /stats`

**Request**: None

**Response**: `200 OK`

```json
{
  "active_nodes": 50,
  "total_nodes_ever": 150,
  "total_jobs_completed": 1000000,
  "total_jobs_failed": 50000,
  "success_rate": 0.95,
  "timestamp": "2025-01-16T12:00:00Z"
}
```

**Example**:

```bash
curl http://localhost:5000/stats
```

---

### Priority Tokens

Get user's priority token balance.

**Endpoint**: `GET /tokens/{user_id}`

**Path Parameters**:
- `user_id`: User identifier

**Request Headers**:
```http
Authorization: Bearer {JWT_TOKEN}
```

**Response**: `200 OK`

```json
{
  "user_id": "user123",
  "balance": 1500,
  "earned_total": 2000,
  "spent_total": 500,
  "last_updated": "2025-01-16T12:00:00Z"
}
```

**Example**:

```bash
curl http://localhost:5000/tokens/user123 \
  -H "Authorization: Bearer your_jwt_token"
```

---

## Federation API

Federation endpoints allow coordinators to sync with peers.

### Get Federation Peers

List all peer coordinators.

**Endpoint**: `GET /federation/peers`

**Request**: None

**Response**: `200 OK`

```json
{
  "peers": [
    {
      "url": "https://coord1.example.com",
      "last_sync": "2025-01-16T12:00:00Z",
      "status": "healthy",
      "error_count": 0,
      "total_syncs": 150
    }
  ],
  "stats": {
    "total_peers": 3,
    "healthy_peers": 2,
    "recent_syncs": 3,
    "federation_enabled": true,
    "sync_interval_seconds": 300
  }
}
```

**Example**:

```bash
curl http://localhost:5000/federation/peers
```

---

### Register Peer Coordinator

Register a new peer coordinator (admin only).

**Endpoint**: `POST /federation/register`

**Request Headers**:
```http
Authorization: Bearer {ADMIN_TOKEN}
```

**Request Body**:

```json
{
  "peer_url": "https://coord3.example.com",
  "description": "Community coordinator in EU"
}
```

**Response**: `200 OK`

```json
{
  "status": "registered",
  "peer_url": "https://coord3.example.com",
  "verification": "success"
}
```

**Example**:

```bash
curl -X POST http://localhost:5000/federation/register \
  -H "Authorization: Bearer your_admin_token" \
  -H "Content-Type: application/json" \
  -d '{
    "peer_url": "https://coord3.example.com"
  }'
```

---

### Get Federation Statistics

Get federation health metrics.

**Endpoint**: `GET /federation/stats`

**Request**: None

**Response**: `200 OK`

```json
{
  "federation_enabled": true,
  "total_peers": 3,
  "healthy_peers": 2,
  "recent_syncs": 3,
  "sync_interval_seconds": 300,
  "last_sync_time": "2025-01-16T12:00:00Z"
}
```

**Example**:

```bash
curl http://localhost:5000/federation/stats
```

---

## Error Handling

All errors follow this format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2025-01-16T12:00:00Z"
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Job completed |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid JSON |
| 401 | Unauthorized | Missing auth token |
| 403 | Forbidden | Invalid auth token |
| 404 | Not Found | Job ID doesn't exist |
| 413 | Payload Too Large | Prompt > 100KB |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Database failure |
| 503 | Service Unavailable | Node at capacity |

### Common Error Codes

**Node Errors**:
- `INVALID_ENCRYPTION`: Cannot decrypt prompt
- `MODEL_NOT_FOUND`: Requested model unavailable
- `JOB_TIMEOUT`: Job exceeded timeout
- `OLLAMA_UNAVAILABLE`: AI model backend offline

**Coordinator Errors**:
- `NODE_NOT_FOUND`: Node ID not in database
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INVALID_TOKEN`: JWT verification failed
- `IP_BLOCKED`: IP address is blocked

---

## Rate Limiting

### Node Rate Limits

- **Default**: 10 requests per minute per IP
- **Configurable**: Set via `MAX_REQUESTS_PER_MINUTE` env var

**Headers**:
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1642348800
```

**Error Response** (429):

```json
{
  "detail": "Rate limit exceeded. Try again in 45 seconds.",
  "retry_after": 45
}
```

### Coordinator Rate Limits

- **Discovery**: 60 requests per minute per IP
- **Heartbeats**: Unlimited (authenticated by node ID)
- **Abuse reports**: 10 per hour per node

---

## Examples

### Complete Client Flow

```python
import requests
import nacl.public
import nacl.encoding
import base64
import time

# 1. Generate ephemeral keypair
client_private = nacl.public.PrivateKey.generate()
client_public = client_private.public_key

# 2. Discover node
coordinator_url = "http://localhost:5000"
nodes = requests.get(f"{coordinator_url}/nodes/discover?limit=1").json()
node = nodes[0]
node_url = f"http://{node['address']}"

# 3. Get node public key
node_pubkey_b64 = node['public_key']
node_pubkey = nacl.public.PublicKey(
    base64.b64decode(node_pubkey_b64)
)

# 4. Encrypt prompt
box = nacl.public.Box(client_private, node_pubkey)
prompt = "Explain quantum computing"
encrypted = box.encrypt(prompt.encode('utf-8'))
encrypted_b64 = base64.b64encode(encrypted).decode()

# 5. Submit job
response = requests.post(
    f"{node_url}/submit",
    json={
        "encrypted_prompt": encrypted_b64,
        "client_pubkey": base64.b64encode(
            bytes(client_public)
        ).decode()
    }
)
job_id = response.json()['job_id']

# 6. Poll for completion
while True:
    status_response = requests.get(f"{node_url}/status/{job_id}")
    status_data = status_response.json()

    if status_data['status'] == 'complete':
        break
    elif status_data['status'] == 'failed':
        raise Exception(status_data['error_message'])

    time.sleep(2)

# 7. Decrypt response
encrypted_response = base64.b64decode(
    status_data['encrypted_response']
)
response_box = nacl.public.Box(client_private, node_pubkey)
plaintext = response_box.decrypt(encrypted_response)
print(plaintext.decode('utf-8'))
```

---

### Running a Multi-Coordinator Federation

```bash
# Coordinator 1 (US East)
FEDERATION_ENABLED=true \
PEER_COORDINATORS=https://coord2.example.com,https://coord3.example.com \
COORDINATOR_PORT=5000 \
python coordinator/server.py

# Coordinator 2 (EU West)
FEDERATION_ENABLED=true \
PEER_COORDINATORS=https://coord1.example.com,https://coord3.example.com \
COORDINATOR_PORT=5000 \
python coordinator/server.py

# Coordinator 3 (Asia Pacific)
FEDERATION_ENABLED=true \
PEER_COORDINATORS=https://coord1.example.com,https://coord2.example.com \
COORDINATOR_PORT=5000 \
python coordinator/server.py
```

After 5 minutes, all coordinators will have a unified view of the network.

---

## Changelog

### v1.0.0 (2025-01-16)
- Initial API documentation
- Node API endpoints documented
- Coordinator API endpoints documented
- Federation API endpoints documented

---

For questions or clarifications, please open an issue on GitHub.
