# Ambient Intelligence

**Privacy-First Decentralized AI Inference Network**

Ambient Intelligence is a decentralized network that allows users to share compute resources for running language models without compromising privacy. Using end-to-end encryption, node operators never see the plaintext of prompts or responses they process.

## Core Philosophy

Build a self-sustaining network that becomes more valuable as it grows, without central control or monetization pressures that lead to enshittification.

## Key Features

- **End-to-End Encryption**: Prompts are encrypted on your device before leaving. Nodes process them without seeing plaintext.
- **Privacy-First**: No data collection, no tracking, no history (by default).
- **Decentralized**: No single point of control or failure.
- **Forward Secrecy**: Ephemeral client keys ensure past sessions remain secure even if keys are compromised.
- **Open Source**: Fully transparent, auditable, and forkable.

## Current Status: Phase 3 - Federation & Autonomy 🎉

The network is now fully decentralized and autonomous with multi-coordinator federation!

**What's Working:**
- ✅ End-to-end encryption with NaCl/libsodium
- ✅ Dockerized one-command deployment
- ✅ Beautiful web client with voice input
- ✅ **Coordinator service with node discovery**
- ✅ **Priority token system**
- ✅ **Abuse detection and prevention**
- ✅ **Multi-coordinator federation with gossip protocol**
- ✅ **Formal protocol specification (v1.0)**
- ✅ **Network monitoring dashboard**
- ✅ **Community governance framework**
- ✅ Zero plaintext leakage (verified by tests)

**What's New in Phase 3:**
- 🔗 **Federation**: Multiple coordinators can sync to create unified network
- 📋 **Protocol Spec**: Formal specification for alternative implementations
- 🌐 **Monitoring Dashboard**: Real-time network health visualization
- 📚 **Complete API docs**: Full documentation for all endpoints
- 🏛️ **Governance**: Community-driven decision making framework

## Quick Start (Docker - Recommended)

**One command to rule them all:**

```bash
git clone https://github.com/yourusername/ambient-intelligence.git
cd ambient-intelligence
./scripts/docker-setup.sh
```

This will:
- ✅ Check requirements
- ✅ Generate crypto keys
- ✅ Build Docker images
- ✅ Start node and web client
- ✅ Pull Ollama model

**Access:**
- 🌐 **Web Client**: http://localhost:8080
- 📊 **Network Dashboard**: http://localhost:8080/dashboard.html
- 🔧 **Node API**: http://localhost:8000
- 🏢 **Coordinator API**: http://localhost:5000
- 💚 **Health Check**: http://localhost:8000/health
- 📈 **Network Stats**: http://localhost:5000/stats

### Quick Start (Manual)

For developers who prefer manual setup:

1. **Install Prerequisites:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull llama3:8b
   ```

2. **Setup and Run:**
   ```bash
   ./scripts/setup.sh
   ollama serve &
   python node/server.py
   ```

3. **Use Web Client:**
   ```bash
   # Serve the web client
   cd client-web
   python -m http.server 8080
   # Open http://localhost:8080
   ```

4. **Or Use CLI Client:**
   ```bash
   cd client-cli
   pip install -r requirements.txt
   python client.py "What is 2+2?"
   ```

**See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete installation guide.**

## Architecture

### Complete Network Architecture (Phase 3)

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ Coordinator  │◄──────► │ Coordinator  │◄──────► │ Coordinator  │
│   (US-East)  │  Gossip │   (EU-West)  │  Gossip │  (Asia-Pac)  │
│              │ Protocol│              │ Protocol│              │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │ Heartbeats             │                        │
       │ & Discovery            │                        │
       │                        │                        │
    ┌──▼────┐  ┌─────┐      ┌──▼────┐  ┌─────┐      ┌──▼────┐
    │ Node  │  │Node │      │ Node  │  │Node │      │ Node  │
    │   1   │  │  2  │      │   3   │  │  4  │      │   5   │
    └───────┘  └─────┘      └───────┘  └─────┘      └───────┘
       ▲                        ▲                        ▲
       │ Encrypted Jobs         │                        │
       │                        │                        │
    ┌──┴───────────────────────┴────────────────────────┴───┐
    │                      Clients                           │
    │  (Web, CLI, Mobile - with ephemeral encryption keys)   │
    └────────────────────────────────────────────────────────┘
```

### Request Flow (Client → Node)

