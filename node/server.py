"""
Ambient Intelligence Node Server

This FastAPI application exposes endpoints for:
- Receiving encrypted prompts
- Processing them through Ollama
- Returning encrypted responses

PRIVACY GUARANTEE: This server never logs, stores, or views plaintext prompts or responses.

Architecture:
- All encryption/decryption handled by crypto module
- Ollama communication isolated in ollama_client module
- No persistence (Phase 0) - all state in memory
"""

import os
import sys
import uuid
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from crypto import NodeCrypto, generate_keypair
from ollama_client import OllamaClient
from config import Config
from rate_limiter import RateLimiter
from prompt_sanitizer import PromptSanitizer
from context_manager import ContextManager
from models import (
    SubmitJobRequest,
    SubmitJobResponse,
    JobStatusResponse,
    PublicKeyResponse,
    HealthResponse,
    Job,
    Message
)

# Initialize configuration
config = Config()

# Prometheus metrics (optional if library available)
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
    METRICS_ENABLED = True
    jobs_submitted_total = Counter("jobs_submitted_total", "Total jobs submitted")
    jobs_running_gauge = Gauge("jobs_running", "Current running jobs")
    jobs_failed_total = Counter("jobs_failed_total", "Total jobs failed")
    jobs_completed_total = Counter("jobs_completed_total", "Total jobs completed")
    prompt_rejected_total = Counter("prompt_rejected_total", "Prompts rejected by validation/sanitization/rate limiting")
    rate_limit_hits_total = Counter("rate_limit_hits_total", "Times rate limiting blocked a submit")
    pow_challenges_issued_total = Counter("pow_challenges_issued_total", "Proof-of-work challenges issued")
    job_duration_seconds = Histogram(
        "job_duration_seconds",
        "Time from job start (running) to completion/failure",
        buckets=[0.5, 1, 2, 5, 10, 30, 60, 120, 300]
    )
except Exception:
    METRICS_ENABLED = False
    # Define no-op placeholders to avoid conditional clutter
    class _NoOp:
        def labels(self, *a, **k):
            return self
        def inc(self, *a, **k):
            pass
        def set(self, *a, **k):
            pass
        def observe(self, *a, **k):
            pass
    jobs_submitted_total = jobs_running_gauge = jobs_failed_total = jobs_completed_total = prompt_rejected_total = rate_limit_hits_total = pow_challenges_issued_total = job_duration_seconds = _NoOp()

# Configure logging
log_level = logging.DEBUG if config.enable_debug_logs else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Server start time for uptime tracking
SERVER_START_TIME = time.time()

