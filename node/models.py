"""
Data models for Ambient Intelligence node API.

These Pydantic models define the request/response schemas
for the node's HTTP endpoints.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
import base64


class SubmitJobRequest(BaseModel):
    """Request to submit an encrypted job for processing."""

    encrypted_prompt: str = Field(
        ...,
        description="Base64-encoded encrypted prompt",
        max_length=100000
    )
    client_pubkey: str = Field(
        ...,
        description="Base64-encoded client public key"
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override",
        max_length=50
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


class Job:
    """Internal job representation (not exposed via API)."""

    def __init__(self, job_id: str, client_pubkey: str):
        self.job_id = job_id
        self.client_pubkey = client_pubkey
        self.status = "pending"
        self.encrypted_response: Optional[str] = None
        self.error_message: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert job to dictionary representation."""
        return {
            "job_id": self.job_id,
            "client_pubkey": self.client_pubkey,
            "status": self.status,
            "encrypted_response": self.encrypted_response,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
