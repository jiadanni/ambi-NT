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

## Current Status: Phase 0 - Smoke Test

Phase 0 validates the core cryptographic design with a simple client-server setup.

**What's Working:**
- ✅ End-to-end encryption with NaCl/libsodium
- ✅ Node server that processes encrypted prompts
- ✅ CLI client for submitting queries
- ✅ Zero plaintext leakage (verified by tests)

**Coming Next:**
- Phase 1: Dockerized deployment, web client, voice input
- Phase 2: Coordinator service, node discovery, priority tokens
- Phase 3: Federation, protocol specification, true autonomy

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [Ollama](https://ollama.com/) installed locally
- 8GB+ RAM recommended

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/ambient-intelligence.git
   cd ambient-intelligence
   ```

2. **Install Ollama and pull a model:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull llama3:8b
   ```

3. **Set up the node:**
   ```bash
   cd node
   pip install -r requirements.txt

   # Generate keypair
   python crypto.py

   # Copy the output to a new .env file in the project root
   cd ..
   cp .env.example .env
   # Edit .env and paste the generated keys
   ```

4. **Start Ollama:**
   ```bash
   ollama serve
   ```

5. **Start the node (in a new terminal):**
   ```bash
   cd node
   python server.py
   ```

6. **Install the CLI client (in another terminal):**
   ```bash
   cd client-cli
   pip install -r requirements.txt
   ```

7. **Submit your first query:**
   ```bash
   python client.py "What is 2+2?"
   ```

You should see output like:
```
Ambient Intelligence - Privacy-First AI
============================================================
Node: http://localhost:8000
Prompt: What is 2+2?
============================================================

[Encrypting and submitting to http://localhost:8000...]
[Job ID: 8b5c2e4a-9f3d-4c5e-a1b2-3d4e5f6a7b8c]
[Waiting for response ........ ✓] (15.3s)

============================================================
Response:
============================================================
The answer is 4.

2 + 2 = 4
============================================================
```

## Architecture

```
┌─────────────┐                    ┌──────────────┐
│   Client    │                    │     Node     │
│             │                    │              │
│  1. Generate├───── Encrypted ───→│  3. Decrypt  │
│  ephemeral  │      Prompt        │  with node   │
│  keypair    │                    │  private key │
│             │                    │              │
│  2. Encrypt │                    │  4. Process  │
│  prompt with│                    │  with Ollama │
│  node pubkey│                    │              │
│             │                    │  5. Encrypt  │
│  6. Decrypt │◄─── Encrypted ─────┤  response    │
│  response   │      Response      │  with client │
│             │                    │  pubkey      │
└─────────────┘                    └──────────────┘
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
│   ├── server.py          # FastAPI server
│   ├── crypto.py          # Encryption/decryption
│   ├── ollama_client.py   # Ollama interface
│   ├── config.py          # Configuration management
│   ├── models.py          # Data models
│   └── requirements.txt
│
├── client-cli/            # Command-line client
│   ├── client.py          # Main CLI application
│   ├── crypto.py          # Client-side encryption
│   └── requirements.txt
│
├── client-web/            # Web client (Phase 1+)
├── coordinator/           # Coordinator service (Phase 2+)
├── tests/                 # Test suite
│   └── test_phase0.py    # Phase 0 tests
│
├── .env.example           # Configuration template
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

## Development Roadmap

### Phase 0: Smoke Test ✅ (Current)
- [x] Core encryption working
- [x] Node server operational
- [x] CLI client functional
- [x] Tests passing

### Phase 1: Trusted Network (Weeks 2-3)
- [ ] Dockerized node deployment
- [ ] Web client
- [ ] Voice input prototype
- [ ] Tailscale integration guide
- [ ] 10+ users onboarded

### Phase 2: Public Beta (Weeks 4-6)
- [ ] Coordinator service
- [ ] Node discovery
- [ ] Priority token system
- [ ] Abuse reporting
- [ ] 100+ daily active users

### Phase 3: Federation & Autonomy (Weeks 7-8+)
- [ ] Protocol specification
- [ ] Coordinator federation
- [ ] Community governance
- [ ] Alternative implementations

## FAQ

**Q: How is this different from other AI networks?**
A: Most networks require you to trust the operator. Ambient Intelligence uses encryption so operators literally cannot see your data, even if they wanted to.

**Q: Is this production-ready?**
A: Not yet. Phase 0 is a proof-of-concept. Use at your own risk.

**Q: Can I run this on a VPS?**
A: Yes! Phase 1 will include Docker deployment guides for VPS providers.

**Q: What models are supported?**
A: Any model supported by Ollama. Default is llama3:8b.

**Q: How much does it cost to run a node?**
A: Just your compute costs. There are no fees or tokens (yet). Phase 2 will introduce optional priority tokens.

**Q: Is my data really private?**
A: Yes, by design. The encryption ensures nodes cannot decrypt your prompts. Read the code to verify.

**Q: Can I use this for commercial purposes?**
A: Yes, under the MIT license. Fork it, modify it, use it however you want.

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

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
