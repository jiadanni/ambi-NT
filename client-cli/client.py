"""
Ambient Intelligence CLI Client

A simple command-line interface for submitting prompts to the network.
This demonstrates the encryption flow and serves as a reference implementation.

Privacy Features:
- Ephemeral keys for each session
- Prompts encrypted before leaving your machine
- No local history or storage
- Forward secrecy
"""

import os
import sys
import time
import argparse
import requests
from typing import Optional

from client_cli.crypto import ClientCrypto


class AmbientClient:
    """Client for interacting with Ambient Intelligence nodes."""

    def __init__(self, node_url: str):
        """
        Initialize client with a target node.

        Args:
            node_url: URL of the node to connect to
        """
        self.node_url = node_url.rstrip('/')

        # Each client session generates ephemeral keys
        # These keys are NOT persisted - they're regenerated on each run
        # This ensures forward secrecy
        self.crypto = ClientCrypto()

        # Fetch the node's public key
        self.node_pubkey = self._get_node_pubkey()

    def _get_node_pubkey(self) -> str:
        """
        Fetch the node's public key.

        Returns:
            Base64-encoded node public key

        Raises:
            SystemExit: If node is unreachable
        """
        try:
            response = requests.get(f"{self.node_url}/pubkey", timeout=5)
            response.raise_for_status()
            return response.json()["public_key"]
        except requests.exceptions.RequestException as e:
            print(f"Error: Could not reach node at {self.node_url}")
            print(f"Details: {e}")
            print("\nTroubleshooting:")
            print("1. Ensure the node is running (python node/server.py)")
            print("2. Check the node URL is correct")
            print("3. Verify firewall settings")
            sys.exit(1)

    def submit_and_wait(
        self,
        prompt: str,
        poll_interval: float = 2.0,
        max_wait: int = 300
    ) -> Optional[str]:
        """
        Submit a prompt and poll until completion.

        Args:
            prompt: The question/prompt to submit
            poll_interval: Seconds between status checks
            max_wait: Maximum seconds to wait for response

        Returns:
            The decrypted response, or None on failure
        """
        # Encrypt the prompt
        try:
            encrypted_prompt = self.crypto.encrypt_for_node(prompt, self.node_pubkey)
        except Exception as e:
            print(f"Error encrypting prompt: {e}")
            return None

        client_pubkey_b64 = self.crypto.get_public_key_b64()

        # Submit the job
        try:
            print(f"[Encrypting and submitting to {self.node_url}...]")
            response = requests.post(
                f"{self.node_url}/submit",
                json={
                    "encrypted_prompt": encrypted_prompt,
                    "client_pubkey": client_pubkey_b64
                },
                timeout=10
            )
            response.raise_for_status()
            job_id = response.json()["job_id"]
            print(f"[Job ID: {job_id}]")

        except requests.exceptions.RequestException as e:
            print(f"Error submitting job: {e}")
            if hasattr(e.response, 'text'):
                print(f"Server response: {e.response.text}")
            return None

        # Poll for completion
        start_time = time.time()
        print("[Waiting for response", end="", flush=True)

        while True:
            # Check timeout
            if time.time() - start_time > max_wait:
                print(f" ✗]\nError: Timeout after {max_wait}s")
                return None

            try:
                response = requests.get(
                    f"{self.node_url}/status/{job_id}",
                    params={"client_pubkey": client_pubkey_b64},
                    timeout=5
                )
                response.raise_for_status()
                data = response.json()

                status = data["status"]

                if status == "complete":
                    elapsed = time.time() - start_time
                    print(f" ✓] ({elapsed:.1f}s)")

                    # Decrypt and return the response
                    encrypted_response = data["encrypted_response"]
                    try:
                        decrypted = self.crypto.decrypt_from_node(
                            encrypted_response,
                            self.node_pubkey
                        )
                        return decrypted
                    except Exception as e:
                        print(f"\nError decrypting response: {e}")
                        return None

                elif status == "failed":
                    print(" ✗]")
                    error_msg = data.get("error_message", "Unknown error")
                    print(f"Error: Job failed on node - {error_msg}")
                    return None

                else:
                    # Still pending/running
                    print(".", end="", flush=True)
                    time.sleep(poll_interval)

            except requests.exceptions.RequestException as e:
                print(f"\nError polling status: {e}")
                return None


def main():
    """Main entry point for the CLI client."""
    parser = argparse.ArgumentParser(
        description="Ambient Intelligence CLI Client - Privacy-first AI inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "What is 2+2?"
  %(prog)s --node http://192.168.1.100:8000 "Explain quantum computing"
  %(prog)s --help

Privacy Notes:
  - Your prompts are encrypted before leaving your machine
  - The node processes them without seeing the plaintext
  - No history is saved locally
  - Each session uses fresh ephemeral keys
        """
    )
    parser.add_argument(
        "prompt",
        nargs="+",
        help="The prompt to submit"
    )
    parser.add_argument(
        "--node",
        default=os.getenv("DEFAULT_NODE_URL", "http://localhost:8000"),
        help="Node URL (default: http://localhost:8000 or $DEFAULT_NODE_URL)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum wait time in seconds (default: 300)"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between status checks (default: 2.0)"
    )

    args = parser.parse_args()
    prompt = " ".join(args.prompt)

    # Create client and submit
    print(f"\nAmbient Intelligence - Privacy-First AI")
    print(f"{'=' * 60}")
    print(f"Node: {args.node}")
    print(f"Prompt: {prompt}")
    print(f"{'=' * 60}\n")

    try:
        client = AmbientClient(args.node)
    except Exception as e:
        print(f"Failed to initialize client: {e}")
        sys.exit(1)

    response = client.submit_and_wait(
        prompt,
        poll_interval=args.poll_interval,
        max_wait=args.timeout
    )

    if response:
        print(f"\n{'=' * 60}")
        print("Response:")
        print(f"{'=' * 60}")
        print(response)
        print(f"{'=' * 60}\n")
        sys.exit(0)
    else:
        print("\nFailed to get response.")
        sys.exit(1)


if __name__ == "__main__":
    main()
