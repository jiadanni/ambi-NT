# Quick Deploy Guide - TL;DR Version

For those who want the absolute fastest path to deployment.

---

## 5-Minute Quick Start (Local Testing)

```bash
# 1. Start services
docker-compose up -d

# 2. Wait for Ollama (30 seconds)
sleep 30

# 3. Test it works
python client.py "What is Python?" --wait

# 4. Try conversation mode
python client-cli/conversation_client.py
```

**Done!** If all 4 steps worked, your system is running.

---

## 30-Minute Production Deploy (Cloud Server)

```bash
# On your cloud server (DigitalOcean, AWS, etc.)

# 1. Install Docker
curl -fsSL https://get.docker.com | sh

# 2. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. Clone repo
git clone <your-repo-url>
cd ambi-NT-Phase3
git checkout claude/phase-3-federation-autonomy-01PzfLCTdTGjgDZP4d1zAa3n

# 4. Configure firewall
sudo ufw allow 22
sudo ufw allow 5000
sudo ufw allow 8000
sudo ufw enable

# 5. Start services
docker-compose up -d

# 6. Wait and test
sleep 30
curl http://localhost:8000/health
```

---

## First User Onboarding (10 Minutes)

**Send them this**:

```
Hi! Here's how to use the AI network:

1. Install Python 3.9+
2. Clone: git clone <repo-url>
3. Install: pip install -r requirements.txt
4. Run: python client.py "your question" --wait

For conversations:
python client-cli/conversation_client.py

Server: http://<your-server-ip>:5000
```

---

## Critical Commands

```bash
# Check if running
docker-compose ps

# View logs
docker-compose logs -f

# Restart everything
docker-compose restart

# Stop everything
docker-compose down

# Check metrics
curl http://localhost:8000/metrics | jq

# Run tests
pytest tests/ -v
```

---

## Troubleshooting One-Liners

```bash
# Connection refused?
docker-compose restart

# Jobs stuck?
docker-compose restart ollama

# Out of memory?
docker-compose down && docker-compose up -d

# Reset everything?
docker-compose down -v && docker-compose up -d
```

---

## When to Scale

- **2-10 users**: Current setup is fine
- **10-100 users**: Add more resources (8GB RAM)
- **100-1000 users**: Add Redis, multiple nodes
- **1000+ users**: Read the full roadmap

---

**Full Guide**: See `DEPLOYMENT_CHECKLIST.md` for detailed steps.
