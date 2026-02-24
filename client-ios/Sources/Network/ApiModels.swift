import Foundation

/// API models matching the Ambient Intelligence protocol.
///
/// See: protocol/SPECIFICATION.md for full protocol details

struct PublicKeyResponse: Codable {
    let publicKey: String
    
    enum CodingKeys: String, CodingKey {
        case publicKey = "public_key"
    }
}

struct SubmitJobRequest: Codable {
    let encryptedPrompt: String
    let clientPubkey: String
    
    enum CodingKeys: String, CodingKey {
        case encryptedPrompt = "encrypted_prompt"
        case clientPubkey = "client_pubkey"
    }
}

struct SubmitJobResponse: Codable {
    let jobId: String
    
    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
    }
}

struct JobStatusResponse: Codable {
    let status: String // "running", "complete", "failed"
    let encryptedResponse: String?
    let errorMessage: String?
    
    enum CodingKeys: String, CodingKey {
        case status
        case encryptedResponse = "encrypted_response"
        case errorMessage = "error_message"
    }
}

/// Coordinator endpoints for dynamic node discovery
struct CoordinatorNodesResponse: Codable {
    let nodes: [NodeInfo]
}

struct NodeInfo: Codable {
    let nodeId: String
    let address: String
    let publicKey: String
    let capabilities: [String]
    
    enum CodingKeys: String, CodingKey {
        case nodeId = "node_id"
        case address
        case publicKey = "public_key"
        case capabilities
    }
}
