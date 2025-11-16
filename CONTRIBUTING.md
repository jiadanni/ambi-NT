# Contributing to Ambient Intelligence

Thank you for your interest in contributing! This project aims to build a privacy-first, decentralized AI inference network that can't be enshittified.

## Code of Conduct

- Be respectful and constructive
- Focus on technical merit
- Privacy and security are paramount
- No tracking, analytics, or data collection features
- Keep it simple and auditable

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/ambient-intelligence.git`
3. Create a feature branch: `git checkout -b feature/my-feature`
4. Make your changes
5. Run tests: `pytest tests/ -v`
6. Commit with clear messages: `git commit -m "feat: Add XYZ"`
7. Push to your fork: `git push origin feature/my-feature`
8. Open a pull request

## Development Setup

```bash
# Install dependencies for all components
cd node && pip install -r requirements.txt && cd ..
cd client-cli && pip install -r requirements.txt && cd ..
cd tests && pip install -r requirements.txt && cd ..

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b

# Run setup script
./scripts/setup.sh

# Run tests
pytest tests/test_phase0.py -v
```

## Code Style

### Python
- Follow PEP 8
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use descriptive variable names
- Add docstrings to all functions and classes

Example:
```python
def encrypt_message(plaintext: str, public_key: str) -> str:
    """
    Encrypt a message using the recipient's public key.

    Args:
        plaintext: The message to encrypt
        public_key: Base64-encoded recipient public key

    Returns:
        Base64-encoded encrypted message

    Raises:
        ValueError: If encryption fails
    """
    # Implementation...
```

### JavaScript (for web client)
- Use ESLint with Standard config
- Prefer `const` over `let`
- Use async/await over promises
- No semicolons (Standard style)

### Dart (for mobile client)
- Follow official Dart style guide
- Use `flutter analyze` before committing
- No analytics or tracking code

## Commit Messages

Use conventional commits format:

- `feat: Add new feature`
- `fix: Fix a bug`
- `docs: Update documentation`
- `test: Add or update tests`
- `refactor: Refactor code without changing behavior`
- `perf: Performance improvements`
- `chore: Maintenance tasks`

Examples:
```
feat: Add voice input to web client
fix: Resolve encryption key mismatch in node
docs: Update installation guide for macOS
test: Add integration tests for Phase 2 coordinator
```

## Testing

All code changes must include tests:

- Unit tests for new functions
- Integration tests for new features
- Security tests for crypto changes

Run tests before submitting:
```bash
pytest tests/ -v --cov=node --cov=client-cli
```

## Security

### Reporting Vulnerabilities

**DO NOT** create public issues for security vulnerabilities.

Contact: security@ambient-intelligence.network

### Security Guidelines

- Never log or store plaintext prompts/responses
- Always use constant-time comparisons for secrets
- Validate all inputs (especially encrypted data)
- Use prepared statements for database queries
- Rate limit all endpoints
- Never disable TLS in production

## Pull Request Process

1. **Before submitting:**
   - Ensure all tests pass
   - Update documentation
   - Add tests for new features
   - Follow code style guidelines
   - Rebase on latest main branch

2. **PR Description should include:**
   - What problem does this solve?
   - How does it solve it?
   - Any breaking changes?
   - Screenshots (if UI changes)

3. **Review process:**
   - At least one maintainer must approve
   - All CI checks must pass
   - Security-sensitive changes require security review

4. **After approval:**
   - Maintainer will merge (no force-push after approval)
   - Delete your feature branch

## Areas for Contribution

### Phase 0 (Current)
- [ ] Improve error handling
- [ ] Add more comprehensive tests
- [ ] Performance optimization
- [ ] Better documentation

### Phase 1 (Next)
- [ ] Docker deployment
- [ ] Web client implementation
- [ ] Voice input integration
- [ ] Tailscale setup guide

### Phase 2
- [ ] Coordinator service
- [ ] Node discovery protocol
- [ ] Priority token system
- [ ] Abuse detection

### Phase 3
- [ ] Protocol specification
- [ ] Federation implementation
- [ ] Alternative language implementations (Rust, Go)
- [ ] Mobile client (Flutter)

## Documentation

When adding features, update:
- README.md (if user-facing)
- Code comments (explain WHY, not just WHAT)
- API documentation (for new endpoints)
- Configuration examples (for new env vars)

## Questions?

- Open a GitHub Discussion for questions
- Check existing issues and PRs
- Read the implementation guide
- Ask in Matrix chat (coming in Phase 1)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Remember: Privacy first. No tracking. No enshittification.**
