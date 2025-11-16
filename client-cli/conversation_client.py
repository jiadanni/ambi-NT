"""
Ambient Intelligence Conversation CLI Client

Interactive REPL mode with conversation support.
Maintains conversation history client-side for multi-turn interactions.

Privacy Features:
- Conversation history stored locally (with optional encryption)
- Full context sent with each request (nodes stay stateless)
- Smart context windowing (4096 token limit)
- Encrypted transmission of all data
"""

import os
import sys
import time
import json
import argparse
import requests
from typing import List, Dict, Optional
from pathlib import Path
import getpass

from crypto import ClientCrypto


class ConversationStorage:
    """Manages conversation storage with optional encryption."""

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize conversation storage.

        Args:
            storage_dir: Directory for storing conversations
                        (defaults to ~/.ambient-conversations)
        """
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / ".ambient-conversations"

        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_conversation(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        password: Optional[str] = None
    ):
        """
        Save conversation to disk.

        Args:
            conversation_id: Unique conversation identifier
            messages: List of message dicts
            password: Optional password for encryption (NOT IMPLEMENTED YET)

        Warning:
            Currently stores conversations UNENCRYPTED.
            Anyone with filesystem access can read them.
            Use disk encryption or --password flag (future) for security.
        """
        filepath = self.storage_dir / f"{conversation_id}.json"

        data = {
            "conversation_id": conversation_id,
            "created_at": time.time(),
            "messages": messages
        }

        if password:
            # TODO: Implement encryption with password
            print("\nWARNING: Password encryption not yet implemented!")
            print("Conversation will be saved UNENCRYPTED.")
            print("Recommended: Use full-disk encryption on your system.\n")

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_conversation(
        self,
        conversation_id: str,
        password: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Load conversation from disk.

        Args:
            conversation_id: Conversation identifier
            password: Optional password for decryption

        Returns:
            List of message dicts

        Raises:
            FileNotFoundError: If conversation doesn't exist
        """
        filepath = self.storage_dir / f"{conversation_id}.json"

        if not filepath.exists():
            raise FileNotFoundError(f"Conversation not found: {conversation_id}")

        with open(filepath, 'r') as f:
            data = json.load(f)

        return data["messages"]

    def list_conversations(self) -> List[str]:
        """List all stored conversations."""
        return [f.stem for f in self.storage_dir.glob("*.json")]


