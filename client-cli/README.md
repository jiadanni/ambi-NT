# Ambient Intelligence CLI Client

A command-line interface for interacting with the Ambient Intelligence network.

## Installation

```bash
cd client-cli
pip install -r requirements.txt
chmod +x ambient_cli.py

# Optional: Add to PATH for easy access
ln -s $(pwd)/ambient_cli.py /usr/local/bin/ambient
```

## Quick Start

### 1. Initialize Configuration

```bash
# Create default config file
ambient config --init

# Edit configuration
nano ~/.config/ambient/config.toml
```

### 2. Basic Usage

```bash
# Ask a question
ambient ask "What's the capital of France?"

# Ask with specific model
ambient ask "Explain quantum computing" --model llama3:70b

# Watch for new responses (for async/background processing)
ambient listen

# View conversation history
ambient history --today
ambient history --days 7

# List available nodes
ambient nodes

# Show current configuration
ambient config --show
```

## Configuration

Configuration is stored in `~/.config/ambient/config.toml`. See `config.example.toml` for all available options.

### Key Configuration Sections

#### Coordinator Settings
```toml
[coordinator]
primary = "https://bootstrap.ambient.network"
fallbacks = ["https://alt1.ambient.network"]
timeout = 10
```

#### Model Preferences
```toml
[preferences]
model = "llama3:8b"
fallback_models = ["mistral:7b", "llama2:7b"]
timeout = 300
conversation_mode = true
max_context_tokens = 4096
```

#### Security
```toml
[security]
private_key_path = "~/.config/ambient/keys/private.pem"
public_key_path = "~/.config/ambient/keys/public.pem"
verify_node_signatures = true
```

#### Audio Settings (for voice mode)
```toml
[audio]
sample_rate = 16000
format = "wav"
max_length = 60  # seconds
```

## Advanced Usage

### Conversation Mode

By default, the CLI maintains conversation context:

```bash
ambient ask "What is Python?"
ambient ask "What are its main features?"  # Continues previous conversation
ambient ask "Show me an example"           # Still in context
```

### Voice-Only Mode

When `voice_only = true` in config:

```bash
# Record and send voice prompt
ambient voice

# Transcription happens automatically before sending to network
```

### Custom Configuration File

```bash
ambient --config /path/to/custom/config.toml ask "Hello"
```

## Architecture

The CLI is designed to be simple and privacy-focused:

1. **No User Tracking**: All identifiers are ephemeral or hashed
2. **Local Keys**: Encryption keys stored locally, never transmitted
3. **Session Cache**: Optional local caching for faster multi-turn conversations
4. **Fallback Coordinators**: Automatic failover if primary is unavailable

## Integration with Existing Clients

This CLI can work alongside or replace the existing clients:

- `client.py` - Original simple client
- `conversation_client.py` - Conversation-aware client

The new CLI provides a better user experience while maintaining compatibility with the protocol.

## Development

To extend the CLI:

```python
# Add new command in ambient_cli.py

# 1. Add subparser
my_parser = subparsers.add_parser("mycommand", help="My command")
my_parser.add_argument("--option", help="An option")

# 2. Add method to AmbientCLI class
async def my_command(self, option: str):
    # Implementation
    pass

# 3. Add to main() command dispatcher
elif args.command == "mycommand":
    await cli.my_command(args.option)
```

## Requirements

- Python 3.8+
- Dependencies in `requirements.txt`:
  - `tomli` (Python <3.11) or `tomllib` (Python 3.11+)
  - `aiohttp` for async HTTP
  - Other dependencies from conversation_client.py

## Future Enhancements

- [ ] Shell completion (bash/zsh)
- [ ] Streaming responses with progress indication
- [ ] Voice input/output integration
- [ ] Local model caching
- [ ] Batch processing
- [ ] Session management UI
- [ ] Node reputation visualization

## Privacy & Security

- **No telemetry**: The CLI never phones home
- **Local-first**: All data cached locally
- **Encrypted transport**: All network communication encrypted
- **Key isolation**: Private keys never leave your machine

## License

See LICENSE file in repository root.
