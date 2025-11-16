"""
Client-side cryptography for Ambient Intelligence.

This module handles:
- Generating ephemeral keypairs for each session
- Encrypting prompts for nodes
- Decrypting responses from nodes

Privacy Features:
- Ephemeral keys provide forward secrecy
- Keys are never persisted to disk
- Each session gets new keys
"""

import base64
from typing import Tuple
import nacl.public
import nacl.encoding


class ClientCrypto:
    """Handles encryption operations for the client."""

    def __init__(self):
        """
        Initialize with a fresh ephemeral keypair.

        The keypair exists only in memory and is never saved.
        This provides forward secrecy - even if a key is compromised,
        past sessions remain secure.
        """
        # Generate ephemeral keypair
        self.private_key = nacl.public.PrivateKey.generate()
        self.public_key = self.private_key.public_key

    def get_public_key_b64(self) -> str:
        """
        Get the client's public key as base64 string.

        This is sent to the node with each request.
        """
        return base64.b64encode(bytes(self.public_key)).decode()

    def encrypt_for_node(self, plaintext: str, node_pubkey_b64: str) -> str:
        """
        Encrypt a message for a specific node.

        Args:
            plaintext: The message to encrypt
            node_pubkey_b64: The node's public key (base64-encoded)

        Returns:
            Base64-encoded encrypted message

        Raises:
            ValueError: If encryption fails
        """
        try:
            # Decode the node's public key
            node_pubkey = nacl.public.PublicKey(
                node_pubkey_b64,
                encoder=nacl.encoding.Base64Encoder
            )

            # Create a Box for encryption
            box = nacl.public.Box(self.private_key, node_pubkey)

            # Encrypt the plaintext
            encrypted = box.encrypt(plaintext.encode('utf-8'))

            # Return as base64 string
            return base64.b64encode(encrypted).decode()

        except Exception as e:
            raise ValueError(f"Failed to encrypt message: {str(e)}")

    def decrypt_from_node(self, encrypted_b64: str, node_pubkey_b64: str) -> str:
        """
        Decrypt a message from a node.

        Args:
            encrypted_b64: Base64-encoded encrypted message
            node_pubkey_b64: The node's public key (base64-encoded)

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If decryption fails
        """
        try:
            # Decode the encrypted message
            encrypted = base64.b64decode(encrypted_b64)

            # Decode the node's public key
            node_pubkey = nacl.public.PublicKey(
                node_pubkey_b64,
                encoder=nacl.encoding.Base64Encoder
            )

            # Create a Box for decryption
            box = nacl.public.Box(self.private_key, node_pubkey)

            # Decrypt and return plaintext
            plaintext_bytes = box.decrypt(encrypted)
            return plaintext_bytes.decode('utf-8')

        except Exception as e:
            raise ValueError(f"Failed to decrypt message: {str(e)}")