# In-memory job storage (Phase 0 only - no persistence needed yet)
# job_id -> Job object
jobs: Dict[str, Job] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the FastAPI application."""
    # Startup
    logger.info("Starting Ambient Intelligence Node...")

    # Validate configuration
    is_valid, error = config.validate()
    if not is_valid:
        logger.error(f"Configuration error: {error}")
        sys.exit(1)

    # Initialize crypto (generate keys if not present)
    global crypto
    if config.node_private_key:
        crypto = NodeCrypto(private_key_b64=config.node_private_key)
        logger.info("Loaded existing keypair from configuration")
    else:
        crypto = NodeCrypto()
        logger.warning("No private key found in configuration!")
        logger.warning("Generated new keypair. Add these to your .env file:")
        logger.warning(f"NODE_PRIVATE_KEY={crypto.get_private_key()}")
        logger.warning(f"NODE_PUBLIC_KEY={crypto.get_public_key()}")

    logger.info(f"Node public key: {crypto.get_public_key()}")

    # Initialize Ollama client
    global ollama
    ollama = OllamaClient(
        host=config.ollama_host,
        model=config.ollama_model
    )

    # Initialize security components
    global rate_limiter, prompt_sanitizer, context_manager
    if config.enable_rate_limiting:
        rate_limiter = RateLimiter(
            max_requests_per_minute=config.rate_limit_per_client,
            max_global_per_minute=config.rate_limit_global
        )
        logger.info(f"Rate limiting enabled: {config.rate_limit_per_client}/min per client, {config.rate_limit_global}/min global")
    else:
        rate_limiter = None
        logger.warning("Rate limiting DISABLED - not recommended for production")

    if config.enable_prompt_sanitization:
        prompt_sanitizer = PromptSanitizer(
            max_length=config.max_prompt_length,
            enable_injection_detection=True
        )
        logger.info(f"Prompt sanitization enabled (max length: {config.max_prompt_length})")
    else:
        prompt_sanitizer = None
        logger.warning("Prompt sanitization DISABLED - security risk!")

    # Initialize context manager for conversation support
    context_manager = ContextManager(max_tokens=4096)
    logger.info("Context manager initialized (max tokens: 4096)")

    # Verify Ollama is available
    if not ollama.is_available():
        logger.error("Ollama is not available! Please start Ollama before running the node.")
        logger.error(f"Expected Ollama at: {config.ollama_host}")
        logger.error("Run: ollama serve")
        sys.exit(1)

    logger.info(f"Connected to Ollama at {config.ollama_host}")
    logger.info(f"Using model: {config.ollama_model}")
    logger.info(f"Node ID: {config.node_id}")
    logger.info(f"Listening on port: {config.node_port}")
    logger.info(f"Max concurrent jobs: {config.max_concurrent_jobs}")
    
    # Log security configuration
    logger.info("=== Security Configuration ===")
    logger.info(f"Rate limiting: {'ENABLED' if config.enable_rate_limiting else 'DISABLED'}")
    logger.info(f"Prompt sanitization: {'ENABLED' if config.enable_prompt_sanitization else 'DISABLED'}")
    logger.info(f"Proof-of-work: {'ENABLED' if config.enable_proof_of_work else 'DISABLED'}")
    logger.info(f"Client allowlist: {'ENABLED' if config.allowed_client_keys else 'DISABLED'}")
    logger.info(f"Max prompt length: {config.max_prompt_length}")
    logger.info("==============================")

    # Start heartbeat to coordinator if configured (Phase 2+)
    if config.coordinator_url:
        logger.info(f"Coordinator URL: {config.coordinator_url}")
        asyncio.create_task(send_heartbeat())
    else:
        logger.info("No coordinator configured - running in standalone mode")

    # Start job cleanup task
    logger.info(f"Starting job cleanup task (interval: {config.job_cleanup_interval_seconds}s, TTL: {config.job_ttl_seconds}s)")
    asyncio.create_task(cleanup_old_jobs())

    yield

    # Shutdown
    logger.info("Shutting down Ambient Intelligence Node...")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Ambient Intelligence Node",
    description="Privacy-first AI inference node",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 0: Allow all. Phase 1+: Restrict to known clients
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns the current health status of the node.
    """
    active_jobs = len([j for j in jobs.values() if j.status == "running"])
    uptime = time.time() - SERVER_START_TIME

    return HealthResponse(
        status="healthy",
        ollama_available=ollama.is_available(),
        active_jobs=active_jobs,
        uptime_seconds=uptime
    )


@app.get("/pubkey", response_model=PublicKeyResponse)
async def get_public_key():
    """
    Return the node's public key so clients can encrypt messages for us.

    This endpoint is called by clients before submitting jobs.
    """
    return PublicKeyResponse(public_key=crypto.get_public_key())


