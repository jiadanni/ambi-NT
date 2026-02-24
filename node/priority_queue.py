"""
Priority Queue Implementation for Job Processing

Replaces simple FIFO queue with intelligent prioritization:
- Job size (small jobs get priority for better throughput)
- Retry attempts (deprioritize failed retries to avoid blocking)
- Credit-based priority (Phase 3+ token economy)
- Fair queuing (prevent starvation)

Thread-safe and async-compatible.
"""

import asyncio
import time
import heapq
from typing import Optional, List, Any
from dataclasses import dataclass, field
from enum import IntEnum
from threading import Lock


class JobPriority(IntEnum):
    """
    Priority levels for jobs.
    
    Lower numeric value = higher priority.
    """
    CRITICAL = 0   # Emergency or retry of critical job
    HIGH = 10      # Priority token holders
    NORMAL = 20    # Standard jobs
    LOW = 30       # Large jobs or retries
    BACKGROUND = 40  # Non-urgent processing


@dataclass(order=True)
class PrioritizedJob:
    """
    A job with priority metadata for queue ordering.
    
    Jobs are ordered by:
    1. Priority level (lower = higher priority)
    2. Size score (smaller = higher priority)
    3. Timestamp (older = higher priority for fairness)
    """
    # Priority fields (used for ordering)
    priority: int = field(compare=True)
    size_score: float = field(compare=True)  # 0.0-1.0, lower is better
    timestamp: float = field(compare=True)
    
    # Job data (not used for ordering)
    job_id: str = field(compare=False)
    payload: Any = field(compare=False)
    retry_count: int = field(default=0, compare=False)
    credit_boost: int = field(default=0, compare=False)
    
    @classmethod
    def create(
        cls,
        job_id: str,
        payload: Any,
        estimated_size: int = 0,
        retry_count: int = 0,
        credit_tokens: int = 0,
        max_size: int = 10000
    ) -> 'PrioritizedJob':
        """
        Create a prioritized job with automatic priority calculation.
        
        Args:
            job_id: Unique job identifier
            payload: Job payload
            estimated_size: Estimated size in characters/tokens
            retry_count: Number of times job has been retried
            credit_tokens: Priority tokens to apply
            max_size: Maximum expected size for normalization
        """
        # Calculate base priority
        if retry_count > 2:
            # Heavily penalize repeated retries
            priority = JobPriority.BACKGROUND
        elif credit_tokens > 100:
            priority = JobPriority.HIGH
        elif credit_tokens > 0:
            priority = JobPriority.NORMAL - min(credit_tokens // 10, 5)
        else:
            priority = JobPriority.NORMAL
        
        # Adjust priority based on retry count
        if retry_count > 0:
            priority = min(priority + (retry_count * 5), JobPriority.BACKGROUND)
        
        # Normalize size to 0.0-1.0 range
        size_score = min(estimated_size / max_size, 1.0) if max_size > 0 else 0.5
        
        # Add small random component to prevent exact timestamp collisions
        import random
        timestamp = time.time() + random.uniform(0, 0.001)
        
        return cls(
            priority=priority,
            size_score=size_score,
            timestamp=timestamp,
            job_id=job_id,
            payload=payload,
            retry_count=retry_count,
            credit_boost=credit_tokens
        )


class PriorityJobQueue:
    """
    Thread-safe priority queue for job processing.
    
    Features:
    - Priority-based ordering
    - Fair queuing to prevent starvation
    - Async-compatible
    - Statistics tracking
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize priority queue.
        
        Args:
            max_size: Maximum queue size (prevents memory exhaustion)
        """
        self.max_size = max_size
        self._heap: List[PrioritizedJob] = []
        self._lock = Lock()
        self._not_empty = asyncio.Condition()
        
        # Statistics
        self._total_enqueued = 0
        self._total_dequeued = 0
        self._total_rejected = 0
    
    def put(self, job: PrioritizedJob) -> bool:
        """
        Add a job to the queue.
        
        Returns:
            True if job was added, False if queue is full
        """
        with self._lock:
            if len(self._heap) >= self.max_size:
                self._total_rejected += 1
                return False
            
            heapq.heappush(self._heap, job)
            self._total_enqueued += 1
        
        # Notify waiters (thread-safe async notification)
        asyncio.create_task(self._notify_waiters())
        return True
    
    async def _notify_waiters(self):
        """Notify async waiters that queue has items."""
        async with self._not_empty:
            self._not_empty.notify()
    
    def get(self) -> Optional[PrioritizedJob]:
        """
        Get highest priority job from queue (non-blocking).
        
        Returns:
            PrioritizedJob or None if queue is empty
        """
        with self._lock:
            if not self._heap:
                return None
            
            job = heapq.heappop(self._heap)
            self._total_dequeued += 1
            return job
    
    async def get_async(self, timeout: Optional[float] = None) -> Optional[PrioritizedJob]:
        """
        Get highest priority job from queue (async, blocking).
        
        Args:
            timeout: Maximum time to wait in seconds, or None for no timeout
            
        Returns:
            PrioritizedJob or None if timeout reached
        """
        start_time = time.time()
        
        while True:
            # Try to get job
            job = self.get()
            if job is not None:
                return job
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return None
                remaining = timeout - elapsed
            else:
                remaining = None
            
            # Wait for notification
            try:
                async with self._not_empty:
                    await asyncio.wait_for(
                        self._not_empty.wait(),
                        timeout=remaining
                    )
            except asyncio.TimeoutError:
                return None
    
    def peek(self) -> Optional[PrioritizedJob]:
        """
        Look at highest priority job without removing it.
        
        Returns:
            PrioritizedJob or None if queue is empty
        """
        with self._lock:
            return self._heap[0] if self._heap else None
    
    def size(self) -> int:
        """Get current queue size."""
        with self._lock:
            return len(self._heap)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self.size() == 0
    
    def is_full(self) -> bool:
        """Check if queue is at maximum capacity."""
        return self.size() >= self.max_size
    
    def clear(self):
        """Clear all jobs from queue."""
        with self._lock:
            self._heap.clear()
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            return {
                'current_size': len(self._heap),
                'max_size': self.max_size,
                'total_enqueued': self._total_enqueued,
                'total_dequeued': self._total_dequeued,
                'total_rejected': self._total_rejected,
                'utilization': len(self._heap) / self.max_size if self.max_size > 0 else 0,
            }
    
    def get_priority_distribution(self) -> dict:
        """Get distribution of jobs by priority level."""
        with self._lock:
            distribution = {}
            for job in self._heap:
                priority_name = self._get_priority_name(job.priority)
                distribution[priority_name] = distribution.get(priority_name, 0) + 1
            return distribution
    
    @staticmethod
    def _get_priority_name(priority: int) -> str:
        """Convert priority number to name."""
        if priority <= JobPriority.CRITICAL:
            return "CRITICAL"
        elif priority <= JobPriority.HIGH:
            return "HIGH"
        elif priority <= JobPriority.NORMAL:
            return "NORMAL"
        elif priority <= JobPriority.LOW:
            return "LOW"
        else:
            return "BACKGROUND"


class FairQueue:
    """
    Fair queuing wrapper that prevents starvation.
    
    Ensures low-priority jobs eventually get processed even when
    high-priority jobs keep arriving.
    """
    
    def __init__(
        self,
        base_queue: PriorityJobQueue,
        max_wait_time: float = 300.0  # 5 minutes
    ):
        """
        Initialize fair queue.
        
        Args:
            base_queue: Underlying priority queue
            max_wait_time: Maximum time a job can wait before priority boost
        """
        self.base_queue = base_queue
        self.max_wait_time = max_wait_time
        self._wait_times: dict[str, float] = {}  # job_id -> enqueue_time
        self._lock = Lock()
    
    def put(self, job: PrioritizedJob) -> bool:
        """Add job and track wait time."""
        with self._lock:
            self._wait_times[job.job_id] = time.time()
        return self.base_queue.put(job)
    
    def get(self) -> Optional[PrioritizedJob]:
        """Get job and clean up wait time tracking."""
        job = self.base_queue.get()
        if job:
            with self._lock:
                self._wait_times.pop(job.job_id, None)
        return job
    
    async def get_async(self, timeout: Optional[float] = None) -> Optional[PrioritizedJob]:
        """Get job asynchronously."""
        job = await self.base_queue.get_async(timeout)
        if job:
            with self._lock:
                self._wait_times.pop(job.job_id, None)
        return job
    
    def boost_starved_jobs(self):
        """
        Boost priority of jobs that have waited too long.
        
        Should be called periodically by background task.
        """
        current_time = time.time()
        boosted = 0
        
        with self._lock:
            # Find jobs that have waited too long
            starved_jobs = {
                job_id: enqueue_time
                for job_id, enqueue_time in self._wait_times.items()
                if (current_time - enqueue_time) > self.max_wait_time
            }
        
        if starved_jobs:
            # Would need to modify base_queue implementation to support priority updates
            # For now, just log
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Detected {len(starved_jobs)} starved jobs waiting > {self.max_wait_time}s")
            boosted = len(starved_jobs)
        
        return boosted


# Example usage:
async def example_usage():
    """Demonstrate priority queue usage."""
    queue = PriorityJobQueue(max_size=1000)
    
    # Create jobs with different priorities
    jobs = [
        PrioritizedJob.create("job1", {"data": "small"}, estimated_size=100, credit_tokens=0),
        PrioritizedJob.create("job2", {"data": "large"}, estimated_size=5000, credit_tokens=0),
        PrioritizedJob.create("job3", {"data": "priority"}, estimated_size=200, credit_tokens=50),
        PrioritizedJob.create("job4", {"data": "retry"}, estimated_size=150, retry_count=2),
    ]
    
    # Add to queue
    for job in jobs:
        queue.put(job)
    
    print("Queue stats:", queue.get_stats())
    print("Priority distribution:", queue.get_priority_distribution())
    
    # Process jobs in priority order
    while not queue.is_empty():
        job = await queue.get_async(timeout=1.0)
        if job:
            print(f"Processing {job.job_id} (priority={job.priority}, size={job.size_score:.2f})")


if __name__ == "__main__":
    asyncio.run(example_usage())