```
1. Client queries Coordinator for available nodes
2. Coordinator returns list sorted by uptime & load
3. Client generates ephemeral keypair
4. Client encrypts prompt with Node's public key
5. Client submits encrypted job to Node
6. Node decrypts prompt (in memory only)
7. Node processes with Ollama
8. Node encrypts response with Client's public key
9. Client retrieves and decrypts response
10. Client discards ephemeral key
```

### Federation Sync (Coordinator ↔ Coordinator)

```
Every 5 minutes:
1. Each Coordinator queries peers for node lists
2. Merge remote nodes with local database
3. Deduplicate by node_id
4. Resolve conflicts (prefer most recent heartbeat)
5. Result: Unified network view across all coordinators
```

### Privacy Guarantees

1. **Node Never Sees Plaintext**: Prompts and responses are only decrypted in memory, never logged or stored.
2. **Forward Secrecy**: Client generates new ephemeral keys for each session.
3. **No Tracking**: No user accounts, no session tracking, no analytics.
4. **No History**: By default, nothing is saved. Enable history at your own risk (with encryption).

## Project Structure

```
ambient-intelligence/
├── node/                   # Node server components
│   ├── server.py          # FastAPI server with heartbeats
│   ├── crypto.py          # Encryption/decryption (NaCl)
│   ├── ollama_client.py   # Ollama interface
│   ├── config.py          # Configuration management
│   ├── models.py          # Data models
│   ├── Dockerfile         # Docker image
│   └── requirements.txt
│
├── coordinator/           # Coordinator service (Phase 2+)
│   ├── server.py          # Discovery & federation API
│   ├── federation.py      # Gossip protocol implementation
│   ├── models.py          # Database models (SQLAlchemy)
│   ├── database.py        # Database setup and sessions
│   ├── config.py          # Coordinator configuration
│   ├── Dockerfile         # Docker image
│   └── requirements.txt
│
├── client-cli/            # Command-line client
│   ├── client.py          # Main CLI application
│   ├── crypto.py          # Client-side encryption
│   └── requirements.txt
│
├── client-web/            # Web clients
│   ├── index.html         # Main UI with voice input
│   ├── dashboard.html     # Network monitoring dashboard
│   └── 404.html
│
├── protocol/              # Protocol specification (Phase 3)
│   └── SPECIFICATION.md   # Formal protocol v1.0
│
├── scripts/               # Deployment scripts
│   ├── docker-setup.sh    # One-command Docker deployment
│   ├── setup.sh           # Manual setup helper
│   └── verify_crypto.py   # Crypto verification
│
├── docs/                  # Documentation
│   ├── DEPLOYMENT.md      # Full deployment guide
│   ├── TAILSCALE.md       # Tailscale integration
│   ├── API.md             # Complete API documentation
│   └── GOVERNANCE.md      # Community governance
│
├── tests/                 # Test suite
│   └── test_phase0.py    # Comprehensive crypto tests
│
├── docker-compose.yml     # Full stack deployment
├── nginx.conf            # Web client server config
├── .env.example          # Configuration template
├── .gitignore
└── README.md
```

## Running Tests

```bash
cd tests
pip install pytest PyNaCl
pytest test_phase0.py -v
```

All tests should pass:
- ✅ Keypair generation
- ✅ Encryption/decryption round-trip
- ✅ Security properties (nonce randomness, auth failures)
- ✅ Unicode handling
- ✅ Large message support

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
# Node Configuration
NODE_ID=<auto-generated>
NODE_PORT=8000
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:8b
MAX_CONCURRENT_JOBS=1
JOB_TIMEOUT_SECONDS=120

# Encryption
NODE_PRIVATE_KEY=<generated-key>
NODE_PUBLIC_KEY=<generated-key>

# Client
DEFAULT_NODE_URL=http://localhost:8000
```

**Important**: Never commit your `.env` file! It contains your private key.

## Federation Setup (Phase 3)

To run a coordinator that federates with others:

```bash
# Enable federation
FEDERATION_ENABLED=true

# Configure peer coordinators (comma-separated)
PEER_COORDINATORS=https://coord1.example.com,https://coord2.example.com