@app.post("/submit", response_model=SubmitJobResponse)
async def submit_job(request: SubmitJobRequest):
    """
    Accept an encrypted job for processing.

    The flow is:
    1. Validate rate limits and authentication
    2. Client encrypts prompt with our public key
    3. We decrypt it (plaintext exists only in this function's scope)
    4. We sanitize the prompt for security
    5. We pass it to Ollama
    6. We encrypt the response with client's public key
    7. We return the job ID for polling

    PRIVACY NOTE: Plaintext prompt and response only exist in memory
    during this function's execution. They are never logged or stored.
    
    SECURITY NOTE: Multiple layers of protection prevent abuse:
    - Rate limiting (per-client and global)
    - Prompt injection detection
    - Size limits
    - Optional proof-of-work
    - Optional client allowlisting
    """
    job_id = str(uuid.uuid4())

    # SECURITY CHECK 1: Rate limiting
    if rate_limiter and config.enable_rate_limiting:
        # Check if client is blocked by auth failures
        if rate_limiter.is_blocked_by_auth_failures(request.client_pubkey):
            logger.warning(f"Job {job_id} rejected: Client blocked due to auth failures")
            raise HTTPException(
                status_code=429,
                detail="Too many failed authentication attempts. Please try again later."
            )
        
        # Check rate limits
        allowed, wait_time, reason = rate_limiter.is_allowed(request.client_pubkey)
        if not allowed:
            logger.warning(f"Job {job_id} rejected: {reason}")
            rate_limit_hits_total.inc()
            prompt_rejected_total.inc()
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {wait_time} seconds. Reason: {reason}"
            )

    # SECURITY CHECK 2: Client allowlist (if configured)
    if config.allowed_client_keys and len(config.allowed_client_keys) > 0:
        if request.client_pubkey not in config.allowed_client_keys:
            logger.warning(f"Job {job_id} rejected: Client not in allowlist")
            if rate_limiter:
                rate_limiter.record_auth_failure(request.client_pubkey)
            prompt_rejected_total.inc()
            raise HTTPException(
                status_code=403,
                detail="Client public key not authorized"
            )

    # SECURITY CHECK 3: Proof-of-work (if enabled)
    if config.enable_proof_of_work:
        if not request.proof_of_work_nonce:
            # Generate challenge and require PoW
            challenge = rate_limiter.generate_pow_challenge(config.pow_difficulty)
            logger.info(f"Job {job_id} requires proof-of-work")
            pow_challenges_issued_total.inc()
            return SubmitJobResponse(
                job_id=job_id,
                estimated_wait_seconds=0,
                requires_proof_of_work=True,
                pow_challenge=challenge
            )
        
        # Verify proof-of-work
        # Note: In production, you'd need to store/verify the challenge was issued
        # For now, we'll just verify the format is correct
        if not rate_limiter.verify_pow(f"{config.pow_difficulty}:placeholder", request.proof_of_work_nonce):
            logger.warning(f"Job {job_id} rejected: Invalid proof-of-work")
            prompt_rejected_total.inc()
            raise HTTPException(
                status_code=400,
                detail="Invalid proof-of-work solution"
            )

    # Log that we received a job, but never log the encrypted content
    logger.info(f"Received job {job_id} from client")

    # Create job record
    job = Job(job_id=job_id, client_pubkey=request.client_pubkey)
    jobs[job_id] = job

    jobs_submitted_total.inc()

    # Process job asynchronously
    asyncio.create_task(process_job(job_id, request))

    return SubmitJobResponse(
        job_id=job_id,
        estimated_wait_seconds=0,  # Phase 0: Immediate processing
        requires_proof_of_work=False
    )


