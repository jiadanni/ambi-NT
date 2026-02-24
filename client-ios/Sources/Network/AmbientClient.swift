import Foundation

/// HTTP client for the Ambient Intelligence network.
///
/// Implements the protocol flow:
/// 1. Get node public key (GET /pubkey)
/// 2. Encrypt prompt with node's key
/// 3. Submit job (POST /submit)
/// 4. Poll for completion (GET /status/{job_id})
/// 5. Decrypt response
///
/// Privacy: All prompts encrypted before leaving device.
@MainActor
class AmbientClient {
    private let nodeUrl: String
    private let crypto: AmbientCrypto
    private let session: URLSession
    
    init(nodeUrl: String) {
        self.nodeUrl = nodeUrl
        self.crypto = AmbientCrypto()
        
        // Configure session with no caching for privacy
        let config = URLSessionConfiguration.default
        config.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        config.urlCache = nil
        self.session = URLSession(configuration: config)
    }
    
    /// Fetch node's public key for encryption.
    private func getNodePublicKey() async throws -> String {
        guard let url = URL(string: "\(nodeUrl)/pubkey") else {
            throw NetworkError.invalidURL
        }
        
        let (data, response) = try await session.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NetworkError.httpError((response as? HTTPURLResponse)?.statusCode ?? 0)
        }
        
        let decoded = try JSONDecoder().decode(PublicKeyResponse.self, from: data)
        return decoded.publicKey
    }
    
    /// Submit encrypted job to node.
    private func submitJob(encryptedPrompt: String) async throws -> String {
        guard let url = URL(string: "\(nodeUrl)/submit") else {
            throw NetworkError.invalidURL
        }
        
        let requestBody = SubmitJobRequest(
            encryptedPrompt: encryptedPrompt,
            clientPubkey: try crypto.getPublicKeyB64()
        )
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(requestBody)
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NetworkError.httpError((response as? HTTPURLResponse)?.statusCode ?? 0)
        }
        
        let decoded = try JSONDecoder().decode(SubmitJobResponse.self, from: data)
        return decoded.jobId
    }
    
    /// Poll job status until complete.
    private func pollJobStatus(
        jobId: String,
        nodePubKey: String,
        maxWaitSeconds: Int = 300,
        pollIntervalSeconds: TimeInterval = 2.0
    ) async throws -> String {
        let startTime = Date()
        let maxWait = TimeInterval(maxWaitSeconds)
        
        while Date().timeIntervalSince(startTime) < maxWait {
            guard let url = URL(string: "\(nodeUrl)/status/\(jobId)") else {
                throw NetworkError.invalidURL
            }
            
            let (data, response) = try await session.data(from: url)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                throw NetworkError.httpError((response as? HTTPURLResponse)?.statusCode ?? 0)
            }
            
            let status = try JSONDecoder().decode(JobStatusResponse.self, from: data)
            
            switch status.status {
            case "complete":
                guard let encryptedResponse = status.encryptedResponse else {
                    throw NetworkError.noResponse
                }
                
                // Decrypt and return
                return try crypto.decryptFromNode(
                    encryptedB64: encryptedResponse,
                    nodePubKeyB64: nodePubKey
                )
                
            case "failed":
                throw NetworkError.jobFailed(status.errorMessage ?? "Unknown error")
                
            case "running":
                // Continue polling
                try await Task.sleep(nanoseconds: UInt64(pollIntervalSeconds * 1_000_000_000))
                
            default:
                throw NetworkError.unknownStatus(status.status)
            }
        }
        
        throw NetworkError.timeout
    }
    
    /// Submit prompt and wait for response.
    ///
    /// - Parameter prompt: User's plaintext prompt
    /// - Returns: Decrypted response from AI
    func submitAndWait(prompt: String) async throws -> String {
        // 1. Get node's public key
        let nodePubKey = try await getNodePublicKey()
        
        // 2. Encrypt prompt
        let encryptedPrompt = try crypto.encryptForNode(
            plaintext: prompt,
            nodePubKeyB64: nodePubKey
        )
        
        // 3. Submit job
        let jobId = try await submitJob(encryptedPrompt: encryptedPrompt)
        
        // 4. Poll until complete and decrypt
        return try await pollJobStatus(jobId: jobId, nodePubKey: nodePubKey)
    }
}

enum NetworkError: LocalizedError {
    case invalidURL
    case httpError(Int)
    case noResponse
    case jobFailed(String)
    case unknownStatus(String)
    case timeout
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .httpError(let code): return "HTTP error: \(code)"
        case .noResponse: return "Job complete but no response"
        case .jobFailed(let message): return "Job failed: \(message)"
        case .unknownStatus(let status): return "Unknown job status: \(status)"
        case .timeout: return "Job timed out"
        }
    }
}
