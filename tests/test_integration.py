import os
import time
import pytest
import asyncio
import json
import base64
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# Set required environment variables BEFORE imports that initialize config
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from node.server import app as node_app
from coordinator.server import app as coordinator_app
from node.crypto import NodeCrypto
from node.key_lifecycle import EphemeralKeyPair
from node.config import Config as NodeConfig
from coordinator.config import CoordinatorConfig

# Mock Ollama for node tests
@pytest.fixture
def mock_ollama():
    with patch("node.server.ollama") as mock:
        mock.is_available.return_value = True
        # Mock generate return value as a dict because node/server.py expects it
        mock.generate.return_value = {"response": "Mocked response from Ollama"}
        mock.generate_chat.return_value = {"message": {"content": "Mocked chat response"}}
        yield mock

@pytest.fixture
def node_client():
    return TestClient(node_app)

@pytest.fixture
def coordinator_client():
    return TestClient(coordinator_app)

@pytest.mark.asyncio
async def test_heartbeat_signing_verification():
    """Test that node signs heartbeats and coordinator verifies them."""
    # Initialize coordinator database
    from coordinator.server import database as coord_db
    coord_db.create_tables()
    
    # 1. Setup Node Crypto
    node_crypto = NodeCrypto()
    node_id = "test-node-1"
    
    # 2. Create heartbeat payload
    payload = {
        "node_id": node_id,
        "ip_address": "127.0.0.1",
        "port": 8000,
        "public_key": node_crypto.get_public_key(),
        "models": ["llama2"],
        "max_concurrent": 1,
        "current_load": 0.0,
        "version": "0.2.0",
        "timestamp": int(time.time())
    }
    
    # 3. Sign it
    signature = node_crypto.sign_heartbeat(payload)
    signature_pubkey = node_crypto.get_signing_public_key()
    
    # 4. Prepare request for coordinator
    heartbeat_data = dict(payload)
    heartbeat_data["signature"] = signature
    heartbeat_data["signature_pubkey"] = signature_pubkey
    
    # 5. Send to coordinator TestClient
    async with AsyncClient(transport=ASGITransport(app=coordinator_app), base_url="http://test") as client:
        response = await client.post("/nodes/announce", json=heartbeat_data)
        assert response.status_code == 200
        assert response.json()["node_id"] == node_id
            
    # Test 6: Invalid signature should fail
    heartbeat_data["signature"] = "invalid_signature"
    async with AsyncClient(transport=ASGITransport(app=coordinator_app), base_url="http://test") as client:
        response = await client.post("/nodes/announce", json=heartbeat_data)
        assert response.status_code == 403
        assert "Invalid signature" in response.json()["detail"]

@pytest.mark.asyncio
async def test_coordinator_resilience_failover():
    """Test that Node tries multiple coordinators if one fails."""
    node_config = NodeConfig()
    node_config.coordinator_urls = ["http://coord1:8000", "http://coord2:8000"]
    
    from node.coordinator_resilience import CoordinatorFallbackManager
    fallback_manager = CoordinatorFallbackManager(node_config.coordinator_urls)
    
    # Mock operations
    op = AsyncMock()
    
    # Scenario 1: First coord fails, second succeeds
    op.side_effect = [Exception("Coord 1 Down"), "Success from Coord 2"]
    
    result = await fallback_manager.execute_with_fallback(op)
    assert result == "Success from Coord 2"
    assert op.call_count == 2
    
    # Verify endpoint status
    assert fallback_manager.endpoints[0].is_healthy is False
    assert fallback_manager.endpoints[1].is_healthy is True

@pytest.mark.asyncio
async def test_end_to_end_encryption_flow(mock_ollama):
    """Test full encryption cycle from client to node and back."""
    async with AsyncClient(transport=ASGITransport(app=node_app), base_url="http://test") as client:
        # 1. Get Node Public Key
        response = await client.get("/pubkey")
        node_pubkey = response.json()["public_key"]
        
        # 2. Client generates ephemeral key and encrypts prompt
        with EphemeralKeyPair() as client_key:
            secret_prompt = "Hello, what is the meaning of life?"
            encrypted_prompt = client_key.encrypt(secret_prompt, node_pubkey)
            
            # 3. Submit Job
            submit_data = {
                "encrypted_prompt": encrypted_prompt,
                "client_pubkey": client_key.public_key_b64,
                "conversation_mode": False
            }
            submit_response = await client.post("/submit", json=submit_data)
            assert submit_response.status_code == 200
            job_id = submit_response.json()["job_id"]
            
            # 4. Wait for processing
            # In AsyncClient with ASGITransport, we need to allow the background task to run
            # because submit_job uses asyncio.create_task.
            
            success = False
            for _ in range(50): # increased timeout
                status_response = await client.get(f"/status/{job_id}", params={"client_pubkey": client_key.public_key_b64})
                data = status_response.json()
                if data["status"] == "complete":
                    success = True
                    break
                if data["status"] == "failed":
                    pytest.fail(f"Job failed: {data.get('error_message')}")
                await asyncio.sleep(0.1) # ASYNC sleep allows loop to run tasks
                
            assert success, "Job did not complete in time"
            encrypted_response = status_response.json()["encrypted_response"]
            
            # 5. Client decrypts response
            decrypted_response = client_key.decrypt(encrypted_response, node_pubkey)
            assert "Mocked response" in decrypted_response

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
