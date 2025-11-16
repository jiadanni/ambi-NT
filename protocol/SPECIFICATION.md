# Ambient Intelligence Protocol Specification v1.0

**Status**: Draft
**Version**: 1.0.0
**Date**: 2025-01-16
**Authors**: Ambient Intelligence Contributors

## Abstract

This document defines the Ambient Intelligence Protocol (AIP), a decentralized system for privacy-preserving AI inference over a peer-to-peer network. The protocol enables secure, encrypted communication between clients and compute nodes without requiring trust in any central authority.

## Table of Contents

1. [Introduction](#1-introduction)
2. [Terminology](#2-terminology)
3. [Cryptography](#3-cryptography)
4. [Node Protocol](#4-node-protocol)
5. [Coordinator Protocol](#5-coordinator-protocol)
6. [Federation Protocol](#6-federation-protocol)
7. [Security Considerations](#7-security-considerations)
8. [Privacy Guarantees](#8-privacy-guarantees)
9. [Implementation Guidelines](#9-implementation-guidelines)
10. [Version History](#10-version-history)

---

## 1. Introduction

### 1.1 Motivation

Existing AI inference services require users to trust centralized operators with their private data. The Ambient Intelligence Protocol solves this through end-to-end encryption, ensuring that compute providers never access plaintext prompts or responses.

### 1.2 Goals

- **Privacy**: End-to-end encryption of all user data
- **Decentralization**: No single point of control or failure
- **Scalability**: Support for thousands of nodes and millions of users
- **Simplicity**: Easy to implement and audit
- **Resilience**: Network continues operating even if components fail

### 1.3 Non-Goals

- Blockchain or cryptocurrency integration
- Proof-of-work consensus
- Anonymous routing (Tor-like onion encryption)
- General-purpose file storage

## 2. Terminology

- **Node**: A server that processes encrypted AI inference requests
- **Client**: Software that submits prompts and receives responses
- **Coordinator**: A discovery service that maintains node lists
- **Federation**: A set of coordinators that share node information
- **Heartbeat**: Periodic message from node to coordinator proving liveness
- **Job**: A single inference request/response cycle
- **Priority Token**: Economic unit for resource allocation (optional)

## 3. Cryptography

### 3.1 Cryptographic Primitives

All encryption MUST use the **NaCl/libsodium** `crypto_box` construction:

- **Key Agreement**: Curve25519
- **Encryption**: XSalsa20
- **Authentication**: Poly1305

### 3.2 Key Generation

#### 3.2.1 Node Keys

Nodes generate a **long-lived** Ed25519 keypair on first startup:

```python
import nacl.public

private_key = nacl.public.PrivateKey.generate()
public_key = private_key.public_key
```

- Private key MUST be stored securely (environment variable, never committed)
- Public key is advertised to clients and coordinators
- Keys SHOULD be rotated at least annually

#### 3.2.2 Client Keys

Clients generate **ephemeral** X25519 keypairs per session:

```python
import nacl.public

session_key = nacl.public.PrivateKey.generate()
```

- Private key exists only in memory
- Provides forward secrecy
- Keys MUST be discarded after session

### 3.3 Message Encryption

#### 3.3.1 Client to Node

```python
# Client encrypts prompt
box = nacl.public.Box(client_private_key, node_public_key)
encrypted = box.encrypt(plaintext.encode('utf-8'))
ciphertext = base64.b64encode(encrypted).decode()
```

#### 3.3.2 Node to Client

```python
# Node encrypts response
box = nacl.public.Box(node_private_key, client_public_key)
encrypted = box.encrypt(response.encode('utf-8'))
ciphertext = base64.b64encode(encrypted).decode()
```

### 3.4 Nonce Handling

NaCl automatically generates unique nonces for each encryption operation. Implementations MUST NOT reuse nonces.

## 4. Node Protocol

### 4.1 Node API Endpoints

Nodes MUST expose the following HTTP endpoints:

#### 4.1.1 GET /pubkey

Returns the node's public key.

**Response:**
```json
{
  "public_key": "base64-encoded-public-key"
}
```

**Status Codes:**
- `200 OK`: Success

#### 4.1.2 POST /submit

Accepts an encrypted job for processing.

**Request:**
```json
{
  "encrypted_prompt": "base64-encoded-ciphertext",
  "client_pubkey": "base64-encoded-client-public-key",
  "model": "llama3:8b"  // optional
}
```

**Response:**
```json
{
  "job_id": "uuid-v4",
  "estimated_wait_seconds": 15
}
```

**Status Codes:**
- `200 OK`: Job accepted
- `400 Bad Request`: Invalid request format
- `413 Payload Too Large`: Prompt exceeds size limit
- `503 Service Unavailable`: Node at capacity

**Constraints:**
- Encrypted prompt MUST NOT exceed 100KB
- Job ID MUST be a valid UUID v4

#### 4.1.3 GET /status/{job_id}

Polls for job completion.

**Response:**
```json
{
  "status": "pending|running|complete|failed",
  "encrypted_response": "base64-encoded-ciphertext",  // if complete
  "node_pubkey": "base64-encoded-public-key",
  "error_message": "error details"  // if failed
}
```

**Status Codes:**
- `200 OK`: Job found
- `404 Not Found`: Job ID not found

**Polling:**
- Clients SHOULD poll every 2-5 seconds
- Nodes MAY expire job records after 1 hour

#### 4.1.4 GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy|degraded|unhealthy",
  "ollama_available": true,
  "active_jobs": 5,
  "uptime_seconds": 86400
}
```

#### 4.1.5 GET /metrics

Operational metrics (no user data).

**Response:**
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

### 4.2 Node Behavior

#### 4.2.1 Job Processing

1. Node receives encrypted prompt via `/submit`
2. Node creates job record with status "pending"
3. Node decrypts prompt (plaintext exists only in memory)
4. Node passes plaintext to AI model
5. Node receives response from AI model
6. Node encrypts response with client's public key
7. Node updates job status to "complete"
8. Node stores encrypted response for retrieval

**Privacy Requirement**: Plaintext MUST NEVER be logged or persisted.

#### 4.2.2 Heartbeats

If coordinator is configured, nodes MUST send heartbeats every 60 seconds:

```json
POST {coordinator_url}/nodes/announce
{
  "node_id": "uuid",
  "ip_address": "1.2.3.4",
  "port": 8000,
  "public_key": "base64-encoded",
  "models": ["llama3:8b", "codellama:13b"],
  "max_concurrent": 2,
  "current_load": 0.3,
  "version": "0.3.0"
}
```

Nodes that miss 1.5x the heartbeat interval (90 seconds default) are considered offline.

## 5. Coordinator Protocol

### 5.1 Coordinator API Endpoints

#### 5.1.1 POST /nodes/announce

Nodes send heartbeats to stay discoverable.

**Request:**
```json
{
  "node_id": "uuid",
  "ip_address": "1.2.3.4",
  "port": 8000,
  "public_key": "base64",
  "models": ["llama3:8b"],
  "max_concurrent": 2,
  "current_load": 0.3,
  "version": "0.3.0"
}
```

**Response:**
```json
{
  "status": "ok",
  "node_id": "uuid"
}
```

#### 5.1.2 GET /nodes/discover

Clients query for available nodes.

**Query Parameters:**
- `model` (optional): Filter by model name
- `min_uptime` (optional): Minimum uptime score
- `limit` (default: 10): Maximum results

**Response:**
```json
[
  {
    "node_id": "uuid",
    "address": "1.2.3.4:8000",
    "public_key": "base64",
    "models": ["llama3:8b"],
    "current_load": 0.3,
    "uptime_score": 75.5,
    "max_concurrent": 2,
    "success_rate": 0.95
  }
]
```

Results MUST be sorted by:
1. Uptime score (descending)
2. Current load (ascending)

#### 5.1.3 POST /abuse/report

Nodes report abusive IPs.

**Request:**
```json
{
  "ip_address": "1.2.3.4",
  "reason": "excessive requests",
  "reporter_node_id": "uuid",
  "severity": "medium"
}
```

#### 5.1.4 GET /abuse/check/{ip_address}

Check if an IP is blocked.

**Response:**
```json
{
  "blocked": true,
  "reason": "multiple abuse reports",
  "expires_at": "2025-01-17T00:00:00Z",
  "is_permanent": false
}
```

#### 5.1.5 GET /stats

Network statistics.

**Response:**
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

### 5.2 Coordinator Behavior

#### 5.2.1 Node Tracking

- Coordinators MUST track last heartbeat timestamp
- Nodes with no heartbeat for 90 seconds MUST be removed from discovery
- Uptime score SHOULD increase gradually (e.g., +0.1 per heartbeat)
- Uptime score SHOULD be capped at 100.0

#### 5.2.2 Abuse Detection

- Multiple reports (≥3) for same IP SHOULD trigger automatic block
- Blocks SHOULD expire after 24 hours (configurable)
- Only nodes with uptime score ≥10.0 can report abuse

## 6. Federation Protocol

### 6.1 Coordinator Federation

Multiple coordinators can federate to create a unified network.

#### 6.1.1 Peer Discovery

Coordinators MUST be manually configured with peer URLs:

```env
PEER_COORDINATORS=https://coord1.example.com,https://coord2.example.com
```

#### 6.1.2 Node Synchronization

Every 5 minutes (configurable), coordinator A:

1. Queries all peer coordinators: `GET {peer}/nodes/discover?limit=1000`
2. Merges peer node lists with local nodes
3. Deduplicates by `node_id`
4. Updates local database

**Conflict Resolution:**
- If node exists in multiple coordinators, use most recent heartbeat
- If heartbeat timestamps equal, prefer local node

#### 6.1.3 Federation API

##### GET /federation/peers

Returns list of known peer coordinators.

**Response:**
```json
{
  "peers": [
    {
      "url": "https://coord1.example.com",
      "last_sync": "2025-01-16T12:00:00Z",
      "status": "healthy"
    }
  ]
}
```

##### POST /federation/register

Allows other coordinators to register as peers.

**Request:**
```json
{
  "url": "https://coord3.example.com",
  "public_key": "base64"  // optional for verification
}
```

### 6.2 Trust Model

- Federation is **permissioned** (manual configuration)
- No automatic peer discovery (prevents Sybil attacks)
- Coordinators trust peers to provide accurate node information
- Clients can query any coordinator and get unified results

## 7. Security Considerations

### 7.1 Encryption

- All user data MUST be encrypted end-to-end
- Nodes MUST use constant-time comparisons for secrets
- Key rotation SHOULD occur at least annually

### 7.2 Rate Limiting

- Nodes SHOULD implement rate limiting (e.g., 10 requests/minute per IP)
- Coordinators SHOULD rate limit discovery queries

### 7.3 Input Validation

- All encrypted inputs MUST be validated for size
- Maximum encrypted prompt: 100KB
- Maximum response: 1MB

### 7.4 Denial of Service

- Nodes SHOULD implement job timeouts (default: 120s)
- Nodes SHOULD limit concurrent jobs
- Coordinators SHOULD implement request throttling

### 7.5 Abuse Prevention

- Multi-node reporting required for IP blocking
- Temporary blocks with expiration
- Only high-reputation nodes can report abuse

## 8. Privacy Guarantees

### 8.1 Node Privacy

**Guarantee**: Nodes NEVER see plaintext prompts or responses.

**Enforcement**:
- All data encrypted before network transmission
- Decryption occurs only in memory
- No logging of plaintext data
- No persistence of plaintext data

### 8.2 Client Privacy

**Guarantee**: Clients maintain privacy through ephemeral keys.

**Enforcement**:
- New keypair for each session
- Keys never persisted to disk
- Forward secrecy (past sessions safe if key compromised)

### 8.3 Coordinator Privacy

**Guarantee**: Coordinators only see metadata, never user data.

**Enforcement**:
- Coordinators receive only node heartbeats
- No encrypted prompts pass through coordinators
- No access to job content

### 8.4 Network Privacy

**Guarantee**: Network traffic reveals minimal metadata.

**Optional Enhancements**:
- Use Tor for IP anonymity
- Use VPNs/Tailscale for traffic masking
- Implement padding to hide message sizes

## 9. Implementation Guidelines

### 9.1 Required Features

Implementations MUST support:
- NaCl crypto_box encryption
- All node API endpoints
- Heartbeat mechanism (if using coordinator)
- Job timeout enforcement

### 9.2 Recommended Features

Implementations SHOULD support:
- Rate limiting
- Abuse reporting
- Metrics collection
- Health checks

### 9.3 Optional Features

Implementations MAY support:
- Priority tokens
- Multiple AI models
- Concurrent job processing
- Federation

### 9.4 Testing

Implementations SHOULD include:
- Encryption round-trip tests
- Security vulnerability tests
- Load testing
- Integration tests

### 9.5 Interoperability

All implementations MUST be compatible at the protocol level:
- Same encryption (NaCl)
- Same API endpoints
- Same message formats (JSON)

## 10. Version History

### v1.0.0 (2025-01-16)
- Initial protocol specification
- Node API defined
- Coordinator API defined
- Federation protocol defined
- Security considerations documented

---

## Appendix A: Example Flow

### Complete Request Flow

```
1. Client generates ephemeral keypair
2. Client queries coordinator: GET /nodes/discover
3. Client selects node with lowest load
4. Client fetches node public key: GET /pubkey
5. Client encrypts prompt with node public key
6. Client submits job: POST /submit
7. Client receives job_id
8. Client polls: GET /status/{job_id} (every 2s)
9. Node decrypts prompt (in memory only)
10. Node processes with AI model
11. Node encrypts response with client public key
12. Node updates job status to "complete"
13. Client retrieves encrypted response
14. Client decrypts response with session private key
15. Client displays result to user
```

### Privacy Verification

At no point in this flow does:
- Node see plaintext prompt or response
- Coordinator see any encrypted or plaintext user data
- Network observers see unencrypted content

---

## Appendix B: Reference Implementation

Reference implementation in Python: https://github.com/yourusername/ambient-intelligence

Alternative implementations welcome:
- Rust
- Go
- JavaScript/TypeScript
- Swift (mobile)

---

## Appendix C: Threat Model

### Threats Mitigated

✅ **Untrusted Nodes**: Cannot decrypt user data
✅ **Untrusted Coordinators**: Never see user data
✅ **Network Eavesdropping**: All traffic encrypted
✅ **Man-in-the-Middle**: Authenticated encryption

### Threats Not Mitigated

❌ **Timing Attacks**: Response times may leak information
❌ **Traffic Analysis**: Message sizes/patterns observable
❌ **Compromised Clients**: Malware can access plaintext
❌ **Quantum Computers**: Curve25519 vulnerable to quantum attacks

### Future Mitigations

- Post-quantum cryptography (when standardized)
- Padding to hide message sizes
- Dummy traffic to obscure patterns

---

**End of Specification**

For questions or improvements, open an issue at:
https://github.com/yourusername/ambient-intelligence/issues