async def process_job(job_id: str, request: SubmitJobRequest):
    """
    Process a job asynchronously.

    This function is executed as a background task.
    Supports both single-prompt and conversation modes.
    """
    job = jobs[job_id]

    try:
        # Mark as running
        job.status = "running"
        jobs_running_gauge.inc()
        start_time = time.time()

        # Decrypt the prompt or conversation context
        # CRITICAL: plaintext only exists in this function
        # It is never stored, logged, or persisted anywhere
        plaintext_data = crypto.decrypt_prompt(
            request.encrypted_prompt,
            request.client_pubkey
        )

        logger.info(f"Job {job_id} decrypted successfully")

        # Handle conversation mode vs single prompt mode
        if request.conversation_mode:
            logger.info(f"Job {job_id} is in conversation mode")

            # Parse conversation JSON
            try:
                messages = context_manager.parse_conversation_json(plaintext_data)
            except ValueError as e:
                job.status = "failed"
                job.error_message = f"Invalid conversation format: {str(e)}"
                logger.warning(f"Job {job_id} rejected: {job.error_message}")
                prompt_rejected_total.inc()
                jobs_failed_total.inc()
                jobs_running_gauge.dec()
                return

            # Validate conversation structure
            is_valid, error_msg = context_manager.validate_conversation(messages)
            if not is_valid:
                job.status = "failed"
                job.error_message = f"Invalid conversation: {error_msg}"
                logger.warning(f"Job {job_id} rejected: {job.error_message}")
                prompt_rejected_total.inc()
                jobs_failed_total.inc()
                jobs_running_gauge.dec()
                return

            # Apply smart truncation
            max_tokens = request.max_context_tokens or 4096
            truncated_messages, token_count = context_manager.truncate_smart(
                messages,
                max_tokens=max_tokens
            )

            logger.info(
                f"Job {job_id} conversation: {len(messages)} messages, "
                f"{token_count} tokens (limit: {max_tokens})"
            )

            # SECURITY CHECK 4A: Validate each message content
            if prompt_sanitizer and config.enable_prompt_sanitization:
                for i, msg in enumerate(truncated_messages):
                    if msg.role == "user":  # Only validate user messages
                        is_valid, error_msg, warnings = prompt_sanitizer.validate_prompt(msg.content)

                        if not is_valid:
                            job.status = "failed"
                            job.error_message = f"Message {i} validation failed: {error_msg}"
                            logger.warning(f"Job {job_id} rejected: {job.error_message}")
                            prompt_rejected_total.inc()
                            jobs_failed_total.inc()
                            jobs_running_gauge.dec()
                            return

                        if warnings:
                            logger.info(f"Job {job_id} message {i} warnings: {', '.join(warnings)}")

            # Format for Ollama
            ollama_messages = context_manager.format_for_ollama(truncated_messages)

            logger.info(f"Job {job_id} sending conversation to Ollama")

            # Generate response from Ollama with conversation context
            plaintext_response = ollama.generate_chat(
                ollama_messages,
                timeout=config.job_timeout_seconds
            )

        else:
            # Single prompt mode (original behavior)
            plaintext_prompt = plaintext_data

            # SECURITY CHECK 4B: Prompt sanitization for single prompts
            if prompt_sanitizer and config.enable_prompt_sanitization:
                is_valid, error_msg, warnings = prompt_sanitizer.validate_prompt(plaintext_prompt)

                if not is_valid:
                    job.status = "failed"
                    job.error_message = f"Prompt validation failed: {error_msg}"
                    logger.warning(f"Job {job_id} rejected: {error_msg}")
                    prompt_rejected_total.inc()
                    jobs_failed_total.inc()
                    jobs_running_gauge.dec()
                    return

                if warnings:
                    logger.info(f"Job {job_id} warnings: {', '.join(warnings)}")

                # Log compute cost estimate
                cost = prompt_sanitizer.estimate_compute_cost(plaintext_prompt)
                logger.info(f"Job {job_id} estimated compute cost: {cost}")

            logger.info(f"Job {job_id} sending to Ollama")

            # Generate response from Ollama
            plaintext_response = ollama.generate(
                plaintext_prompt,
                timeout=config.job_timeout_seconds
            )

        if plaintext_response is None:
            job.status = "failed"
            job.error_message = "Ollama generation failed or timed out"
            logger.error(f"Job {job_id} failed: Ollama generation failed")
            jobs_failed_total.inc()
            jobs_running_gauge.dec()
            return

        logger.info(f"Job {job_id} generated response, encrypting")

        # Encrypt the response for the client
        encrypted_response = crypto.encrypt_response(
            plaintext_response,
            request.client_pubkey
        )

        # Store the encrypted response
        job.status = "complete"
        job.encrypted_response = encrypted_response
        job.completed_at = datetime.utcnow()
        duration = time.time() - start_time
        job_duration_seconds.observe(duration)
        jobs_completed_total.inc()
        jobs_running_gauge.dec()

        # At this point, all plaintext data goes out of scope
        # Python's garbage collector will reclaim this memory
        # The plaintext existed for only a few seconds

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        logger.error(f"Job {job_id} failed: {str(e)}")
        jobs_failed_total.inc()
        # Ensure gauge decremented if we marked running earlier
        if jobs_running_gauge:
            try:
                jobs_running_gauge.dec()
            except Exception:
                pass


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Poll for job completion.

    Clients will call this repeatedly until status is 'complete' or 'failed'.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    return JobStatusResponse(
        status=job.status,
        encrypted_response=job.encrypted_response,
        node_pubkey=crypto.get_public_key(),
        error_message=job.error_message
    )


