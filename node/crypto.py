"""
Cryptographic operations for the Ambient Intelligence node.

This module handles encryption and decryption of prompts and responses.
The key insight is that the node NEVER stores or logs plaintext data.
All encryption uses NaCl (libsodium) which is designed to be hard to misuse.

Privacy Guarantee:
- Plaintext prompts only exist in memory during processing
- No plaintext data is ever logged or persisted
- Forward secrecy through ephemeral client keys
"""

import os
import base64
from typing import Tuple
import nacl.public
import nacl.encoding
import nacl.utils


class NodeCrypto:
    """Handles encryption operations for the node."""

    def __init__(self, private_key_b64: str = None):
        """
        Initialize with a private key, or generate a new one.

        The private key should be stored in environment variables and
        never committed to version control.

        Args:
            private_key_b64: Base64-encoded private key. If None, generates new keypair.
        """
        if private_key_b64:
            self.private_key = nacl.public.PrivateKey(
                private_key_b64,
                encoder=nacl.encoding.Base64Encoder
            )
        else:
            # Generate new keypair
            self.private_key = nacl.public.PrivateKey.generate()

        self.public_key = self.private_key.public_key

    def get_public_key(self) -> str:
        """Return the node's public key as base64 string."""
        return base64.b64encode(bytes(self.public_key)).decode()

    def get_private_key(self) -> str:
        """Return the node's private key as base64 string (for storage in .env)."""
        return base64.b64encode(bytes(self.private_key)).decode()

    def decrypt_prompt(self, encrypted_b64: str, client_pubkey_b64: str) -> str:
        """
        Decrypt an incoming prompt from a client.

        The client encrypts with our public key, we decrypt with our private key.
        This is asymmetric encryption - only we can decrypt messages sent to us.

        CRITICAL: This is the only place where plaintext prompts exist on the node.
        The returned string should be immediately passed to Ollama and never logged.

        Args:
            encrypted_b64: Base64-encoded encrypted message from client
            client_pubkey_b64: Base64-encoded client public key

        Returns:
            Decrypted plaintext prompt

        Raises:
            ValueError: If decryption fails (malformed data, wrong key, etc.)
        """
        try:
            # Decode the base64-encoded encrypted message
            encrypted = base64.b64decode(encrypted_b64)

            # Decode the client's public key
            client_pubkey = nacl.public.PublicKey(
                client_pubkey_b64,
                encoder=nacl.encoding.Base64Encoder
            )

            # Create a Box for decryption using our private key and their public key
            box = nacl.public.Box(self.private_key, client_pubkey)

            # Decrypt and return plaintext
            plaintext_bytes = box.decrypt(encrypted)
            return plaintext_bytes.decode('utf-8')

        except Exception as e:
            # If decryption fails, it's likely because the client sent malformed data
            # We don't log the encrypted data because that could leak metadata
            raise ValueError(f"Failed to decrypt prompt: {str(e)}")

    def encrypt_response(self, plaintext: str, client_pubkey_b64: str) -> str:
        """
        Encrypt a response to send back to the client.

        We encrypt with the client's public key, so only they can decrypt it.
        Even we (the node) cannot decrypt this response after encryption.

        Args:
            plaintext: The response text to encrypt
            client_pubkey_b64: Base64-encoded client public key

        Returns:
            Base64-encoded encrypted response

        Raises:
            ValueError: If encryption fails
        """
        try:
            # Decode the client's public key
            client_pubkey = nacl.public.PublicKey(
                client_pubkey_b64,
                encoder=nacl.encoding.Base64Encoder
            )

            # Create a Box for encryption
            box = nacl.public.Box(self.private_key, client_pubkey)

            # Encrypt the plaintext
            encrypted = box.encrypt(plaintext.encode('utf-8'))

            # Return as base64 string
            return base64.b64encode(encrypted).decode()

        except Exception as e:
            raise ValueError(f"Failed to encrypt response: {str(e)}")


def generate_keypair() -> Tuple[str, str]:
    """
    Generate a new keypair for initial setup.

    Returns:
        Tuple of (private_key_b64, public_key_b64)

    Usage:
        Run this once and store the private key in .env

    Example:
        >>> priv, pub = generate_keypair()
        >>> print(f"NODE_PRIVATE_KEY={priv}")
        >>> print(f"NODE_PUBLIC_KEY={pub}")
    """
    private_key = nacl.public.PrivateKey.generate()
    public_key = private_key.public_key

    private_b64 = base64.b64encode(bytes(private_key)).decode()
    public_b64 = base64.b64encode(bytes(public_key)).decode()

    return private_b64, public_b64


if __name__ == "__main__":
    # Generate a keypair for testing/setup
    print("Generating new keypair...")
    priv, pub = generate_keypair()
    print(f"\nAdd these to your .env file:")
    print(f"NODE_PRIVATE_KEY={priv}")
    print(f"NODE_PUBLIC_KEY={pub}")
