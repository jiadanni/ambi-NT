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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from crypto import NodeCrypto, generate_keypair
from ollama_client import OllamaClient
from config import Config
from models import (
    SubmitJobRequest,
    SubmitJobResponse,
    JobStatusResponse,
    PublicKeyResponse,
    HealthResponse,
    Job
)

# Initialize configuration
config = Config()

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

    # Start heartbeat to coordinator if configured (Phase 2+)
    if config.coordinator_url:
        logger.info(f"Coordinator URL: {config.coordinator_url}")
        asyncio.create_task(send_heartbeat())
    else:
        logger.info("No coordinator configured - running in standalone mode")

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
    1. Client encrypts prompt with our public key
    2. We decrypt it (plaintext exists only in this function's scope)
    3. We pass it to Ollama
    4. We encrypt the response with client's public key
    5. We return the job ID for polling

    PRIVACY NOTE: Plaintext prompt and response only exist in memory
    during this function's execution. They are never logged or stored.
    """
    job_id = str(uuid.uuid4())

    # Log that we received a job, but never log the encrypted content
    logger.info(f"Received job {job_id} from client")

    # Create job record
    job = Job(job_id=job_id, client_pubkey=request.client_pubkey)
    jobs[job_id] = job

    # Process job asynchronously
    asyncio.create_task(process_job(job_id, request))

    return SubmitJobResponse(
        job_id=job_id,
        estimated_wait_seconds=0  # Phase 0: Immediate processing
    )


async def process_job(job_id: str, request: SubmitJobRequest):
    """
    Process a job asynchronously.

    This function is executed as a background task.
    """
    job = jobs[job_id]

    try:
        # Mark as running
        job.status = "running"

        # Decrypt the prompt
        # CRITICAL: plaintext_prompt only exists in this function
        # It is never stored, logged, or persisted anywhere
        plaintext_prompt = crypto.decrypt_prompt(
            request.encrypted_prompt,
            request.client_pubkey
        )

        logger.info(f"Job {job_id} decrypted successfully, sending to Ollama")

        # Generate response from Ollama
        # This is also plaintext and equally sensitive
        plaintext_response = ollama.generate(
            plaintext_prompt,
            timeout=config.job_timeout_seconds
        )

        if plaintext_response is None:
            job.status = "failed"
            job.error_message = "Ollama generation failed or timed out"
            logger.error(f"Job {job_id} failed: Ollama generation failed")
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

        # At this point, plaintext_prompt and plaintext_response go out of scope
        # Python's garbage collector will reclaim this memory
        # The plaintext existed for only a few seconds

        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        logger.error(f"Job {job_id} failed: {str(e)}")


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

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "running_jobs": running_jobs,
        "success_rate": completed_jobs / total_jobs if total_jobs > 0 else 0,
        "ollama_available": ollama.is_available(),
        "uptime_seconds": time.time() - SERVER_START_TIME
    }


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
