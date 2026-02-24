"""
Retry Logic with Exponential Backoff and Fallback Mechanisms

This module provides resilient communication patterns for:
- Client -> Coordinator
- Client -> Node (direct)
- Node -> Coordinator

Handles:
- Network failures
- Coordinator unavailability
- Node failures mid-inference
- Network partitions
"""

import asyncio
import time
import random
import logging
from typing import Callable, Optional, Any, List, TypeVar, Coroutine
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)."""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            # Add ±25% jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class RetryableError(Exception):
    """Base exception for errors that should trigger retry."""
    pass


class CoordinatorUnreachable(RetryableError):
    """Coordinator is down or unreachable."""
    pass


class NodeUnreachable(RetryableError):
    """Node is down or unreachable."""
    pass


class NetworkPartition(RetryableError):
    """Network partition detected."""
    pass


class TemporaryFailure(RetryableError):
    """Temporary failure that should be retried."""
    pass


class PermanentFailure(Exception):
    """Permanent failure that should NOT be retried."""
    pass


def retry_async(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (RetryableError,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator for async functions that implements exponential backoff retry.
    
    Example:
        @retry_async(config=RetryConfig(max_attempts=5))
        async def submit_job(payload):
            # ... network call that might fail
            pass
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.get_delay(attempt)
                        
                        if on_retry:
                            on_retry(e, attempt)
                        else:
                            logger.warning(
                                f"{func.__name__} failed (attempt {attempt + 1}/{config.max_attempts}): {e}. "
                                f"Retrying in {delay:.2f}s..."
                            )
                        
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {config.max_attempts} attempts: {e}"
                        )
                
                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"{func.__name__} failed with non-retryable error: {e}")
                    raise
            
            # All retries exhausted
            raise last_exception
        
        return wrapper
    return decorator


class FallbackChain:
    """
    Execute operations with fallback strategies.
    
    Example:
        chain = FallbackChain()
        chain.add_strategy("primary_coordinator", submit_to_primary)
        chain.add_strategy("secondary_coordinator", submit_to_secondary)
        chain.add_strategy("cached_nodes", submit_direct_to_node)
        
        result = await chain.execute(payload)
    """
    
    def __init__(self, name: str = "FallbackChain"):
        self.name = name
        self.strategies: List[tuple[str, Callable]] = []
    
    def add_strategy(self, name: str, func: Callable[..., Coroutine[Any, Any, T]]):
        """Add a fallback strategy."""
        self.strategies.append((name, func))
    
    async def execute(self, *args, **kwargs) -> T:
        """
        Execute strategies in order until one succeeds.
        
        Raises:
            Exception: If all strategies fail
        """
        errors = []
        
        for strategy_name, strategy_func in self.strategies:
            try:
                logger.debug(f"{self.name}: Trying strategy '{strategy_name}'")
                result = await strategy_func(*args, **kwargs)
                logger.info(f"{self.name}: Strategy '{strategy_name}' succeeded")
                return result
                
            except Exception as e:
                logger.warning(f"{self.name}: Strategy '{strategy_name}' failed: {e}")
                errors.append((strategy_name, e))
        
        # All strategies failed
        error_summary = "; ".join(f"{name}: {error}" for name, error in errors)
        raise Exception(f"{self.name}: All strategies failed: {error_summary}")


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable[..., Coroutine[Any, Any, T]], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker.
        
        Raises:
            Exception: If circuit is OPEN
        """
        if self._state == "OPEN":
            # Check if we should try recovery
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                logger.info("Circuit breaker entering HALF_OPEN state")
                self._state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN - failing fast")
        
        try:
            result = await func(*args, **kwargs)
            
            # Success - reset if we were in HALF_OPEN
            if self._state == "HALF_OPEN":
                logger.info("Circuit breaker recovered - entering CLOSED state")
                self._state = "CLOSED"
                self._failure_count = 0
            
            return result
            
        except self.expected_exception as e:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == "HALF_OPEN":
                # Failed during recovery attempt
                logger.warning("Circuit breaker recovery failed - returning to OPEN state")
                self._state = "OPEN"
            elif self._failure_count >= self.failure_threshold:
                # Too many failures
                logger.error(
                    f"Circuit breaker threshold exceeded ({self._failure_count} failures) - "
                    f"entering OPEN state"
                )
                self._state = "OPEN"
            
            raise


class NodeCache:
    """
    Cache of known nodes for direct peer-to-peer fallback.
    
    When coordinator is unavailable, clients can use cached node list
    to attempt direct connections.
    """
    
    def __init__(self, cache_ttl: int = 300):  # 5 minutes default
        self.cache_ttl = cache_ttl
        self._nodes: List[dict] = []
        self._last_update: float = 0
    
    def update(self, nodes: List[dict]):
        """Update cached node list."""
        self._nodes = nodes
        self._last_update = time.time()
        logger.debug(f"Updated node cache with {len(nodes)} nodes")
    
    def get_nodes(self) -> List[dict]:
        """Get cached nodes if not expired."""
        if self.is_valid():
            return self._nodes.copy()
        return []
    
    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._nodes:
            return False
        return (time.time() - self._last_update) < self.cache_ttl
    
    def select_node(self, criteria: Optional[Callable[[dict], bool]] = None) -> Optional[dict]:
        """
        Select a node from cache based on criteria.
        
        Args:
            criteria: Optional function to filter nodes
            
        Returns:
            Selected node or None
        """
        nodes = self.get_nodes()
        
        if criteria:
            nodes = [n for n in nodes if criteria(n)]
        
        if not nodes:
            return None
        
        # Simple random selection
        # Could be enhanced with load-based selection
        return random.choice(nodes)


# Example usage patterns:

async def submit_job_with_retry(
    coordinator_url: str,
    payload: dict,
    node_cache: Optional[NodeCache] = None
) -> dict:
    """
    Example: Submit job with comprehensive retry and fallback.
    
    Strategy:
    1. Try primary coordinator with retry
    2. Try cached node list (direct P2P)
    3. Fail
    """
    chain = FallbackChain(name="SubmitJob")
    
    # Strategy 1: Primary coordinator with retry
    @retry_async(config=RetryConfig(max_attempts=3))
    async def try_coordinator():
        # Would use actual HTTP client here
        raise CoordinatorUnreachable("Example: coordinator down")
    
    chain.add_strategy("primary_coordinator", try_coordinator)
    
    # Strategy 2: Direct to cached node
    if node_cache and node_cache.is_valid():
        async def try_cached_node():
            node = node_cache.select_node()
            if not node:
                raise NodeUnreachable("No cached nodes available")
            
            # Would use actual HTTP client here
            # return await http_client.post(f"{node['address']}/submit", json=payload)
            logger.info(f"Would submit directly to node: {node['node_id']}")
            raise NodeUnreachable("Example: node unavailable")
        
        chain.add_strategy("cached_node", try_cached_node)
    
    # Execute chain
    return await chain.execute()


# Health check with circuit breaker example
class HealthChecker:
    """Check health with circuit breaker to prevent cascading failures."""
    
    def __init__(self, target_url: str):
        self.target_url = target_url
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0
        )
    
    async def check_health(self) -> bool:
        """Check if target is healthy."""
        try:
            async def health_check():
                # Would use actual HTTP client
                # response = await http_client.get(f"{self.target_url}/health")
                # return response.status_code == 200
                raise Exception("Health check failed")
            
            await self.circuit_breaker.call(health_check)
            return True
            
        except Exception:
            return False