# Sync interval (default: 300 seconds = 5 minutes)
FEDERATION_SYNC_INTERVAL=300
```

**How Federation Works**:
1. Each coordinator maintains its own database of nodes
2. Every 5 minutes, coordinators query their peers for node lists
3. Nodes are merged and deduplicated by `node_id`
4. Conflicts are resolved using most recent heartbeat
5. Result: All coordinators share a unified view of the network

**See [protocol/SPECIFICATION.md](protocol/SPECIFICATION.md#6-federation-protocol)** for complete federation protocol details.

## API Documentation

Complete API documentation is available:

- **[docs/API.md](docs/API.md)**: Full API reference for nodes and coordinators
- **[protocol/SPECIFICATION.md](protocol/SPECIFICATION.md)**: Formal protocol specification v1.0
- **[docs/GOVERNANCE.md](docs/GOVERNANCE.md)**: Community governance and contribution guidelines

**Quick API Examples**:

```bash
# Discover available nodes
curl http://localhost:5000/nodes/discover?limit=5

# Check network statistics
curl http://localhost:5000/stats

# Get federation status
curl http://localhost:5000/federation/peers

# Check node health
curl http://localhost:8000/health
```

## Development Roadmap

### Phase 0: Smoke Test ✅ (Complete)
- [x] Core encryption working
- [x] Node server operational
- [x] CLI client functional
- [x] Tests passing

### Phase 1: Trusted Network ✅ (Complete)
- [x] Dockerized node deployment
- [x] Web client with beautiful UI
- [x] Voice input integrated
- [x] Tailscale integration guide
- [x] One-command setup scripts
- [x] Comprehensive documentation

### Phase 2: Public Beta ✅ (Complete)
- [x] Coordinator service with PostgreSQL & Redis
- [x] Node discovery and registration
- [x] Priority token system with JWT
- [x] Abuse reporting and IP blocking
- [x] Network statistics and health monitoring
- [x] Heartbeat mechanism for node tracking
- [x] Docker Compose orchestration

### Phase 3: Federation & Autonomy ✅ (Complete!)
- [x] **Formal protocol specification v1.0**
- [x] **Coordinator federation with gossip protocol**
- [x] **Multi-coordinator node synchronization**
- [x] **Network monitoring dashboard**
- [x] **Complete API documentation**
- [x] **Community governance framework**
- [x] Conflict resolution for federated nodes
- [x] Federation health tracking

### Phase 4: Ecosystem Growth (Community-Driven)
- [ ] Alternative client implementations (Rust, Go, mobile)
- [ ] 100+ daily active users
- [ ] Community-run coordinators
- [ ] Protocol improvements and versioning
- [ ] Additional language bindings
- [ ] Performance benchmarks
- [ ] Security audits

## FAQ

**Q: How is this different from other AI networks?**
A: Most networks require you to trust the operator. Ambient Intelligence uses encryption so operators literally cannot see your data, even if they wanted to.

**Q: Is this production-ready?**
A: Phase 1 is ready for trusted deployment with friends. Full production-readiness comes in Phase 2 with coordinator services and scaling.

**Q: Can I run this on a VPS?**
A: Yes! See docs/DEPLOYMENT.md for complete VPS deployment guides. Docker makes it easy.

**Q: What models are supported?**
A: Any model supported by Ollama. Default is llama3:8b.

**Q: How much does it cost to run a node?**
A: Just your compute costs. There are no fees or tokens (yet). Phase 2 will introduce optional priority tokens.

**Q: Is my data really private?**
A: Yes, by design. The encryption ensures nodes cannot decrypt your prompts. Read the code to verify.

**Q: Can I use this for commercial purposes?**
A: Yes, under the MIT license. Fork it, modify it, use it however you want.

## Contributing

We welcome contributions of all kinds! This is a community-driven project.

**Quick Start**:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Submit a pull request

**See [docs/GOVERNANCE.md](docs/GOVERNANCE.md) for**:
- Contribution guidelines
- Code quality standards
- Decision-making process
- Code of conduct
- Community roles

**High Priority Contributions**:
- Security audits and improvements
- Alternative client implementations (Rust, Go, mobile)
- Documentation improvements
- Performance optimizations
- Running public coordinators

## Security

If you discover a security vulnerability, please email security@ambient-intelligence.network (or create a private issue if that email doesn't exist yet).

**Do NOT** create public issues for security vulnerabilities.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Ollama](https://ollama.com/) for making local AI accessible
- [NaCl/libsodium](https://libsodium.gitbook.io/) for foolproof cryptography
- The open-source community

## Contact

- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For questions and ideas
- **Matrix**: [Coming in Phase 1]

---

**Built with privacy in mind. No tracking. No data collection. No enshittification.**
