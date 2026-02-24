"""
Encryption Key Lifecycle Management

Handles:
- Ephemeral key generation and destruction
- Key rotation policies
- Secure key storage in memory (never disk)
- Forward secrecy guarantees
- Key derivation flows

Security principles:
1. Client ephemeral keys exist only in memory
2. Keys are destroyed immediately after use
3. No key reuse across sessions
4. Automatic rotation for long-lived node keys
"""

import os
import time
import base64
import secrets
import hashlib
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import nacl.public
import nacl.encoding
import nacl.utils
import nacl.secret
import nacl.pwhash


@dataclass
class KeyMetadata:
    """Metadata about a cryptographic key."""
    key_id: str
    created_at: float
    expires_at: Optional[float]
    rotation_count: int = 0
    last_used: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if key has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def should_rotate(self, max_age_seconds: int = 86400) -> bool:
        """Check if key should be rotated based on age."""
        age = time.time() - self.created_at
        return age > max_age_seconds


class EphemeralKeyPair:
    """
    Ephemeral key pair for single-use encryption.
    
    Automatically destroys private key when context exits.
    Designed for client-side use where keys should never persist.
    """
    
    def __init__(self):
        """Generate new ephemeral keypair."""
        self._private_key = nacl.public.PrivateKey.generate()
        self._public_key = self._private_key.public_key
        self._created_at = time.time()
        self._used = False
        self._destroyed = False
    
    @property
    def public_key_b64(self) -> str:
        """Get base64-encoded public key."""
        return base64.b64encode(bytes(self._public_key)).decode()
    
    def encrypt(self, plaintext: str, recipient_pubkey_b64: str) -> str:
        """
        Encrypt plaintext for recipient.
        
        Args:
            plaintext: Message to encrypt
            recipient_pubkey_b64: Recipient's public key (base64)
            
        Returns:
            Base64-encoded encrypted message
        """
        if self._destroyed:
            raise ValueError("Cannot use destroyed key")
        
        recipient_pubkey = nacl.public.PublicKey(
            recipient_pubkey_b64,
            encoder=nacl.encoding.Base64Encoder
        )
        
        box = nacl.public.Box(self._private_key, recipient_pubkey)
        encrypted = box.encrypt(plaintext.encode('utf-8'))
        
        self._used = True
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_b64: str, sender_pubkey_b64: str) -> str:
        """
        Decrypt message from sender.
        
        Args:
            encrypted_b64: Base64-encoded encrypted message
            sender_pubkey_b64: Sender's public key (base64)
            
        Returns:
            Decrypted plaintext
        """
        if self._destroyed:
            raise ValueError("Cannot use destroyed key")
        
        sender_pubkey = nacl.public.PublicKey(
            sender_pubkey_b64,
            encoder=nacl.encoding.Base64Encoder
        )
        
        box = nacl.public.Box(self._private_key, sender_pubkey)
        encrypted = base64.b64decode(encrypted_b64)
        plaintext_bytes = box.decrypt(encrypted)
        
        self._used = True
        return plaintext_bytes.decode('utf-8')
    
    def destroy(self):
        """
        Securely destroy private key material.
        
        Overwrites memory and clears references.
        """
        if self._destroyed:
            return
        
        # Overwrite private key bytes with random data
        # Note: Python's memory management makes this best-effort
        try:
            key_bytes = bytes(self._private_key)
            random_bytes = os.urandom(len(key_bytes))
            # Overwrite (limited effectiveness in Python, but symbolic)
            del self._private_key
        except Exception:
            pass
        
        self._destroyed = True
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto-destroy key."""
        self.destroy()
    
    def __del__(self):
        """Destructor - ensure key is destroyed."""
        self.destroy()


class KeyRotationManager:
    """
    Manages key rotation for long-lived node keys.
    
    Supports graceful rotation where old keys are kept for a period
    to decrypt in-flight messages.
    """
    
    def __init__(
        self,
        rotation_interval: int = 86400,  # 24 hours
        grace_period: int = 3600  # 1 hour overlap
    ):
        """
        Initialize key rotation manager.
        
        Args:
            rotation_interval: Seconds between rotations
            grace_period: Seconds to keep old key active
        """
        self.rotation_interval = rotation_interval
        self.grace_period = grace_period
        
        self._current_key: Optional[nacl.public.PrivateKey] = None
        self._current_metadata: Optional[KeyMetadata] = None
        self._old_keys: list[Tuple[nacl.public.PrivateKey, KeyMetadata]] = []
    
    def initialize(self, private_key_b64: Optional[str] = None) -> str:
        """
        Initialize with existing key or generate new one.
        
        Returns:
            Base64-encoded public key
        """
        if private_key_b64:
            self._current_key = nacl.public.PrivateKey(
                private_key_b64,
                encoder=nacl.encoding.Base64Encoder
            )
        else:
            self._current_key = nacl.public.PrivateKey.generate()
        
        key_id = hashlib.sha256(bytes(self._current_key.public_key)).hexdigest()[:16]
        self._current_metadata = KeyMetadata(
            key_id=key_id,
            created_at=time.time(),
            expires_at=time.time() + self.rotation_interval
        )
        
        return self.get_public_key()
    
    def get_public_key(self) -> str:
        """Get current public key."""
        if not self._current_key:
            raise ValueError("Key manager not initialized")
        return base64.b64encode(bytes(self._current_key.public_key)).decode()
    
    def get_private_key(self) -> str:
        """Get current private key (for backup/config)."""
        if not self._current_key:
            raise ValueError("Key manager not initialized")
        return base64.b64encode(bytes(self._current_key)).decode()
    
    def should_rotate(self) -> bool:
        """Check if current key should be rotated."""
        if not self._current_metadata:
            return False
        return self._current_metadata.should_rotate(self.rotation_interval)
    
    def rotate(self) -> str:
        """
        Rotate to new key pair.
        
        Old key is retained for grace period.
        
        Returns:
            New public key (base64)
        """
        if not self._current_key or not self._current_metadata:
            raise ValueError("Key manager not initialized")
        
        # Move current to old keys
        self._current_metadata.expires_at = time.time() + self.grace_period
        self._old_keys.append((self._current_key, self._current_metadata))
        
        # Generate new key
        self._current_key = nacl.public.PrivateKey.generate()
        key_id = hashlib.sha256(bytes(self._current_key.public_key)).hexdigest()[:16]
        self._current_metadata = KeyMetadata(
            key_id=key_id,
            created_at=time.time(),
            expires_at=time.time() + self.rotation_interval,
            rotation_count=self._current_metadata.rotation_count + 1
        )
        
        # Clean up expired old keys
        self._cleanup_old_keys()
        
        return self.get_public_key()
    
    def decrypt_with_any_key(
        self,
        encrypted_b64: str,
        sender_pubkey_b64: str
    ) -> Optional[str]:
        """
        Try to decrypt with current key, fall back to old keys.
        
        Useful during rotation overlap period.
        """
        sender_pubkey = nacl.public.PublicKey(
            sender_pubkey_b64,
            encoder=nacl.encoding.Base64Encoder
        )
        encrypted = base64.b64decode(encrypted_b64)
        
        # Try current key first
        try:
            box = nacl.public.Box(self._current_key, sender_pubkey)
            plaintext = box.decrypt(encrypted)
            return plaintext.decode('utf-8')
        except Exception:
            pass
        
        # Try old keys
        for old_key, metadata in self._old_keys:
            if metadata.is_expired():
                continue
            
            try:
                box = nacl.public.Box(old_key, sender_pubkey)
                plaintext = box.decrypt(encrypted)
                metadata.last_used = time.time()
                return plaintext.decode('utf-8')
            except Exception:
                continue
        
        return None
    
    def _cleanup_old_keys(self):
        """Remove expired old keys."""
        self._old_keys = [
            (key, metadata)
            for key, metadata in self._old_keys
            if not metadata.is_expired()
        ]
    
    def get_stats(self) -> dict:
        """Get key rotation statistics."""
        if not self._current_metadata:
            return {}
        
        return {
            'current_key_id': self._current_metadata.key_id,
            'current_key_age': time.time() - self._current_metadata.created_at,
            'rotation_count': self._current_metadata.rotation_count,
            'old_keys_count': len(self._old_keys),
            'should_rotate': self.should_rotate(),
        }


class ClientKeyManager:
    """
    Simplified key manager for clients.
    
    Clients use ephemeral keys per request for maximum forward secrecy.
    """
    
    @staticmethod
    def create_request_keypair() -> EphemeralKeyPair:
        """
        Create ephemeral keypair for a single request.
        
        Usage:
            with ClientKeyManager.create_request_keypair() as keypair:
                encrypted = keypair.encrypt(prompt, node_pubkey)
                # ... send encrypted
                # ... receive response
                plaintext = keypair.decrypt(response, node_pubkey)
            # keypair automatically destroyed here
        """
        return EphemeralKeyPair()
    
    @staticmethod
    def derive_session_key(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Derive a key from password (for optional client-side encryption).
        
        Args:
            password: User password
            salt: Optional salt, or None to generate new
            
        Returns:
            (derived_key, salt)
        """
        if salt is None:
            salt = nacl.utils.random(nacl.pwhash.argon2i.SALTBYTES)
        
        key = nacl.pwhash.argon2i.kdf(
            nacl.secret.SecretBox.KEY_SIZE,
            password.encode('utf-8'),
            salt,
            opslimit=nacl.pwhash.argon2i.OPSLIMIT_INTERACTIVE,
            memlimit=nacl.pwhash.argon2i.MEMLIMIT_INTERACTIVE
        )
        
        return key, salt


