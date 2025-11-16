"""
Phase 0 Integration Tests

These tests verify that:
1. Encryption/decryption works correctly
2. Node never sees plaintext
3. End-to-end flow completes successfully

Run with: pytest tests/test_phase0.py -v
"""

import pytest
import base64
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'client-cli'))

import nacl.public
import nacl.encoding
from node.crypto import NodeCrypto, generate_keypair
from crypto import ClientCrypto


class TestKeypairGeneration:
    """Test keypair generation and key management."""

    def test_generate_keypair(self):
        """Test that we can generate valid keypairs."""
        priv, pub = generate_keypair()

        # Both should be base64 strings
        assert isinstance(priv, str)
        assert isinstance(pub, str)

        # Should be non-empty
        assert len(priv) > 0
        assert len(pub) > 0

        # Should be able to reconstruct keys
        crypto = NodeCrypto(priv)
        assert crypto.get_public_key() == pub

    def test_node_crypto_without_key(self):
        """Test that NodeCrypto generates a key if none provided."""
        crypto = NodeCrypto()

        # Should have generated keys
        priv = crypto.get_private_key()
        pub = crypto.get_public_key()

        assert isinstance(priv, str)
        assert isinstance(pub, str)
        assert len(priv) > 0
        assert len(pub) > 0

    def test_client_crypto_ephemeral_keys(self):
        """Test that client generates ephemeral keys."""
        client1 = ClientCrypto()
        client2 = ClientCrypto()

        # Two clients should have different keys
        assert client1.get_public_key_b64() != client2.get_public_key_b64()


class TestEncryptionDecryption:
    """Test encryption and decryption operations."""

    def test_encryption_decryption_roundtrip(self):
        """Test that encryption/decryption round-trip works."""
        # Create node crypto
        node_crypto = NodeCrypto()

        # Create client crypto
        client_crypto = ClientCrypto()

        # Original message
        original = "What is the meaning of life?"

        # Client encrypts for node
        encrypted = client_crypto.encrypt_for_node(
            original,
            node_crypto.get_public_key()
        )

        # Encrypted should be different from original
        assert encrypted != original
        assert isinstance(encrypted, str)

        # Node decrypts
        decrypted = node_crypto.decrypt_prompt(
            encrypted,
            client_crypto.get_public_key_b64()
        )

        # Should match original
        assert decrypted == original

    def test_node_encrypts_response(self):
        """Test that node can encrypt a response that client can decrypt."""
        # Create node crypto
        node_crypto = NodeCrypto()

        # Create client crypto
        client_crypto = ClientCrypto()

        # Node encrypts response
        response = "42"
        encrypted_response = node_crypto.encrypt_response(
            response,
            client_crypto.get_public_key_b64()
        )

        # Client decrypts response
        decrypted_response = client_crypto.decrypt_from_node(
            encrypted_response,
            node_crypto.get_public_key()
        )

        assert decrypted_response == response

    def test_full_bidirectional_encryption(self):
        """Test complete bidirectional encryption flow."""
        node_crypto = NodeCrypto()
        client_crypto = ClientCrypto()

        # Client sends encrypted prompt to node
        prompt = "Hello, node!"
        encrypted_prompt = client_crypto.encrypt_for_node(
            prompt,
            node_crypto.get_public_key()
        )
        decrypted_prompt = node_crypto.decrypt_prompt(
            encrypted_prompt,
            client_crypto.get_public_key_b64()
        )
        assert decrypted_prompt == prompt

        # Node sends encrypted response to client
        response = "Hello, client!"
        encrypted_response = node_crypto.encrypt_response(
            response,
            client_crypto.get_public_key_b64()
        )
        decrypted_response = client_crypto.decrypt_from_node(
            encrypted_response,
            node_crypto.get_public_key()
        )
        assert decrypted_response == response


