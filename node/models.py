"""
Data models for Ambient Intelligence node API.

These Pydantic models define the request/response schemas
for the node's HTTP endpoints.
"""

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator
import base64


class Message(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Message role: user, assistant, or system"
    )
    content: str = Field(
        ...,
        description="Message content"
    )


class SubmitJobRequest(BaseModel):
    """Request to submit an encrypted job for processing."""

    encrypted_prompt: str = Field(
        ...,
        description="Base64-encoded encrypted prompt or conversation context",
        max_length=100000
    )
    client_pubkey: str = Field(
        ...,
        description="Base64-encoded client public key"
    )
    conversation_mode: bool = Field(
        default=False,
        description="Whether this request includes conversation context"
    )
    max_context_tokens: Optional[int] = Field(
        None,
        description="Maximum tokens to use for context (for truncation)",
        ge=0,
        le=32000
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override",
        max_length=50
    )
    proof_of_work_nonce: Optional[str] = Field(
        None,
        description="Proof-of-work nonce (if required)",
        max_length=64
    )
    pow_challenge: Optional[str] = Field(
        None,
        description="Proof-of-work challenge from server (client must include when submitting nonce)",
        max_length=128
    )
    timestamp: Optional[int] = Field(
        None,
        description="Request timestamp (for replay attack prevention)"
    )

    @validator('encrypted_prompt')
    def validate_encrypted_prompt(cls, v):
        """Validate that encrypted_prompt is valid base64 and reasonable size."""
        try:
            decoded = base64.b64decode(v)
            if len(decoded) > 50000:  # 50KB max
                raise ValueError('Encrypted prompt too large (max 50KB)')
        except Exception as e:
            raise ValueError(f'Invalid base64 encoding: {str(e)}')
        return v

    @validator('client_pubkey')
    def validate_client_pubkey(cls, v):
        """Validate that client_pubkey is valid base64."""
        try:
            decoded = base64.b64decode(v)
            if len(decoded) != 32:  # NaCl public keys are 32 bytes
                raise ValueError('Invalid public key length')
        except Exception as e:
            raise ValueError(f'Invalid base64 encoding: {str(e)}')
        return v


class SubmitJobResponse(BaseModel):
    """Response after submitting a job."""

    job_id: str = Field(..., description="Unique job identifier")
    estimated_wait_seconds: int = Field(
        ...,
        description="Estimated time until completion"
    )
    requires_proof_of_work: bool = Field(
        default=False,
        description="Whether proof-of-work is required for this request"
    )
    pow_challenge: Optional[str] = Field(
        None,
        description="Proof-of-work challenge (if required)"
    )


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    status: str = Field(
        ...,
        description="Job status: pending, running, complete, or failed"
    )
    encrypted_response: Optional[str] = Field(
        None,
        description="Base64-encoded encrypted response (if complete)"
    )
    node_pubkey: str = Field(
        ...,
        description="Base64-encoded node public key"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error details (if failed)"
    )


class PublicKeyResponse(BaseModel):
    """Response containing node's public key."""

    public_key: str = Field(
        ...,
        description="Base64-encoded node public key"
    )


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: str = Field(..., description="Health status")
    ollama_available: bool = Field(..., description="Whether Ollama is reachable")
    active_jobs: int = Field(..., description="Number of currently running jobs")
    uptime_seconds: Optional[float] = Field(
        None,
        description="Server uptime in seconds"
    )


class NodeHeartbeat(BaseModel):
    """Heartbeat message sent to coordinator (Phase 2+)."""

    node_id: str
    ip_address: str
    port: int = 8000
    public_key: str
    models: list[str]
    max_concurrent: int = 1
    current_load: float = 0.0
    timestamp: Optional[int] = None
    signature: Optional[str] = None
    signature_pubkey: Optional[str] = None


class Job:
    """Internal job representation (not exposed via API)."""

    def __init__(self, job_id: str, client_pubkey: str):
        self.job_id = job_id
        self.client_pubkey = client_pubkey
        self.status = "pending"
        self.encrypted_response: Optional[str] = None
        self.error_message: Optional[str] = None
        self.submitted_at = datetime.utcnow()
        self.created_at = self.submitted_at
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert job to dictionary representation."""
        return {
            "job_id": self.job_id,
            "client_pubkey": self.client_pubkey,
            "status": self.status,
            "encrypted_response": self.encrypted_response,
            "error_message": self.error_message,
            "submitted_at": self.submitted_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
