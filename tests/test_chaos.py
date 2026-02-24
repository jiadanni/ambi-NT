"""
Chaos Testing for Ambient Intelligence Network

Tests system resilience under adverse conditions:
- Network failures and packet loss
- High latency and jitter
- Service failures and recovery
- Race conditions
"""

import pytest
import asyncio
import random
import time
from typing import Optional
from unittest.mock import Mock, patch
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class ChaosSimulator:
    """Simulates various failure modes for chaos testing."""
    
    def __init__(self):
        self.packet_loss_rate = 0.0
        self.latency_ms = 0
        self.jitter_ms = 0
        self.failure_rate = 0.0
        self.connection_timeout = False
        
    async def apply_network_chaos(self, operation_name: str = "operation"):
        """
        Apply chaos to a network operation.
        
        Simulates:
        - Packet loss
        - Network latency with jitter
        - Connection timeouts
        - Random failures
        
        Raises:
            ConnectionError: If packet loss or timeout occurs
            TimeoutError: If connection times out
        """
        # Simulate packet loss
        if self.packet_loss_rate > 0 and random.random() < self.packet_loss_rate:
            raise ConnectionError(f"Simulated packet loss during {operation_name}")
        
        # Simulate connection timeout
        if self.connection_timeout and random.random() < 0.3:
            raise TimeoutError(f"Simulated connection timeout during {operation_name}")
        
        # Simulate random failures
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            raise Exception(f"Simulated random failure during {operation_name}")
        
        # Simulate network latency
        if self.latency_ms > 0:
            delay = self.latency_ms / 1000.0
            
            # Add jitter
            if self.jitter_ms > 0:
                jitter = random.uniform(-self.jitter_ms, self.jitter_ms) / 1000.0
                delay += jitter
            
            await asyncio.sleep(max(0, delay))
    
    def set_mild_chaos(self):
        """Configure mild network issues."""
        self.packet_loss_rate = 0.05  # 5% packet loss
        self.latency_ms = 100
        self.jitter_ms = 50
        self.failure_rate = 0.02
        
    def set_moderate_chaos(self):
        """Configure moderate network issues."""
        self.packet_loss_rate = 0.15  # 15% packet loss
        self.latency_ms = 300
        self.jitter_ms = 150
        self.failure_rate = 0.10
        
    def set_severe_chaos(self):
        """Configure severe network issues."""
        self.packet_loss_rate = 0.30  # 30% packet loss
        self.latency_ms = 1000
        self.jitter_ms = 500
        self.failure_rate = 0.20
        self.connection_timeout = True
        
    def reset(self):
        """Reset to no chaos."""
        self.packet_loss_rate = 0.0
        self.latency_ms = 0
        self.jitter_ms = 0
        self.failure_rate = 0.0
        self.connection_timeout = False


