# Multi-Coordinator Federation - Deployment Guide

**Version**: 1.0.0
**Last Updated**: 2025-01-16

This guide explains how to deploy and operate a federated Ambient Intelligence network with multiple coordinators.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Single Coordinator Setup](#single-coordinator-setup)
4. [Multi-Coordinator Federation](#multi-coordinator-federation)
5. [Production Deployment](#production-deployment)
6. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
7. [Security Best Practices](#security-best-practices)

---

## Overview

### What is Federation?

Federation allows multiple independent coordinators to share node information, creating a unified decentralized network without central control.

**Benefits**:
- No single point of failure
- Geographic distribution
- Independent operation
- Shared network view
- Scalability

**How it Works**:
```
Every 5 minutes:
1. Each coordinator queries peers: GET /nodes/discover?limit=1000
2. Received nodes are merged with local database
3. Duplicates removed by node_id
4. Conflicts resolved (most recent heartbeat wins)
5. All coordinators converge to same network view
```

### Architecture

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  Coordinator A   │◄───────►│  Coordinator B   │◄───────►│  Coordinator C   │
│    (US-East)     │  Gossip │    (EU-West)     │  Gossip │   (Asia-Pac)     │
│                  │ Protocol│                  │ Protocol│                  │
│  PostgreSQL      │         │  PostgreSQL      │         │  PostgreSQL      │
│  Redis           │         │  Redis           │         │  Redis           │
└────────┬─────────┘         └────────┬─────────┘         └────────┬─────────┘
         │                            │                            │
         │ Heartbeats                 │                            │
         │                            │                            │
      Nodes                        Nodes                        Nodes
```

---

## Prerequisites

### System Requirements

**Per Coordinator**:
- Ubuntu 20.04+ or similar Linux distribution
- 2+ CPU cores (4+ recommended)
- 4GB+ RAM (8GB recommended)
- 20GB+ disk space
- Public IP address with open ports
- Domain name (for HTTPS, recommended)

**Required Software**:
- Docker 20.10+
- Docker Compose 1.29+
- (Optional) Nginx for reverse proxy
- (Optional) Certbot for SSL certificates

### Firewall Configuration

Open these ports:

```bash
# Coordinator API (required)
sudo ufw allow 5000/tcp

# Optional: HTTPS (recommended for production)
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp  # For SSL certificate validation
```

---

## Single Coordinator Setup

Before setting up federation, deploy a single coordinator to verify everything works.

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/ambient-intelligence.git
cd ambient-intelligence
```

### Step 2: Configure Environment

```bash
cp .env.example .env
nano .env
```

**Minimum configuration**:

```bash
# PostgreSQL
POSTGRES_DB=ambient
POSTGRES_USER=ambient
POSTGRES_PASSWORD=<GENERATE_STRONG_PASSWORD>

# Coordinator
COORDINATOR_PORT=5000
JWT_SECRET_KEY=<GENERATE_SECRET_KEY>
ADMIN_TOKEN=<GENERATE_ADMIN_TOKEN>

# Federation (disabled for now)
FEDERATION_ENABLED=false
```

**Generate secrets**:

```bash
# JWT secret (32+ characters)
openssl rand -base64 32

# Admin token
openssl rand -hex 32
```

### Step 3: Start Coordinator

```bash
docker-compose up -d postgres redis coordinator
```

### Step 4: Verify Health

```bash
# Check coordinator health
curl http://localhost:5000/health

# Expected response:
# {"status":"healthy","database":"connected","redis":"connected","active_nodes":0}

# Check network stats
curl http://localhost:5000/stats
```

### Step 5: Test Node Registration

Start a test node:

```bash
# Generate node keys
cd node
python -c "import nacl.public, base64; sk = nacl.public.PrivateKey.generate(); print('PRIVATE:', base64.b64encode(bytes(sk)).decode()); print('PUBLIC:', base64.b64encode(bytes(sk.public_key)).decode())"

# Add keys to .env
NODE_PRIVATE_KEY=<generated_private_key>
NODE_PUBLIC_KEY=<generated_public_key>
COORDINATOR_URL=http://localhost:5000

# Start node
docker-compose up -d node
```

Wait 60 seconds, then verify:

```bash
curl http://localhost:5000/nodes/discover

# Should return your node in the list
```

---

## Multi-Coordinator Federation

Once you have multiple coordinators running independently, configure federation.

### Scenario: 3-Coordinator Federation

**Coordinators**:
- Coordinator A: `coord-a.example.com` (US-East)
- Coordinator B: `coord-b.example.com` (EU-West)
- Coordinator C: `coord-c.example.com` (Asia-Pacific)

### Step 1: Deploy All Coordinators

Deploy each coordinator independently following the single coordinator setup.

**Coordinator A** (.env):
```bash
FEDERATION_ENABLED=false  # Will enable after all are running
```

**Coordinator B** (.env):
```bash
FEDERATION_ENABLED=false
```

**Coordinator C** (.env):
```bash
FEDERATION_ENABLED=false
```

Start all coordinators and verify each is healthy.

### Step 2: Configure Peer URLs

Update each coordinator's `.env`:

**Coordinator A**:
```bash
FEDERATION_ENABLED=true
PEER_COORDINATORS=https://coord-b.example.com,https://coord-c.example.com
FEDERATION_SYNC_INTERVAL=300
```

**Coordinator B**:
```bash
FEDERATION_ENABLED=true
PEER_COORDINATORS=https://coord-a.example.com,https://coord-c.example.com
FEDERATION_SYNC_INTERVAL=300
```

**Coordinator C**:
```bash
FEDERATION_ENABLED=true
PEER_COORDINATORS=https://coord-a.example.com,https://coord-b.example.com
FEDERATION_SYNC_INTERVAL=300
```

### Step 3: Restart Coordinators

```bash
# On each server
docker-compose restart coordinator
```

### Step 4: Verify Federation

Wait 5 minutes for initial sync, then check federation status:

```bash
# Check peers on Coordinator A
curl https://coord-a.example.com/federation/peers

# Expected response:
{
  "peers": [
    {
      "url": "https://coord-b.example.com",
      "last_sync": "2025-01-16T12:05:00Z",
      "status": "healthy",
      "error_count": 0,
      "total_syncs": 1
    },
    {
      "url": "https://coord-c.example.com",
      "last_sync": "2025-01-16T12:05:00Z",
      "status": "healthy",
      "error_count": 0,
      "total_syncs": 1
    }
  ],
  "stats": {
    "total_peers": 2,
    "healthy_peers": 2,
    "recent_syncs": 2,
    "federation_enabled": true
  }
}
```

### Step 5: Verify Node Synchronization

Register a node with Coordinator A, then check if it appears on Coordinator B:

```bash
# Register node with Coordinator A
# (node sends heartbeat to coord-a.example.com)

# Wait 5 minutes for sync

# Query Coordinator B
curl https://coord-b.example.com/nodes/discover

# Node should appear in results!
```

---

## Production Deployment

### HTTPS Setup with Nginx

**Install Nginx and Certbot**:

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

**Nginx Configuration** (`/etc/nginx/sites-available/coordinator`):

```nginx
server {
    listen 80;
    server_name coord-a.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS headers (if needed for web clients)
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
    }
}
```

**Enable site**:

```bash
sudo ln -s /etc/nginx/sites-available/coordinator /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**Get SSL certificate**:

```bash
sudo certbot --nginx -d coord-a.example.com
```

**Test HTTPS**:

```bash
curl https://coord-a.example.com/health
```

### Database Backups

**Automated daily backups**:

```bash
# Create backup script
cat > /usr/local/bin/backup-coordinator.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/backups/coordinator
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec ambient-postgres pg_dump -U ambient ambient > \
  $BACKUP_DIR/ambient_$DATE.sql

# Compress
gzip $BACKUP_DIR/ambient_$DATE.sql

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
EOF

chmod +x /usr/local/bin/backup-coordinator.sh
```

**Add to crontab**:

```bash
sudo crontab -e

# Add this line:
0 2 * * * /usr/local/bin/backup-coordinator.sh
```

### Resource Limits

**Update docker-compose.yml** for production:

```yaml
coordinator:
  # ... existing config ...
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 4G
      reservations:
        cpus: '1.0'
        memory: 2G
  restart: unless-stopped
```

### Monitoring

**Health check script**:

```bash
cat > /usr/local/bin/check-coordinator.sh << 'EOF'
#!/bin/bash
HEALTH=$(curl -s http://localhost:5000/health | jq -r '.status')

if [ "$HEALTH" != "healthy" ]; then
  echo "Coordinator unhealthy! Status: $HEALTH"
  # Send alert (email, Slack, PagerDuty, etc.)
  exit 1
fi
EOF

chmod +x /usr/local/bin/check-coordinator.sh
```

**Run every 5 minutes**:

```bash
*/5 * * * * /usr/local/bin/check-coordinator.sh
```

---

## Monitoring & Troubleshooting

### Check Logs

```bash
# Coordinator logs
docker-compose logs -f coordinator

# Database logs
docker-compose logs -f postgres

# All services
docker-compose logs -f
```

### Common Issues

**Federation not syncing**:

```bash
# Check logs for sync errors
docker-compose logs coordinator | grep -i federation

# Verify peer URLs are reachable
curl https://peer-coordinator.com/health

# Check firewall
sudo ufw status
```

**Database connection errors**:

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker exec -it ambient-postgres psql -U ambient -d ambient -c "SELECT COUNT(*) FROM nodes;"
```

**Nodes not appearing**:

```bash
# Check heartbeat timeout
docker-compose exec coordinator env | grep HEARTBEAT

# Check node logs
docker-compose logs node | grep heartbeat

# Manually query database
docker exec -it ambient-postgres psql -U ambient -d ambient -c "SELECT node_id, ip_address, last_heartbeat FROM nodes;"
```

### Monitoring Dashboard

Access the web dashboard:

```
https://coord-a.example.com/dashboard.html
```

**Features**:
- Real-time network statistics
- Active node list
- Federation peer status
- Auto-refresh every 10 seconds
- Export stats to JSON

---

## Security Best Practices

### 1. Environment Variables

**Never commit secrets**:

```bash
# Always in .gitignore
.env
*.key
*.pem
```

**Rotate secrets regularly**:

```bash
# Generate new JWT secret
openssl rand -base64 32

# Update .env
JWT_SECRET_KEY=<new_secret>

# Restart coordinator
docker-compose restart coordinator
```

### 2. Network Security

**Use HTTPS everywhere**:
- Federation peers MUST use HTTPS in production
- Self-signed certificates NOT recommended

**Restrict database access**:

```yaml
# docker-compose.yml
postgres:
  networks:
    - ambient_network  # Internal network only
  # Do NOT expose ports externally
```

### 3. Rate Limiting

**Configure in .env**:

```bash
MAX_REQUESTS_PER_MINUTE=60
ABUSE_REPORT_THRESHOLD=3
ABUSE_BLOCK_DURATION_HOURS=24
```

### 4. Admin Endpoints

Protect admin endpoints with strong tokens:

```bash
# Generate strong admin token
ADMIN_TOKEN=$(openssl rand -hex 32)

# Use in requests
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://coord-a.example.com/federation/register \
  -d '{"peer_url":"https://new-peer.com"}'
```

### 5. Database Security

**Use strong passwords**:

```bash
POSTGRES_PASSWORD=$(openssl rand -base64 24)
```

**Regular backups** (see Production Deployment section)

**Monitor for suspicious activity**:

```sql
-- Check for unusual node patterns
SELECT ip_address, COUNT(*) as node_count
FROM nodes
GROUP BY ip_address
HAVING COUNT(*) > 10;

-- Check abuse reports
SELECT ip_address, COUNT(*) as report_count
FROM abuse_reports
GROUP BY ip_address
ORDER BY report_count DESC
LIMIT 10;
```

---

## Testing Federation

### Local Testing with Docker Compose

Test federation locally with 3 coordinators:

```bash
# Create test directory
mkdir test-federation
cd test-federation

# Copy base files
cp ../docker-compose.yml .
```

**Create docker-compose.override.yml**:

```yaml
version: '3.8'

services:
  coordinator-a:
    build: ../coordinator
    ports:
      - "5001:5000"
    environment:
      - DATABASE_URL=postgresql://ambient:ambient@postgres-a:5432/ambient
      - REDIS_URL=redis://redis-a:6379/0
      - FEDERATION_ENABLED=true
      - PEER_COORDINATORS=http://coordinator-b:5000,http://coordinator-c:5000
    depends_on:
      - postgres-a
      - redis-a
    networks:
      - fed_network

  coordinator-b:
    build: ../coordinator
    ports:
      - "5002:5000"
    environment:
      - DATABASE_URL=postgresql://ambient:ambient@postgres-b:5432/ambient
      - REDIS_URL=redis://redis-b:6379/0
      - FEDERATION_ENABLED=true
      - PEER_COORDINATORS=http://coordinator-a:5000,http://coordinator-c:5000
    depends_on:
      - postgres-b
      - redis-b
    networks:
      - fed_network

  coordinator-c:
    build: ../coordinator
    ports:
      - "5003:5000"
    environment:
      - DATABASE_URL=postgresql://ambient:ambient@postgres-c:5432/ambient
      - REDIS_URL=redis://redis-c:6379/0
      - FEDERATION_ENABLED=true
      - PEER_COORDINATORS=http://coordinator-a:5000,http://coordinator-b:5000
    depends_on:
      - postgres-c
      - redis-c
    networks:
      - fed_network

  postgres-a:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=ambient
      - POSTGRES_USER=ambient
      - POSTGRES_PASSWORD=ambient
    networks:
      - fed_network

  postgres-b:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=ambient
      - POSTGRES_USER=ambient
      - POSTGRES_PASSWORD=ambient
    networks:
      - fed_network

  postgres-c:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=ambient
      - POSTGRES_USER=ambient
      - POSTGRES_PASSWORD=ambient
    networks:
      - fed_network

  redis-a:
    image: redis:7-alpine
    networks:
      - fed_network

  redis-b:
    image: redis:7-alpine
    networks:
      - fed_network

  redis-c:
    image: redis:7-alpine
    networks:
      - fed_network

networks:
  fed_network:
    driver: bridge
```

**Start federation**:

```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

**Test sync**:

```bash
# Add node to coordinator A
curl -X POST http://localhost:5001/nodes/announce \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "test-node-1",
    "ip_address": "192.168.1.100",
    "port": 8000,
    "public_key": "test_key_123",
    "models": ["llama3:8b"]
  }'

# Wait 5 minutes

# Check coordinator B
curl http://localhost:5002/nodes/discover

# Should include test-node-1!
```

---

## Conclusion

You now have a fully functional federated Ambient Intelligence network!

**Next Steps**:
- Monitor federation health regularly
- Add more coordinators as network grows
- Implement monitoring alerts
- Contribute improvements to the protocol

**Resources**:
- [Protocol Specification](../protocol/SPECIFICATION.md)
- [API Documentation](API.md)
- [Governance](GOVERNANCE.md)

**Questions?** Open an issue on GitHub or check the community channels.

---

**Built with decentralization in mind. No single point of control. No single point of failure.**
