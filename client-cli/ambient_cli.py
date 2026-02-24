#!/usr/bin/env python3
"""
Ambient Intelligence CLI Client

A command-line interface for the Ambient Intelligence network.

Usage:
    ambient ask "What's the capital of France?"
    ambient listen                      # Watch for new responses
    ambient history --today            # Show conversation history
    ambient config --show              # Show current configuration
    ambient nodes                      # List available nodes
    
Configuration:
    Configuration is loaded from ~/.config/ambient/config.toml
    See config.example.toml for all available options.
"""

import sys
import os
import argparse
import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Try to import tomli/tomllib for TOML parsing
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("Error: TOML parsing requires tomli (Python <3.11) or tomllib (Python 3.11+)")
        print("Install with: pip install tomli")
        sys.exit(1)


class AmbientConfig:
    """Configuration manager for Ambient CLI."""
    
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ambient" / "config.toml"
    DEFAULT_CACHE_DIR = Path.home() / ".cache" / "ambient"
    DEFAULT_KEY_DIR = Path.home() / ".config" / "ambient" / "keys"
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to config file (uses default if not specified)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        self._ensure_directories()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from TOML file."""
        if not self.config_path.exists():
            print(f"Config file not found: {self.config_path}")
            print("Using default configuration. Run 'ambient config --init' to create a config file.")
            return self._default_config()
        
        try:
            with open(self.config_path, 'rb') as f:
                return tomllib.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            print("Using default configuration.")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "coordinator": {
                "primary": "http://localhost:9000",
                "fallbacks": [],
                "timeout": 10
            },
            "preferences": {
                "model": "llama3:8b",
                "fallback_models": ["mistral:7b", "llama2:7b"],
                "timeout": 300,
                "conversation_mode": True,
                "max_context_tokens": 4096
            },
            "security": {
                "private_key_path": str(self.DEFAULT_KEY_DIR / "private.pem"),
                "public_key_path": str(self.DEFAULT_KEY_DIR / "public.pem"),
                "verify_node_signatures": True,
                "trusted_coordinators": []
            },
            "output": {
                "format": "text",
                "colors": True,
                "verbose": False,
                "log_file": ""
            },
            "cache": {
                "directory": str(self.DEFAULT_CACHE_DIR),
                "enable_session_cache": True,
                "session_ttl": 3600
            }
        }
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        # Create config directory
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create key directory
        key_dir = Path(self.config["security"]["private_key_path"]).parent
        key_dir.mkdir(parents=True, exist_ok=True)
        
        # Create cache directory
        cache_dir = Path(self.config["cache"]["directory"])
        cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            section: Config section (e.g., "coordinator")
            key: Config key (e.g., "primary")
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(section, {}).get(key, default)
    
    def init_config_file(self):
        """Create a default configuration file."""
        if self.config_path.exists():
            response = input(f"Config file already exists at {self.config_path}. Overwrite? [y/N] ")
            if response.lower() != 'y':
                print("Aborted.")
                return
        
        # Copy example config
        example_path = Path(__file__).parent / "config.example.toml"
        if example_path.exists():
            import shutil
            shutil.copy(example_path, self.config_path)
            print(f"Created config file: {self.config_path}")
            print("Edit this file to customize your settings.")
        else:
            print(f"Error: Example config not found at {example_path}")


class AmbientCLI:
    """Main CLI application."""
    
    def __init__(self, config: AmbientConfig):
        """
        Initialize CLI.
        
        Args:
            config: Configuration object
        """
        self.config = config
    
    async def ask(self, prompt: str, model: Optional[str] = None):
        """
        Send a prompt to the network.
        
        Args:
            prompt: The question/prompt to send
            model: Override default model
        """
        model = model or self.config.get("preferences", "model")
        
        print(f"Asking model '{model}': {prompt}")
        print("\nNote: Full implementation requires conversation_client.py")
        print("This is a template showing the CLI structure.")
        
        # TODO: Integrate with conversation_client.py
        # from conversation_client import ConversationClient
        # client = ConversationClient(...)
        # response = await client.send_message(prompt, model=model)
        # print(response)
    
    def listen(self):
        """Watch for new responses."""
        print("Listening for responses...")
        print("(Press Ctrl+C to stop)")
        print("\nNote: Full implementation requires WebSocket support")
    
    def history(self, days: int = 1):
        """
        Show conversation history.
        
        Args:
            days: Number of days to show
        """
        cache_dir = Path(self.config.get("cache", "directory"))
        print(f"History from last {days} day(s):")
        print(f"(Cache directory: {cache_dir})")
        print("\nNote: Full implementation requires session cache")
    
    def show_config(self):
        """Display current configuration."""
        print(f"Configuration from: {self.config.config_path}\n")
        print(json.dumps(self.config.config, indent=2))
    
    def list_nodes(self):
        """List available nodes."""
        coordinator_url = self.config.get("coordinator", "primary")
        print(f"Querying coordinator: {coordinator_url}")
        print("\nNote: Full implementation requires coordinator client")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ambient Intelligence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ambient ask "What's the capital of France?"
  ambient ask "Explain quantum computing" --model llama3:70b
  ambient listen
  ambient history --today
  ambient config --show
  ambient config --init
  ambient nodes
        """
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config file (default: ~/.config/ambient/config.toml)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Send a prompt")
    ask_parser.add_argument("prompt", help="The prompt to send")
    ask_parser.add_argument("--model", help="Override default model")
    
    # Listen command
    listen_parser = subparsers.add_parser("listen", help="Watch for responses")
    
    # History command
    history_parser = subparsers.add_parser("history", help="Show conversation history")
    history_parser.add_argument("--today", action="store_true", help="Show today's history only")
    history_parser.add_argument("--days", type=int, default=1, help="Number of days to show")
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--show", action="store_true", help="Show current config")
    config_parser.add_argument("--init", action="store_true", help="Initialize config file")
    
    # Nodes command
    nodes_parser = subparsers.add_parser("nodes", help="List available nodes")
    
    args = parser.parse_args()
    
    # Load configuration
    config = AmbientConfig(args.config)
    cli = AmbientCLI(config)
    
    # Execute command
    if args.command == "ask":
        asyncio.run(cli.ask(args.prompt, args.model))
    
    elif args.command == "listen":
        cli.listen()
    
    elif args.command == "history":
        days = 1 if args.today else args.days
        cli.history(days)
    
    elif args.command == "config":
        if args.init:
            config.init_config_file()
        elif args.show:
            cli.show_config()
        else:
            print("Use --show to display config or --init to create config file")
    
    elif args.command == "nodes":
        cli.list_nodes()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