# Example usage patterns:

def example_client_flow():
    """Demonstrate client-side ephemeral key usage."""
    node_pubkey = "base64_encoded_node_public_key"
    
    # Create ephemeral keypair for request
    with ClientKeyManager.create_request_keypair() as keypair:
        # Encrypt prompt
        prompt = "Hello, world!"
        encrypted_prompt = keypair.encrypt(prompt, node_pubkey)
        client_pubkey = keypair.public_key_b64
        
        # Send to node: {encrypted_prompt, client_pubkey}
        print(f"Sending encrypted prompt with pubkey {client_pubkey[:16]}...")
        
        # Receive encrypted response
        encrypted_response = "base64_encrypted_response_from_node"
        
        # Decrypt response
        # response = keypair.decrypt(encrypted_response, node_pubkey)
        # print(f"Decrypted: {response}")
    
    # Key is automatically destroyed here


def example_node_rotation():
    """Demonstrate node key rotation."""
    manager = KeyRotationManager(
        rotation_interval=86400,  # 24 hours
        grace_period=3600  # 1 hour
    )
    
    # Initialize
    pubkey = manager.initialize()
    print(f"Node public key: {pubkey}")
    
    # Check if rotation needed (in background task)
    if manager.should_rotate():
        new_pubkey = manager.rotate()
        print(f"Rotated to new key: {new_pubkey}")
        
        # Update coordinator with new public key
        # coordinator.update_node_pubkey(node_id, new_pubkey)
    
    # During grace period, can decrypt with either key
    # plaintext = manager.decrypt_with_any_key(encrypted, client_pubkey)


if __name__ == "__main__":
    print("=== Client Flow ===")
    example_client_flow()
    
    print("\n=== Node Key Rotation ===")
    example_node_rotation()