@app.get("/metrics")
async def get_metrics():
    """
    Expose basic metrics for monitoring.

    These metrics contain NO user data, only operational statistics.
    """
    total_jobs = len(jobs)
    completed_jobs = len([j for j in jobs.values() if j.status == "complete"])
    failed_jobs = len([j for j in jobs.values() if j.status == "failed"])
    running_jobs = len([j for j in jobs.values() if j.status == "running"])
    pending_jobs = len([j for j in jobs.values() if j.status == "pending"])

    # Calculate average job duration for completed jobs
    avg_duration = 0
    if completed_jobs > 0:
        durations = []
        for job in jobs.values():
            if job.status == "complete" and job.completed_at and job.submitted_at:
                duration = (job.completed_at - job.submitted_at).total_seconds()
                durations.append(duration)
        if durations:
            avg_duration = sum(durations) / len(durations)

    return {
        "jobs": {
            "total": total_jobs,
            "completed": completed_jobs,
            "failed": failed_jobs,
            "running": running_jobs,
            "pending": pending_jobs,
            "success_rate": completed_jobs / total_jobs if total_jobs > 0 else 0,
            "average_duration_seconds": avg_duration
        },
        "system": {
            "ollama_available": ollama.is_available(),
            "uptime_seconds": time.time() - SERVER_START_TIME,
            "max_concurrent_jobs": config.max_concurrent_jobs,
            "job_timeout_seconds": config.job_timeout_seconds,
            "job_ttl_seconds": config.job_ttl_seconds
        },
        "security": {
            "rate_limiting_enabled": config.enable_rate_limiting,
            "rate_limit_per_client": config.rate_limit_per_client if config.enable_rate_limiting else None,
            "rate_limit_global": config.rate_limit_global if config.enable_rate_limiting else None,
            "prompt_sanitization_enabled": config.enable_prompt_sanitization,
            "max_prompt_length": config.max_prompt_length if config.enable_prompt_sanitization else None,
            "proof_of_work_enabled": config.enable_proof_of_work,
            "client_allowlist_enabled": len(config.allowed_client_keys) > 0,
            "allowed_clients_count": len(config.allowed_client_keys)
        },
        "prometheus_metrics_exposed": METRICS_ENABLED,
        "node_info": {
            "node_id": config.node_id,
            "model": config.ollama_model
        }
    }


@app.get("/prometheus")
async def prometheus_metrics():
    """Return Prometheus-formatted metrics for scraping."""
    if not METRICS_ENABLED:
        raise HTTPException(status_code=503, detail="Prometheus metrics not enabled (library missing)")
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


async def cleanup_old_jobs():
    """
    Periodically clean up old completed/failed jobs to prevent memory exhaustion.

    Removes jobs that have been completed or failed for longer than job_ttl_seconds.
    This prevents indefinite memory growth in the in-memory job storage.
    """
    while True:
        try:
            await asyncio.sleep(config.job_cleanup_interval_seconds)

            current_time = time.time()
            jobs_to_remove = []

            for job_id, job in jobs.items():
                # Only clean up completed or failed jobs
                if job.status in ["complete", "failed"]:
                    if job.completed_at:
                        # Calculate age in seconds
                        age_seconds = (datetime.utcnow() - job.completed_at).total_seconds()

                        if age_seconds > config.job_ttl_seconds:
                            jobs_to_remove.append(job_id)

            # Remove expired jobs
            if jobs_to_remove:
                for job_id in jobs_to_remove:
                    del jobs[job_id]
                logger.info(f"Cleaned up {len(jobs_to_remove)} expired jobs (TTL: {config.job_ttl_seconds}s)")

        except Exception as e:
            logger.error(f"Job cleanup error: {e}")


async def send_heartbeat():
    """
    Periodically announce this node to the coordinator (Phase 2+).

    This function runs as a background task if coordinator is configured.
    """
    import aiohttp

    if not config.coordinator_url:
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                # Calculate current load
                running_count = len([j for j in jobs.values() if j.status == "running"])
                current_load = running_count / config.max_concurrent_jobs

                heartbeat_data = {
                    "node_id": config.node_id,
                    "ip_address": get_public_ip(),
                    "port": config.node_port,
                    "public_key": crypto.get_public_key(),
                    "models": [config.ollama_model],
                    "max_concurrent": config.max_concurrent_jobs,
                    "current_load": current_load,
                    "version": "0.2.0"  # Phase 2 version
                }

                async with session.post(
                    f"{config.coordinator_url}/nodes/announce",
                    json=heartbeat_data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.debug("Heartbeat sent successfully")
                    else:
                        logger.warning(f"Heartbeat failed: {response.status}")

        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

        await asyncio.sleep(config.heartbeat_interval_seconds)


def get_public_ip() -> str:
    """
    Get the public IP address of this node.

    Tries multiple methods to detect the public IP:
    1. Environment variable PUBLIC_IP
    2. ifconfig.me service
    3. Fallback to localhost
    """
    # Method 1: Environment variable (for manual override)
    env_ip = os.getenv("PUBLIC_IP")
    if env_ip:
        return env_ip

    # Method 2: Try to detect public IP via external service
    try:
        import requests
        response = requests.get("https://ifconfig.me/ip", timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass

    # Fallback: Return localhost (for local testing)
    logger.warning("Could not detect public IP, using localhost")
    return "127.0.0.1"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.node_port,
        log_level="debug" if config.enable_debug_logs else "info"
    )