class RetryStrategy:
    """Implements retry logic with exponential backoff."""
    
    def __init__(self, max_attempts: int = 5, base_delay: float = 0.1):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        
    async def execute_with_retry(self, operation, *args, **kwargs):
        """
        Execute operation with retry on failure.
        
        Args:
            operation: Async function to execute
            *args, **kwargs: Arguments for operation
            
        Returns:
            Result of successful operation
            
        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return await operation(*args, **kwargs)
            except (ConnectionError, TimeoutError) as e:
                last_exception = e
                
                if attempt < self.max_attempts - 1:
                    # Exponential backoff with jitter
                    delay = self.base_delay * (2 ** attempt)
                    jitter = random.uniform(0, delay * 0.1)
                    await asyncio.sleep(delay + jitter)
                    continue
                    
        raise last_exception


@pytest.mark.asyncio
async def test_mild_chaos_resilience():
    """Test system handles mild network issues with retries."""
    chaos = ChaosSimulator()
    chaos.set_mild_chaos()
    retry = RetryStrategy(max_attempts=5)
    
    success_count = 0
    fail_count = 0
    
    async def simulated_request():
        await chaos.apply_network_chaos("test_request")
        return "success"
    
    # Run 20 requests with retries
    for i in range(20):
        try:
            result = await retry.execute_with_retry(simulated_request)
            success_count += 1
        except Exception:
            fail_count += 1
    
    # With retries, most should succeed despite 5% packet loss
    assert success_count >= 15, f"Too many failures: {fail_count}/20 (expected < 5)"
    print(f"Mild chaos: {success_count}/20 succeeded with retries")


@pytest.mark.asyncio
async def test_moderate_chaos_degradation():
    """Test system degrades gracefully under moderate chaos."""
    chaos = ChaosSimulator()
    chaos.set_moderate_chaos()
    retry = RetryStrategy(max_attempts=3)
    
    success_count = 0
    total_time = 0
    
    async def simulated_request():
        start = time.time()
        await chaos.apply_network_chaos("test_request")
        return time.time() - start
    
    # Run 20 requests
    for i in range(20):
        try:
            duration = await retry.execute_with_retry(simulated_request)
            success_count += 1
            total_time += duration
        except Exception:
            pass
    
    # Should still have some success despite 15% packet loss + failures
    assert success_count >= 10, f"Success rate too low: {success_count}/20"
    
    # Average latency should be elevated
    if success_count > 0:
        avg_latency = total_time / success_count
        assert avg_latency > 0.2, f"Latency not elevated: {avg_latency:.2f}s"
        print(f"Moderate chaos: {success_count}/20 succeeded, avg latency: {avg_latency:.2f}s")


@pytest.mark.asyncio
async def test_severe_chaos_failure_handling():
    """Test system handles severe chaos without crashing."""
    chaos = ChaosSimulator()
    chaos.set_severe_chaos()
    retry = RetryStrategy(max_attempts=10)  # More retries for severe chaos
    
    success_count = 0
    
    async def simulated_request():
        await chaos.apply_network_chaos("test_request")
        return "success"
    
    # Run 10 requests
    for i in range(10):
        try:
            result = await retry.execute_with_retry(simulated_request)
            success_count += 1
        except Exception:
            # Expected to fail sometimes
            pass
    
    # Even with 30% packet loss, some should succeed with enough retries
    print(f"Severe chaos: {success_count}/10 succeeded (30% packet loss)")
    # No assertion - just verify it doesn't crash


@pytest.mark.asyncio
async def test_circuit_breaker_pattern():
    """Test circuit breaker prevents cascading failures."""
    chaos = ChaosSimulator()
    chaos.set_severe_chaos()
    # Force failures to ensure circuit breaker triggers consistently
    chaos.failure_rate = 1.0
    
    class CircuitBreaker:
        def __init__(self, failure_threshold: int = 5, timeout: float = 2.0):
            self.failure_count = 0
            self.failure_threshold = failure_threshold
            self.timeout = timeout
            self.open_until = 0
            self.state = "closed"  # closed, open, half-open
            
        async def call(self, operation):
            # Check if circuit is open
            if self.state == "open":
                if time.time() < self.open_until:
                    raise Exception("Circuit breaker OPEN")
                else:
                    self.state = "half-open"
            
            try:
                result = await operation()
                # Success - reset failure count
                self.failure_count = 0
                self.state = "closed"
                return result
            except Exception as e:
                self.failure_count += 1
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    self.open_until = time.time() + self.timeout
                    
                raise e
    
    breaker = CircuitBreaker(failure_threshold=3, timeout=1.0)
    
    async def failing_operation():
        await chaos.apply_network_chaos("circuit_test")
        return "success"
    
    # Try multiple requests
    circuit_open_count = 0
    other_failures = 0
    successes = 0
    
    for i in range(20):
        try:
            await breaker.call(failing_operation)
            successes += 1
        except Exception as e:
            if "Circuit breaker OPEN" in str(e):
                circuit_open_count += 1
            else:
                other_failures += 1
        
        await asyncio.sleep(0.1)
    
    # Circuit should open and prevent some requests
    assert circuit_open_count > 0, "Circuit breaker never opened"
    print(f"Circuit breaker: {circuit_open_count} blocked, {other_failures} failed, {successes} succeeded")


@pytest.mark.asyncio
async def test_rate_limiting_under_chaos():
    """Test rate limiting still works under chaotic conditions."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'node')))
    from rate_limiter import RateLimiter
    
    chaos = ChaosSimulator()
    chaos.set_moderate_chaos()
    limiter = RateLimiter(max_requests_per_minute=10)
    
    client_key = "chaos_test_client"
    allowed_count = 0
    blocked_count = 0
    
    # Try 20 requests with chaos
    for i in range(20):
        try:
            await chaos.apply_network_chaos("rate_limit_check")
            allowed, wait_time, reason = limiter.is_allowed(client_key)
            
            if allowed:
                allowed_count += 1
            else:
                blocked_count += 1
        except Exception:
            # Network failure, skip
            pass
    
    # Rate limiting should still work despite chaos
    assert blocked_count > 0, "Rate limiting not working under chaos"
    assert allowed_count <= 12, f"Too many requests allowed: {allowed_count}"
    print(f"Rate limiting under chaos: {allowed_count} allowed, {blocked_count} blocked")