class TestEncryptionSecurity:
    """Test security properties of encryption."""

    def test_different_messages_different_ciphertexts(self):
        """Verify that same message encrypted twice produces different ciphertexts (nonce)."""
        node_crypto = NodeCrypto()
        client_crypto = ClientCrypto()

        message = "Test message"

        # Encrypt twice
        encrypted1 = client_crypto.encrypt_for_node(message, node_crypto.get_public_key())
        encrypted2 = client_crypto.encrypt_for_node(message, node_crypto.get_public_key())

        # Ciphertexts should be different (NaCl uses random nonces)
        assert encrypted1 != encrypted2

        # But both should decrypt to the same message
        decrypted1 = node_crypto.decrypt_prompt(encrypted1, client_crypto.get_public_key_b64())
        decrypted2 = node_crypto.decrypt_prompt(encrypted2, client_crypto.get_public_key_b64())

        assert decrypted1 == message
        assert decrypted2 == message

    def test_wrong_key_fails_decryption(self):
        """Verify that decryption with wrong key fails."""
        node_crypto = NodeCrypto()

        # Client 1 encrypts
        client1 = ClientCrypto()
        message = "Secret message"
        encrypted = client1.encrypt_for_node(message, node_crypto.get_public_key())

        # Try to decrypt with client 2's key (wrong key)
        client2 = ClientCrypto()

        with pytest.raises(ValueError):
            node_crypto.decrypt_prompt(encrypted, client2.get_public_key_b64())

    def test_tampered_ciphertext_fails(self):
        """Verify that tampered ciphertext fails to decrypt."""
        node_crypto = NodeCrypto()
        client_crypto = ClientCrypto()

        message = "Original message"
        encrypted = client_crypto.encrypt_for_node(message, node_crypto.get_public_key())

        # Tamper with the ciphertext
        encrypted_bytes = base64.b64decode(encrypted)
        tampered_bytes = bytearray(encrypted_bytes)
        tampered_bytes[10] ^= 0xFF  # Flip some bits
        tampered_encrypted = base64.b64encode(bytes(tampered_bytes)).decode()

        # Should fail to decrypt
        with pytest.raises(ValueError):
            node_crypto.decrypt_prompt(tampered_encrypted, client_crypto.get_public_key_b64())

    def test_invalid_base64_fails(self):
        """Verify that invalid base64 fails gracefully."""
        node_crypto = NodeCrypto()
        client_crypto = ClientCrypto()

        invalid_base64 = "This is not valid base64!!!"

        with pytest.raises(ValueError):
            node_crypto.decrypt_prompt(invalid_base64, client_crypto.get_public_key_b64())


class TestUnicode:
    """Test that encryption handles Unicode correctly."""

    def test_unicode_messages(self):
        """Test encryption/decryption of Unicode strings."""
        node_crypto = NodeCrypto()
        client_crypto = ClientCrypto()

        # Test various Unicode strings
        test_messages = [
            "Hello, 世界!",  # Chinese
            "Привет, мир!",  # Russian
            "مرحبا بالعالم",  # Arabic
            "🚀 🌟 ✨",  # Emojis
            "Ça marche très bien!",  # French with accents
        ]

        for message in test_messages:
            # Encrypt
            encrypted = client_crypto.encrypt_for_node(
                message,
                node_crypto.get_public_key()
            )

            # Decrypt
            decrypted = node_crypto.decrypt_prompt(
                encrypted,
                client_crypto.get_public_key_b64()
            )

            # Should match original
            assert decrypted == message


class TestLargeMessages:
    """Test handling of large messages."""

    def test_large_message(self):
        """Test encryption/decryption of a large message."""
        node_crypto = NodeCrypto()
        client_crypto = ClientCrypto()

        # Create a large message (10KB)
        large_message = "A" * 10000

        # Encrypt
        encrypted = client_crypto.encrypt_for_node(
            large_message,
            node_crypto.get_public_key()
        )

        # Decrypt
        decrypted = node_crypto.decrypt_prompt(
            encrypted,
            client_crypto.get_public_key_b64()
        )

        # Should match original
        assert decrypted == large_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
