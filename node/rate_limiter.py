"""
Rate limiting for node endpoints with multi-level protection
"""

import time
from collections import defaultdict
from typing import Dict, Tuple, Optional
import hashlib
import logging
import uuid
import redis

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_requests_per_minute: int = 10, max_global_per_minute: int = 100, redis_url: Optional[str] = None):
        self.max_requests = max_requests_per_minute
        self.max_global = max_global_per_minute
        self.redis_url = redis_url
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                logger.info(f"Connected to Redis at {redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis_client = None

        # In-memory fallbacks
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
        
        if self.redis_client:
            try:
                # Redis pipelining for atomic operations
                pipe = self.redis_client.pipeline()
                now = time.time()
                minute_ago = now - 60

                # Global
                global_key = "ratelimit:global"
                pipe.zremrangebyscore(global_key, 0, minute_ago)
                pipe.zcard(global_key)

                # Client
                client_key = f"ratelimit:client:{key_hash}"
                pipe.zremrangebyscore(client_key, 0, minute_ago)
                pipe.zcard(client_key)

                results = pipe.execute()
                # results: [removed_global, global_count, removed_client, client_count]

                global_count = results[1]
                client_count = results[3]

                if global_count >= self.max_global:
                    return False, 60, "Global rate limit exceeded"

                if client_count >= self.max_requests:
                    return False, 60, "Client rate limit exceeded"

                # Add current request
                pipe = self.redis_client.pipeline()
                # Use timestamp as score and member to ensure uniqueness
                pipe.zadd(global_key, {str(now): now})
                pipe.expire(global_key, 60)
                pipe.zadd(client_key, {str(now): now})
                pipe.expire(client_key, 60)
                pipe.execute()

                return True, 0, None

            except redis.RedisError as e:
                logger.error(f"Redis rate limit error, falling back to in-memory: {e}")
                # Fallback to in-memory logic

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

        if self.redis_client:
            try:
                key = f"auth_fail:{key_hash}"
                pipe = self.redis_client.pipeline()
                hour_ago = current_time - 3600
                pipe.zremrangebyscore(key, 0, hour_ago)
                pipe.zadd(key, {str(current_time): current_time})
                pipe.expire(key, 3600)
                # Check count for logging
                pipe.zcard(key)
                results = pipe.execute()
                count = results[3]
                if count > 10:
                    logger.warning(f"Client {key_hash} has {count} failed auth attempts")
                return
            except redis.RedisError as e:
                logger.error(f"Redis error in record_auth_failure: {e}")
                # Fallback

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

        if self.redis_client:
            try:
                key = f"auth_fail:{key_hash}"
                hour_ago = current_time - 3600
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, hour_ago)
                pipe.zcard(key)
                results = pipe.execute()
                count = results[1]
                return count > 20
            except redis.RedisError as e:
                logger.error(f"Redis error in is_blocked_by_auth_failures: {e}")
                # Fallback

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
            f"{time.time()}{uuid.uuid4()}".encode()
        ).hexdigest()

        if self.redis_client:
            try:
                key = f"pow:{challenge_hash}"
                # Store difficulty
                self.redis_client.setex(key, 300, difficulty)
                return f"{difficulty}:{challenge_hash}"
            except redis.RedisError as e:
                logger.error(f"Redis error in generate_pow_challenge: {e}")
                # Fallback

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

            if self.redis_client:
                try:
                    key = f"pow:{challenge_hash}"
                    stored_difficulty = self.redis_client.get(key)

                    if not stored_difficulty:
                        logger.warning(f"PoW challenge not found or expired: {challenge_hash[:16]}...")
                        return False

                    stored_difficulty = int(stored_difficulty)

                    if difficulty != stored_difficulty:
                        logger.warning(f"PoW difficulty mismatch: {difficulty} != {stored_difficulty}")
                        return False

                    # Compute hash of challenge + nonce
                    solution = hashlib.sha256(f"{challenge_hash}{nonce}".encode()).hexdigest()

                    # Check if it has the required leading zeros
                    required = '0' * difficulty
                    is_valid = solution.startswith(required)

                    if is_valid:
                        self.redis_client.delete(key)

                    return is_valid
                except redis.RedisError as e:
                    logger.error(f"Redis error in verify_pow: {e}")
                    # Fallback

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