class ConversationClient:
    """Client with conversation support."""

    def __init__(self, node_url: str, max_context_tokens: int = 4096):
        """
        Initialize conversation client.

        Args:
            node_url: URL of the node to connect to
            max_context_tokens: Maximum tokens for context window
        """
        self.node_url = node_url.rstrip('/')
        self.max_context_tokens = max_context_tokens

        # Each client session generates ephemeral keys
        self.crypto = ClientCrypto()

        # Fetch the node's public key
        self.node_pubkey = self._get_node_pubkey()

        # Conversation state
        self.messages: List[Dict[str, str]] = []

    def _get_node_pubkey(self) -> str:
        """Fetch the node's public key."""
        try:
            response = requests.get(f"{self.node_url}/pubkey", timeout=5)
            response.raise_for_status()
            return response.json()["public_key"]
        except requests.exceptions.RequestException as e:
            print(f"Error: Could not reach node at {self.node_url}")
            print(f"Details: {e}")
            sys.exit(1)

    def add_user_message(self, content: str):
        """Add a user message to the conversation."""
        self.messages.append({
            "role": "user",
            "content": content
        })

    def add_assistant_message(self, content: str):
        """Add an assistant message to the conversation."""
        self.messages.append({
            "role": "assistant",
            "content": content
        })

    def submit_conversation(
        self,
        poll_interval: float = 2.0,
        max_wait: int = 300
    ) -> Optional[str]:
        """
        Submit the current conversation and get a response.

        Args:
            poll_interval: Seconds between status checks
            max_wait: Maximum seconds to wait for response

        Returns:
            The decrypted response, or None on failure
        """
        if not self.messages:
            print("Error: No messages to send")
            return None

        # Convert messages to JSON string
        conversation_json = json.dumps(self.messages)

        # Encrypt the entire conversation
        try:
            encrypted_data = self.crypto.encrypt_for_node(conversation_json, self.node_pubkey)
        except Exception as e:
            print(f"Error encrypting conversation: {e}")
            return None

        client_pubkey_b64 = self.crypto.get_public_key_b64()

        # Submit the job with conversation_mode=true
        try:
            response = requests.post(
                f"{self.node_url}/submit",
                json={
                    "encrypted_prompt": encrypted_data,
                    "client_pubkey": client_pubkey_b64,
                    "conversation_mode": True,
                    "max_context_tokens": self.max_context_tokens
                },
                timeout=10
            )
            response.raise_for_status()
            job_id = response.json()["job_id"]

        except requests.exceptions.RequestException as e:
            print(f"Error submitting job: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"Server response: {e.response.text}")
            return None

        # Poll for completion
        start_time = time.time()

        while True:
            if time.time() - start_time > max_wait:
                print(f"Error: Timeout after {max_wait}s")
                return None

            try:
                response = requests.get(
                    f"{self.node_url}/status/{job_id}",
                    timeout=5
                )
                response.raise_for_status()
                data = response.json()

                status = data["status"]

                if status == "complete":
                    # Decrypt and return the response
                    encrypted_response = data["encrypted_response"]
                    try:
                        decrypted = self.crypto.decrypt_from_node(
                            encrypted_response,
                            self.node_pubkey
                        )
                        return decrypted
                    except Exception as e:
                        print(f"Error decrypting response: {e}")
                        return None

                elif status == "failed":
                    error_msg = data.get("error_message", "Unknown error")
                    print(f"Error: Job failed - {error_msg}")
                    return None

                else:
                    # Still pending/running
                    time.sleep(poll_interval)

            except requests.exceptions.RequestException as e:
                print(f"Error polling status: {e}")
                return None

    def clear_history(self):
        """Clear the conversation history."""
        self.messages = []


def interactive_mode(node_url: str, storage_dir: Optional[str] = None):
    """Run interactive REPL mode."""
    client = ConversationClient(node_url)
    storage = ConversationStorage(storage_dir)

    print(f"\nAmbient Intelligence - Conversation Mode")
    print(f"{'=' * 60}")
    print(f"Node: {node_url}")
    print(f"Context window: {client.max_context_tokens} tokens")
    print(f"{'=' * 60}")
    print("\nCommands:")
    print("  /clear    - Clear conversation history")
    print("  /save     - Save conversation to disk")
    print("  /load     - Load a previous conversation")
    print("  /list     - List saved conversations")
    print("  /exit     - Exit conversation mode")
    print(f"{'=' * 60}\n")

    print("⚠️  WARNING: Conversations are stored UNENCRYPTED locally!")
    print("   Anyone with access to your computer can read them.")
    print("   Recommended: Use full-disk encryption.\n")

    conversation_id = str(int(time.time()))

    while True:
        try:
            user_input = input("\n> ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                command = user_input[1:].lower()

                if command == "exit" or command == "quit":
                    print("Goodbye!")
                    break

                elif command == "clear":
                    client.clear_history()
                    print("Conversation history cleared.")
                    conversation_id = str(int(time.time()))
                    continue

                elif command == "save":
                    if not client.messages:
                        print("No conversation to save.")
                        continue

                    storage.save_conversation(conversation_id, client.messages)
                    print(f"Conversation saved: {conversation_id}")
                    print(f"Location: {storage.storage_dir / f'{conversation_id}.json'}")
                    continue

                elif command == "load":
                    convos = storage.list_conversations()
                    if not convos:
                        print("No saved conversations found.")
                        continue

                    print("\nSaved conversations:")
                    for i, cid in enumerate(convos[-10:], 1):  # Show last 10
                        print(f"  {i}. {cid}")

                    try:
                        choice = input("\nEnter conversation ID to load: ").strip()
                        messages = storage.load_conversation(choice)
                        client.messages = messages
                        conversation_id = choice
                        print(f"Loaded {len(messages)} messages from {choice}")

                        # Display last few exchanges
                        print("\nRecent messages:")
                        for msg in messages[-6:]:
                            role_icon = "👤" if msg["role"] == "user" else "🤖"
                            preview = msg["content"][:80]
                            if len(msg["content"]) > 80:
                                preview += "..."
                            print(f"{role_icon} {msg['role']}: {preview}")

                    except Exception as e:
                        print(f"Error loading conversation: {e}")
                    continue

                elif command == "list":
                    convos = storage.list_conversations()
                    if not convos:
                        print("No saved conversations found.")
                    else:
                        print(f"\nSaved conversations ({len(convos)} total):")
                        for cid in convos[-20:]:  # Show last 20
                            print(f"  - {cid}")
                    continue

                else:
                    print(f"Unknown command: /{command}")
                    continue

            # Regular message
            client.add_user_message(user_input)

            print("[Encrypting and sending", end="", flush=True)
            for _ in range(3):
                time.sleep(0.3)
                print(".", end="", flush=True)
            print("]")

            response = client.submit_conversation()

            if response:
                client.add_assistant_message(response)

                print(f"\n{'─' * 60}")
                print(response)
                print(f"{'─' * 60}")
            else:
                # Remove the user message since we didn't get a response
                client.messages.pop()
                print("\nFailed to get response. Try again.")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Use /exit to quit cleanly.")
            continue
        except EOFError:
            print("\nGoodbye!")
            break


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ambient Intelligence Conversation Client",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--node",
        default=os.getenv("DEFAULT_NODE_URL", "http://localhost:8000"),
        help="Node URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--storage-dir",
        help="Directory for storing conversations (default: ~/.ambient-conversations)"
    )

    args = parser.parse_args()

    try:
        interactive_mode(args.node, args.storage_dir)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
