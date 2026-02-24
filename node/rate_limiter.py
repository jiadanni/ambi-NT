"""
Rate limiting for node endpoints with multi-level protection
"""

import time
from collections import defaultdict
from typing import Dict, Tuple, Optional
import hashlib
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_requests_per_minute: int = 10, max_global_per_minute: int = 100):
        self.max_requests = max_requests_per_minute
        self.max_global = max_global_per_minute
        # Track requests by client pubkey hash
        self.requests: Dict[str, list] = defaultdict(list)
        # Track global requests across all clients
        self.global_requests: list = []
        # Track authenticated clients (pubkey_hash -> auth_timestamp)
        self.authenticated_clients: Dict[str, float] = {}
        # Track failed auth attempts
        self.failed_auths: Dict[str, list] = defaultdict(list)
        # Track PoW challenges (challenge_hash -> (timestamp, difficulty))
        # Challenges expire after 5 minutes
        self.pow_challenges: Dict[str, Tuple[float, int]] = {}
        
    def is_allowed(self, client_pubkey: str) -> Tuple[bool, int, Optional[str]]:
        """Check if client is within rate limits.
        
        Returns (allowed, seconds_until_reset, reason)
        """
        # Hash the pubkey for privacy
        key_hash = hashlib.sha256(client_pubkey.encode()).hexdigest()[:16]
        
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Check global rate limit first (prevents DDoS with many keys)
        self.global_requests = [
            req_time for req_time in self.global_requests
            if req_time > minute_ago
        ]
        
        if len(self.global_requests) >= self.max_global:
            logger.warning(f"Global rate limit exceeded: {len(self.global_requests)}/{self.max_global}")
            oldest = min(self.global_requests)
            wait_time = int(60 - (current_time - oldest))
            return False, wait_time, "Global rate limit exceeded"
        
        # Check per-client rate limit
        self.requests[key_hash] = [
            req_time for req_time in self.requests[key_hash]
            if req_time > minute_ago
        ]
        
        if len(self.requests[key_hash]) >= self.max_requests:
            logger.warning(f"Client {key_hash} rate limit exceeded")
            oldest_request = min(self.requests[key_hash])
            wait_time = int(60 - (current_time - oldest_request))
            return False, wait_time, "Client rate limit exceeded"
            
        # Record this request
        self.requests[key_hash].append(current_time)
        self.global_requests.append(current_time)
        return True, 0, None
    
    def record_auth_failure(self, client_pubkey: str):
        """Record a failed authentication attempt.
        
        After too many failures, temporarily block the client.
        """
        key_hash = hashlib.sha256(client_pubkey.encode()).hexdigest()[:16]
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Clean old failures
        self.failed_auths[key_hash] = [
            fail_time for fail_time in self.failed_auths[key_hash]
            if fail_time > hour_ago
        ]
        
        self.failed_auths[key_hash].append(current_time)
        
        if len(self.failed_auths[key_hash]) > 10:
            logger.warning(f"Client {key_hash} has {len(self.failed_auths[key_hash])} failed auth attempts")
    
    def is_blocked_by_auth_failures(self, client_pubkey: str) -> bool:
        """Check if client is temporarily blocked due to auth failures."""
        key_hash = hashlib.sha256(client_pubkey.encode()).hexdigest()[:16]
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Clean old failures
        self.failed_auths[key_hash] = [
            fail_time for fail_time in self.failed_auths[key_hash]
            if fail_time > hour_ago
        ]
        
        return len(self.failed_auths[key_hash]) > 20  # Block after 20 failures in an hour
    
    def generate_pow_challenge(self, difficulty: int = 4) -> str:
        """Generate a proof-of-work challenge and store it.

        Args:
            difficulty: Number of leading zeros required in hash

        Returns:
            Challenge string in format 'difficulty:random_challenge'
        """
        # Generate unique challenge
        challenge_hash = hashlib.sha256(
            f"{time.time()}{len(self.pow_challenges)}".encode()
        ).hexdigest()

        # Store challenge with timestamp and difficulty
        self.pow_challenges[challenge_hash] = (time.time(), difficulty)

        # Clean up expired challenges (older than 5 minutes)
        current_time = time.time()
        expired = [
            ch for ch, (ts, _) in self.pow_challenges.items()
            if current_time - ts > 300
        ]
        for ch in expired:
            del self.pow_challenges[ch]

        return f"{difficulty}:{challenge_hash}"

    def verify_pow(self, challenge: str, nonce: str) -> bool:
        """Verify a proof-of-work solution.

        Args:
            challenge: Original challenge in format 'difficulty:challenge_hash'
            nonce: Client's proposed nonce

        Returns:
            True if the proof-of-work is valid
        """
        try:
            parts = challenge.split(':')
            if len(parts) != 2:
                logger.warning("Invalid PoW challenge format")
                return False

            difficulty = int(parts[0])
            challenge_hash = parts[1]

            # Verify challenge was actually issued and not expired
            if challenge_hash not in self.pow_challenges:
                logger.warning(f"PoW challenge not found or expired: {challenge_hash[:16]}...")
                return False

            stored_time, stored_difficulty = self.pow_challenges[challenge_hash]

            # Verify difficulty matches
            if difficulty != stored_difficulty:
                logger.warning(f"PoW difficulty mismatch: {difficulty} != {stored_difficulty}")
                return False

            # Verify not expired (5 minutes)
            if time.time() - stored_time > 300:
                logger.warning("PoW challenge expired")
                del self.pow_challenges[challenge_hash]
                return False

            # Compute hash of challenge + nonce
            solution = hashlib.sha256(f"{challenge_hash}{nonce}".encode()).hexdigest()

            # Check if it has the required leading zeros
            required = '0' * difficulty
            is_valid = solution.startswith(required)

            # Remove challenge after successful verification (one-time use)
            if is_valid:
                del self.pow_challenges[challenge_hash]

            return is_valid

        except Exception as e:
            logger.error(f"PoW verification failed: {e}")
            return False
