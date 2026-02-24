package com.ambient.client.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * API models matching the Ambient Intelligence protocol.
 * 
 * See: protocol/SPECIFICATION.md for full protocol details
 */

@Serializable
data class PublicKeyResponse(
    @SerialName("public_key")
    val publicKey: String
)

@Serializable
data class SubmitJobRequest(
    @SerialName("encrypted_prompt")
    val encryptedPrompt: String,
    
    @SerialName("client_pubkey")
    val clientPubkey: String
)

@Serializable
data class SubmitJobResponse(
    @SerialName("job_id")
    val jobId: String
)

@Serializable
data class JobStatusResponse(
    val status: String, // "running", "complete", "failed"
    
    @SerialName("encrypted_response")
    val encryptedResponse: String? = null,
    
    @SerialName("error_message")
    val errorMessage: String? = null
)

/**
 * Coordinator endpoints for dynamic node discovery
 */
@Serializable
data class CoordinatorNodesResponse(
    val nodes: List<NodeInfo>
)

@Serializable
data class NodeInfo(
    @SerialName("node_id")
    val nodeId: String,
    
    val address: String,
    
    @SerialName("public_key")
    val publicKey: String,
    
    val capabilities: List<String> = emptyList()
)
