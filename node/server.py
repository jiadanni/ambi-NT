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
import base64
import struct
import json
from datetime import datetime
from typing import Dict, Optional, List
from contextlib import asynccontextmanager, nullcontext

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

from utils.telemetry import setup_telemetry
from node.crypto import NodeCrypto, generate_keypair
import nacl.signing
import nacl.encoding
try:
    from node.ollama_client import OllamaClient
except Exception:
    try:
        from ollama_client import OllamaClient
    except Exception:
        OllamaClient = None
# Module-level placeholders so tests can patch `node.server.ollama` and `crypto`
ollama = None
crypto = None
from node.config import Config
from node.rate_limiter import RateLimiter
from node.prompt_sanitizer import PromptSanitizer
from node.context_manager import ContextManager
from node.session_manager import SessionManager
from node.key_lifecycle import KeyRotationManager
from node.coordinator_resilience import CoordinatorFallbackManager
from node.models import (
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
        def dec(self, *a, **k):
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

# Module-level placeholders for components initialized during lifespan
rate_limiter = None
prompt_sanitizer = None
context_manager = None
session_manager = None
key_rotation_manager = None
coordinator_fallback = None
job_semaphore = None

# Background task tracking for proper cleanup
background_tasks = set()


def create_background_task(coro, name: str):
    """
    Create a tracked background task with proper error handling.

    Args:
        coro: Coroutine to run
        name: Descriptive name for the task
    """
    async def wrapped():
        try:
            await coro
        except asyncio.CancelledError:
            logger.info(f"Background task '{name}' cancelled")
            raise
        except Exception as e:
            logger.error(f"Background task '{name}' failed: {e}", exc_info=True)

    task = asyncio.create_task(wrapped())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


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
    crypto = NodeCrypto(
        private_key_b64=config.node_private_key,
        signing_private_key_b64=config.node_signing_private_key
    )
    
    if not config.node_private_key:
        logger.warning("No private key found in configuration!")
        logger.warning("Generated new keypair. Add these to your .env file:")
        logger.warning(f"NODE_PRIVATE_KEY={crypto.get_private_key()}")
        logger.warning(f"NODE_PUBLIC_KEY={crypto.get_public_key()}")

    # Log only first 16 chars of public key for privacy
    pubkey = crypto.get_public_key()
    logger.info(f"Node public key: {pubkey[:16]}...{pubkey[-8:]}")

    # Initialize signing info from crypto
    if not config.node_signing_private_key:
        logger.warning("No signing key found in configuration!")
        logger.warning("Generated new signing keypair. Add these to your .env file:")
        logger.warning(f"NODE_SIGNING_PRIVATE_KEY={crypto.get_signing_private_key()}")
        logger.warning(f"NODE_SIGNING_PUBLIC_KEY={crypto.get_signing_public_key()}")

    signing_pubkey = crypto.get_signing_public_key()
    logger.info(
        "Node signing public key: %s...%s",
        signing_pubkey[:16],
        signing_pubkey[-8:]
    )

    # Initialize job semaphore to enforce max concurrency
    global job_semaphore
    job_semaphore = asyncio.Semaphore(config.max_concurrent_jobs)

    # Initialize Ollama client if available. If `OllamaClient` is not present
    # we assume tests or runtime will patch `node.server.ollama` as needed.
    global ollama
    if OllamaClient is not None:
        try:
            ollama = OllamaClient(
                host=config.ollama_host,
                model=config.ollama_model
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OllamaClient: {e}")
            ollama = None
    else:
        # Keep module-level `ollama` (tests may patch this before startup)
        if ollama is None:
            logger.warning("Ollama client not available - running in mock/test mode")

    # Initialize security components
    global rate_limiter, prompt_sanitizer, context_manager, session_manager, key_rotation_manager
    if config.enable_rate_limiting:
        rate_limiter = RateLimiter(
            max_requests_per_minute=config.rate_limit_per_client,
            max_global_per_minute=config.rate_limit_global,
            redis_url=config.redis_url
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

    # Initialize session manager for multi-turn conversations
    session_manager = SessionManager(
        default_ttl=3600,
        cleanup_interval=300,
        max_sessions=1000
    )
    logger.info("Session manager initialized (TTL: 1 hour)")

    # Initialize key rotation manager
    key_rotation_manager = KeyRotationManager(
        rotation_interval=24 * 3600,
        grace_period=3600
    )
    key_rotation_manager.initialize(private_key_b64=config.node_private_key)
    logger.info(f"Key rotation manager initialized (interval: 24 hours)")

    # Verify Ollama is available if initialized
    if ollama is not None:
        try:
            if not ollama.is_available():
                logger.error("Ollama is not available! Please start Ollama before running the node.")
                logger.error(f"Expected Ollama at: {config.ollama_host}")
                logger.error("Run: ollama serve")
                sys.exit(1)
        except Exception:
            logger.warning("Ollama availability check raised an exception - continuing in test/mock mode")

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
    global coordinator_fallback
    if config.coordinator_urls:
        logger.info(f"Coordinator URLs: {', '.join(config.coordinator_urls)}")
        coordinator_fallback = CoordinatorFallbackManager(config.coordinator_urls)
        create_background_task(send_heartbeat(), "heartbeat")
    else:
        logger.info("No coordinator configured - running in standalone mode")

    # Start job cleanup task
    logger.info(f"Starting job cleanup task (interval: {config.job_cleanup_interval_seconds}s, TTL: {config.job_ttl_seconds}s)")
    create_background_task(cleanup_old_jobs(), "job_cleanup")

    # Start session cleanup task
    logger.info("Starting session cleanup task")
    create_background_task(cleanup_expired_sessions(), "session_cleanup")

    # Start key rotation task
    logger.info("Starting key rotation monitoring task")
    create_background_task(monitor_key_rotation(), "key_rotation")

    yield

    # Shutdown
    logger.info("Shutting down Ambient Intelligence Node...")

    # Cancel all background tasks
    logger.info(f"Cancelling {len(background_tasks)} background tasks...")
    for task in background_tasks:
        task.cancel()

    # Wait for tasks to complete cancellation
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

    logger.info("All background tasks cancelled")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Ambient Intelligence Node",
    description="Privacy-first AI inference node with end-to-end encryption",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc alternative UI
    openapi_url="/openapi.json"  # OpenAPI schema
)

# Setup Tracing
tracer = setup_telemetry("ambi-node")
if tracer:
    # Instrument incoming FastAPI requests
    FastAPIInstrumentor.instrument_app(app)
    # Instrument outgoing aiohttp calls
    AioHttpClientInstrumentor().instrument()
    logger.info("OpenTelemetry tracing enabled")

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

    ollama_available = False
    try:
        if ollama is not None:
            ollama_available = await asyncio.to_thread(ollama.is_available)
    except Exception:
        ollama_available = False

    return HealthResponse(
        status="healthy",
        ollama_available=ollama_available,
        active_jobs=active_jobs,
        uptime_seconds=uptime
    )


@app.get("/pubkey", response_model=PublicKeyResponse)
async def get_public_key():
    """
    Return the node's public key so clients can encrypt messages for us.

    This endpoint is called by clients before submitting jobs.
    """
    global crypto
    if crypto is None:
        # Lazily initialize a temporary crypto instance for tests or minimal runs
        crypto = NodeCrypto()
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
    ctx = tracer.start_as_current_span("process_job_submission") if tracer else nullcontext()

    with ctx as span:
        if span:
             span.set_attribute("client_id", request.client_pubkey[:8])

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
        if config.enable_proof_of_work and rate_limiter:
            if not request.proof_of_work_nonce or not request.pow_challenge:
                # Generate challenge and require PoW
                challenge = rate_limiter.generate_pow_challenge(config.pow_difficulty)
                logger.info(f"Job {job_id} requires proof-of-work (difficulty: {config.pow_difficulty})")
                pow_challenges_issued_total.inc()
                return SubmitJobResponse(
                    job_id=job_id,
                    estimated_wait_seconds=0,
                    requires_proof_of_work=True,
                    pow_challenge=challenge
                )

            # Verify proof-of-work with the challenge provided by client
            if not rate_limiter.verify_pow(request.pow_challenge, request.proof_of_work_nonce):
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

        # Process job asynchronously with concurrency limits
        asyncio.create_task(process_job_with_semaphore(job_id, request))

        return SubmitJobResponse(
            job_id=job_id,
            estimated_wait_seconds=0,  # Phase 0: Immediate processing
            requires_proof_of_work=False
        )


async def validate_audio_request(encrypted_audio: str) -> tuple[bool, str]:
    """
    Validate audio request without killing UX.
    
    Performs lightweight validation on encrypted audio to prevent abuse
    without requiring full decryption first.
    
    Args:
        encrypted_audio: Base64 encoded encrypted audio data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Decode base64 to get size estimate
        audio_bytes = base64.b64decode(encrypted_audio)
        
        # Estimate audio duration based on size
        # Typical audio: 16kHz, 16-bit = 32KB/sec
        # Adding overhead for encryption (typically 1.3-1.5x)
        estimated_duration = len(audio_bytes) / (32 * 1024 * 1.3)
        
        if estimated_duration > config.max_audio_length_seconds:
            return False, f"Audio too long (estimated {estimated_duration:.1f}s, max {config.max_audio_length_seconds}s)"
        
        # Size sanity check (prevent huge uploads)
        max_size_bytes = config.max_audio_length_seconds * 64 * 1024  # Conservative estimate
        if len(audio_bytes) > max_size_bytes:
            return False, f"Audio file too large ({len(audio_bytes)} bytes, max {max_size_bytes})"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"Audio validation error: {e}")
        return False, "Invalid audio encoding"


async def validate_transcription(text: str) -> tuple[bool, str]:
    """
    Validate transcription length to prevent abuse.
    
    Args:
        text: Transcribed text
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Rough token estimate: 1 token ≈ 4 characters
    estimated_tokens = len(text) // 4
    
    if estimated_tokens > config.max_transcription_tokens:
        return False, f"Transcription too long ({estimated_tokens} tokens, max {config.max_transcription_tokens})"
    
    return True, ""


async def _run_ollama_generate(prompt: str, timeout: int) -> Optional[str]:
    """Run blocking Ollama generation in a worker thread."""
    if ollama is None:
        return None
    try:
        response = await asyncio.to_thread(ollama.generate, model=config.ollama_model, prompt=prompt)
        return response.get('response', '') if isinstance(response, dict) else str(response)
    except Exception as e:
        logger.error(f"Ollama generate error: {e}")
        return None


async def _run_ollama_chat(messages: List[dict], timeout: int) -> Optional[str]:
    """Run blocking Ollama chat generation in a worker thread."""
    if ollama is None:
        return None
    try:
        response = await asyncio.to_thread(ollama.chat, model=config.ollama_model, messages=messages)
        if isinstance(response, dict):
            return response.get('message', {}).get('content', '')
        return str(response)
    except Exception as e:
        logger.error(f"Ollama chat error: {e}")
        return None


async def process_job_with_semaphore(job_id: str, request: SubmitJobRequest):
    """Run job processing with concurrency limits."""
    if job_semaphore is None:
        await process_job(job_id, request)
        return

    async with job_semaphore:
        await process_job(job_id, request)


async def process_job(job_id: str, request: SubmitJobRequest):
    """
    Process a job asynchronously.

    This function is executed as a background task.
    Supports both single-prompt and conversation modes.
    """
    job = jobs[job_id]

    try:
        def mark_failed(message: str):
            job.status = "failed"
            job.error_message = message
            job.completed_at = datetime.utcnow()
            jobs_failed_total.inc()
            try:
                jobs_running_gauge.dec()
            except Exception:
                pass

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
                error_msg = f"Invalid conversation format: {str(e)}"
                logger.warning(f"Job {job_id} rejected: {error_msg}")
                prompt_rejected_total.inc()
                mark_failed(error_msg)
                return

            # Validate conversation structure
            is_valid, error_msg = context_manager.validate_conversation(messages)
            if not is_valid:
                error_msg = f"Invalid conversation: {error_msg}"
                logger.warning(f"Job {job_id} rejected: {error_msg}")
                prompt_rejected_total.inc()
                mark_failed(error_msg)
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
                            error_msg = f"Message {i} validation failed: {error_msg}"
                            logger.warning(f"Job {job_id} rejected: {error_msg}")
                            prompt_rejected_total.inc()
                            mark_failed(error_msg)
                            return

                        if warnings:
                            logger.info(f"Job {job_id} message {i} warnings: {', '.join(warnings)}")

            # Format for Ollama
            ollama_messages = context_manager.format_for_ollama(truncated_messages)

            logger.info(f"Job {job_id} sending conversation to Ollama")

            # Generate response from Ollama with conversation context
            plaintext_response = await _run_ollama_chat(
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
                    error_msg = f"Prompt validation failed: {error_msg}"
                    logger.warning(f"Job {job_id} rejected: {error_msg}")
                    prompt_rejected_total.inc()
                    mark_failed(error_msg)
                    return

                if warnings:
                    logger.info(f"Job {job_id} warnings: {', '.join(warnings)}")

                # Log compute cost estimate
                cost = prompt_sanitizer.estimate_compute_cost(plaintext_prompt)
                logger.info(f"Job {job_id} estimated compute cost: {cost}")

            logger.info(f"Job {job_id} sending to Ollama")

            # Generate response from Ollama
            plaintext_response = await _run_ollama_generate(
                plaintext_prompt,
                timeout=config.job_timeout_seconds
            )

        if plaintext_response is None:
            error_msg = "Ollama generation failed or timed out"
            logger.error(f"Job {job_id} failed: Ollama generation failed")
            mark_failed(error_msg)
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
        logger.error(f"Job {job_id} failed: {str(e)}")
        if job.status != "failed":
            mark_failed(str(e))


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, client_pubkey: str = None):
    """
    Poll for job completion.

    Requires client_pubkey query parameter for authentication.
    Only the client that submitted the job can retrieve its status.

    Args:
        job_id: Job identifier
        client_pubkey: Client's public key (must match the key used to submit job)

    Clients will call this repeatedly until status is 'complete' or 'failed'.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # SECURITY: Verify client owns this job
    if client_pubkey:
        if job.client_pubkey != client_pubkey:
            logger.warning(f"Unauthorized status request for job {job_id}")
            raise HTTPException(
                status_code=403,
                detail="Unauthorized: client public key does not match job owner"
            )
    else:
        # If no client_pubkey provided, reject (except for testing/backwards compat)
        # In production, this should always require authentication
        if not config.enable_debug_logs:
            raise HTTPException(
                status_code=400,
                detail="Missing client_pubkey parameter"
            )

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
            submitted_at = getattr(job, "submitted_at", None) or getattr(job, "created_at", None)
            if job.status == "complete" and job.completed_at and submitted_at:
                duration = (job.completed_at - submitted_at).total_seconds()
                durations.append(duration)
        if durations:
            avg_duration = sum(durations) / len(durations)

    ollama_available = False
    try:
        if ollama is not None:
            ollama_available = await asyncio.to_thread(ollama.is_available)
    except Exception:
        ollama_available = False

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
            "ollama_available": ollama_available,
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


async def cleanup_expired_sessions():
    """
    Periodically clean up expired sessions to prevent memory leaks.

    Removes sessions that have exceeded their TTL.
    """
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes

            if session_manager:
                cleaned = session_manager.cleanup_expired()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} expired sessions")

        except Exception as e:
            logger.error(f"Session cleanup error: {e}")


async def monitor_key_rotation():
    """
    Monitor and perform key rotation when needed.

    Checks periodically if keys need rotation and performs the rotation,
    updating the coordinator with the new public key.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # Check every hour

            if key_rotation_manager and key_rotation_manager.should_rotate():
                logger.info("Key rotation needed - rotating keys...")

                try:
                    new_key = key_rotation_manager.rotate()
                    logger.info(f"Key rotation complete - new public key: {new_key[:16]}...")

                    # Update coordinators with new public key if configured
                    if coordinator_fallback:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            update_data = {
                                "node_id": config.node_id,
                                "public_key": new_key
                            }
                            
                            async def do_key_update(coordinator_url):
                                async with session.post(
                                    f"{coordinator_url}/nodes/update_key",
                                    json=update_data,
                                    timeout=aiohttp.ClientTimeout(total=10)
                                ) as response:
                                    if response.status == 200:
                                        logger.info(f"Coordinator {coordinator_url} updated with new public key")
                                        return True
                                    else:
                                        logger.warning(f"Failed to update coordinator {coordinator_url} with new key: {response.status}")
                                        raise Exception(f"Status {response.status}")

                            try:
                                await coordinator_fallback.execute_with_fallback(do_key_update)
                            except Exception as e:
                                logger.error(f"Key update failed for all coordinators: {e}")

                except Exception as e:
                    logger.error(f"Key rotation failed: {e}")

        except Exception as e:
            logger.error(f"Key rotation monitoring error: {e}")


def _canonicalize_heartbeat(payload: dict) -> str:
    """Create a canonical JSON string for heartbeat signing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


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

                ip_address = await asyncio.to_thread(get_public_ip)
                heartbeat_payload = {
                    "node_id": config.node_id,
                    "ip_address": ip_address,
                    "port": config.node_port,
                    "public_key": crypto.get_public_key(),
                    "models": [config.ollama_model],
                    "max_concurrent": config.max_concurrent_jobs,
                    "current_load": current_load,
                    "version": "0.2.0",  # Phase 2 version
                    "timestamp": int(time.time())
                }
                heartbeat_data = dict(heartbeat_payload)
                heartbeat_data["signature"] = crypto.sign_heartbeat(heartbeat_payload)
                heartbeat_data["signature_pubkey"] = crypto.get_signing_public_key()

                # Heartbeat operation for fallback manager
                async def do_heartbeat(coordinator_url):
                    async with session.post(
                        f"{coordinator_url}/nodes/announce",
                        json=heartbeat_data,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            logger.debug(f"Heartbeat sent successfully to {coordinator_url}")
                            return True
                        else:
                            logger.warning(f"Heartbeat failed for {coordinator_url}: {response.status}")
                            raise Exception(f"Status {response.status}")

                if coordinator_fallback:
                    try:
                        await coordinator_fallback.execute_with_fallback(do_heartbeat)
                    except Exception as e:
                        logger.error(f"Heartbeat failed for all coordinators: {e}")
                else:
                    # Standalone mode fallback (though shouldn't be here)
                    pass

        except Exception as e:
            logger.error(f"Heartbeat task error: {e}")

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