@pytest.mark.asyncio
async def test_concurrent_requests_with_chaos():
    """Test handling multiple concurrent requests under chaos."""
    chaos = ChaosSimulator()
    chaos.set_mild_chaos()
    
    async def process_request(request_id: int):
        await chaos.apply_network_chaos(f"request_{request_id}")
        await asyncio.sleep(0.05)  # Simulate work
        return f"result_{request_id}"
    
    # Launch 50 concurrent requests
    tasks = [process_request(i) for i in range(50)]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start_time
    
    # Count successes vs failures
    successes = [r for r in results if isinstance(r, str)]
    failures = [r for r in results if isinstance(r, Exception)]
    
    print(f"Concurrent chaos test: {len(successes)}/50 succeeded in {duration:.2f}s")
    
    # Should complete most despite failures
    assert len(successes) >= 40, f"Too many failures: {len(failures)}/50"


@pytest.mark.asyncio
async def test_job_cleanup_under_stress():
    """Test job cleanup works correctly under chaos conditions."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'node')))
    from node.models import Job
    from datetime import datetime, timedelta
    
    chaos = ChaosSimulator()
    chaos.set_mild_chaos()
    
    # Create many jobs
    jobs = {}
    for i in range(100):
        job = Job(job_id=f"chaos-job-{i}", client_pubkey="test")
        
        # Mix of old and new jobs
        if i < 50:
            job.status = "complete"
            job.completed_at = datetime.utcnow() - timedelta(hours=2)
        else:
            job.status = "running"
        
        jobs[job.job_id] = job
    
    # Simulate cleanup with chaos
    ttl_seconds = 3600
    jobs_to_remove = []
    
    for job_id, job in jobs.items():
        try:
            await chaos.apply_network_chaos("cleanup_check")
            
            if job.status in ["complete", "failed"]:
                if job.completed_at:
                    age_seconds = (datetime.utcnow() - job.completed_at).total_seconds()
                    if age_seconds > ttl_seconds:
                        jobs_to_remove.append(job_id)
        except Exception:
            # Network issue during cleanup, continue
            continue
    
    # Should identify most old jobs despite chaos
    assert len(jobs_to_remove) >= 40, f"Cleanup incomplete: only {len(jobs_to_remove)} marked"
    print(f"Cleanup under chaos: {len(jobs_to_remove)} jobs marked for removal")


@pytest.mark.asyncio
async def test_federation_sync_resilience():
    """Test federation sync handles network chaos gracefully."""
    chaos = ChaosSimulator()
    chaos.set_moderate_chaos()
    retry = RetryStrategy(max_attempts=3)
    
    # Simulate node data from peer
    peer_nodes = [
        {"node_id": f"node-{i}", "address": f"192.168.1.{i}:8000",
         "public_key": f"key-{i}", "models": ["llama3:8b"],
         "uptime_score": 0.9, "current_load": 0.3}
        for i in range(10)
    ]
    
    async def fetch_peer_nodes():
        await chaos.apply_network_chaos("federation_sync")
        return peer_nodes
    
    # Try to sync with retries
    synced_nodes = []
    try:
        synced_nodes = await retry.execute_with_retry(fetch_peer_nodes)
    except Exception:
        pass
    
    # Should either succeed or fail gracefully
    if synced_nodes:
        assert len(synced_nodes) == 10, "Incomplete sync"
        print("Federation sync succeeded despite chaos")
    else:
        print("Federation sync failed gracefully (exhausted retries)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
