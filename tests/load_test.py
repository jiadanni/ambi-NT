#!/usr/bin/env python3
"""
Local Load Testing for Ambient Intelligence Node

Tests performance and stability under load without external tools.
Runs entirely locally with configurable parameters.

Usage:
    python load_test.py --duration 60 --concurrency 10
    python load_test.py --requests 1000 --rps 50
"""

import argparse
import asyncio
import time
import sys
import os
from typing import List, Dict
from dataclasses import dataclass
from collections import defaultdict
import statistics

# Add paths for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'node')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'client-cli')))


@dataclass
class RequestResult:
    """Result of a single request."""
    success: bool
    duration: float
    status_code: int = 0
    error: str = ""
    timestamp: float = 0


class LoadTester:
    """Local load testing framework."""
    
    def __init__(self, target_url: str = "http://localhost:8000"):
        self.target_url = target_url
        self.results: List[RequestResult] = []
        self.start_time = 0
        self.end_time = 0
        
    async def single_request(self) -> RequestResult:
        """Execute a single test request."""
        start = time.time()
        
        try:
            # Simulate a simple health check (fast)
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.target_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    duration = time.time() - start
                    return RequestResult(
                        success=response.status == 200,
                        duration=duration,
                        status_code=response.status,
                        timestamp=start
                    )
        except asyncio.TimeoutError:
            return RequestResult(
                success=False,
                duration=time.time() - start,
                error="Timeout",
                timestamp=start
            )
        except Exception as e:
            return RequestResult(
                success=False,
                duration=time.time() - start,
                error=str(e),
                timestamp=start
            )
    
    async def run_concurrent_batch(self, num_requests: int) -> List[RequestResult]:
        """Run a batch of concurrent requests."""
        tasks = [self.single_request() for _ in range(num_requests)]
        return await asyncio.gather(*tasks)
    
    async def run_sustained_load(
        self,
        duration_seconds: int,
        requests_per_second: int
    ):
        """Run sustained load for a duration."""
        print(f"\n{'='*60}")
        print(f"Load Test: {requests_per_second} req/s for {duration_seconds}s")
        print(f"Target: {self.target_url}")
        print(f"{'='*60}\n")
        
        self.start_time = time.time()
        interval = 1.0 / requests_per_second
        
        while (time.time() - self.start_time) < duration_seconds:
            batch_start = time.time()
            
            # Launch request
            result = await self.single_request()
            self.results.append(result)
            
            # Rate limiting
            elapsed = time.time() - batch_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            
            # Progress indicator
            if len(self.results) % 100 == 0:
                success_rate = sum(1 for r in self.results if r.success) / len(self.results) * 100
                print(f"  Progress: {len(self.results)} requests, {success_rate:.1f}% success", end='\r')
        
        self.end_time = time.time()
        print()  # New line after progress
    
    async def run_burst_test(self, num_requests: int, concurrency: int):
        """Run burst test with specified concurrency."""
        print(f"\n{'='*60}")
        print(f"Burst Test: {num_requests} requests, {concurrency} concurrent")
        print(f"Target: {self.target_url}")
        print(f"{'='*60}\n")
        
        self.start_time = time.time()
        
        # Run in batches to avoid overwhelming the system
        batch_size = concurrency
        for i in range(0, num_requests, batch_size):
            batch_count = min(batch_size, num_requests - i)
            results = await self.run_concurrent_batch(batch_count)
            self.results.extend(results)
            
            # Progress
            success_rate = sum(1 for r in self.results if r.success) / len(self.results) * 100
            print(f"  Progress: {len(self.results)}/{num_requests} ({success_rate:.1f}% success)", end='\r')
        
        self.end_time = time.time()
        print()
    
    def print_report(self):
        """Print detailed test report."""
        if not self.results:
            print("No results to report")
            return
        
        total_duration = self.end_time - self.start_time
        total_requests = len(self.results)
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        
        print(f"\n{'='*60}")
        print(f"LOAD TEST RESULTS")
        print(f"{'='*60}\n")
        
        # Summary
        print("Summary:")
        print(f"  Total Requests:    {total_requests}")
        print(f"  Successful:        {len(successful)} ({len(successful)/total_requests*100:.1f}%)")
        print(f"  Failed:            {len(failed)} ({len(failed)/total_requests*100:.1f}%)")
        print(f"  Duration:          {total_duration:.2f}s")
        print(f"  Requests/Second:   {total_requests/total_duration:.2f}")
        
        if successful:
            durations = [r.duration for r in successful]
            print(f"\nLatency (successful requests):")
            print(f"  Min:               {min(durations)*1000:.2f}ms")
            print(f"  Max:               {max(durations)*1000:.2f}ms")
            print(f"  Mean:              {statistics.mean(durations)*1000:.2f}ms")
            print(f"  Median:            {statistics.median(durations)*1000:.2f}ms")
            
            if len(durations) > 1:
                print(f"  Std Dev:           {statistics.stdev(durations)*1000:.2f}ms")
            
            # Percentiles
            sorted_durations = sorted(durations)
            p50 = sorted_durations[int(len(sorted_durations) * 0.50)]
            p90 = sorted_durations[int(len(sorted_durations) * 0.90)]
            p95 = sorted_durations[int(len(sorted_durations) * 0.95)]
            p99 = sorted_durations[int(len(sorted_durations) * 0.99)]
            
            print(f"\n  Percentiles:")
            print(f"    P50:             {p50*1000:.2f}ms")
            print(f"    P90:             {p90*1000:.2f}ms")
            print(f"    P95:             {p95*1000:.2f}ms")
            print(f"    P99:             {p99*1000:.2f}ms")
        
        if failed:
            print(f"\nErrors:")
            error_types = defaultdict(int)
            for r in failed:
                error_types[r.error] += 1
            
            for error, count in sorted(error_types.items(), key=lambda x: -x[1]):
                print(f"  {error}: {count}")
        
        # Recommendations
        print(f"\n{'='*60}")
        print("Recommendations:")
        
        success_rate = len(successful) / total_requests * 100
        if success_rate < 95:
            print("  ⚠️  Success rate below 95% - check error logs")
        elif success_rate < 99:
            print("  ℹ️  Success rate acceptable but could be improved")
        else:
            print("  ✅ Excellent success rate!")
        
        if successful:
            avg_latency = statistics.mean([r.duration for r in successful]) * 1000
            if avg_latency > 1000:
                print("  ⚠️  High latency detected - check system load")
            elif avg_latency > 500:
                print("  ℹ️  Moderate latency - consider optimization")
            else:
                print("  ✅ Low latency - performing well!")
        
        actual_rps = total_requests / total_duration
        if actual_rps < 10:
            print("  ℹ️  Low throughput - suitable for small deployments")
        elif actual_rps < 100:
            print("  ✅ Good throughput for medium deployments")
        else:
            print("  ✅ Excellent throughput for production use!")
        
        print(f"{'='*60}\n")


async def main():
    parser = argparse.ArgumentParser(description="Local load testing for Ambient Intelligence")
    parser.add_argument("--url", default="http://localhost:8000", help="Target URL")
    parser.add_argument("--duration", type=int, help="Test duration in seconds")
    parser.add_argument("--requests", type=int, help="Total number of requests")
    parser.add_argument("--rps", type=int, default=10, help="Requests per second (for duration mode)")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent requests (for burst mode)")
    
    args = parser.parse_args()
    
    tester = LoadTester(target_url=args.url)
    
    try:
        if args.duration:
            # Sustained load test
            await tester.run_sustained_load(args.duration, args.rps)
        elif args.requests:
            # Burst test
            await tester.run_burst_test(args.requests, args.concurrency)
        else:
            # Default: quick test
            print("No duration or requests specified, running quick test...")
            await tester.run_burst_test(100, 10)
        
        tester.print_report()
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        if tester.results:
            tester.print_report()
        sys.exit(0)


if __name__ == "__main__":
    try:
        import aiohttp
    except ImportError:
        print("Error: aiohttp not installed")
        print("Install with: pip install aiohttp")
        sys.exit(1)
    
    asyncio.run(main())
