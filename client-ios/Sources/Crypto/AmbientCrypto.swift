import Foundation
import Sodium

/// Handles NaCl/libsodium encryption for the Ambient Intelligence client.
///
/// Privacy guarantees:
/// - Ephemeral Curve25519 keypair (generated per session, never persisted)
/// - Forward secrecy: past sessions remain secure even if keys compromised
/// - Memory-only storage: keys cleared on app close
///
/// Crypto primitives (matching Python/Android clients):
/// - Key agreement: Curve25519
/// - Encryption: XSalsa20
/// - Authentication: Poly1305
@MainActor
class AmbientCrypto {
    private let sodium = Sodium()
    private var keyPair: Box.KeyPair?
    
    init() {
        // Generate ephemeral keypair
        keyPair = sodium.box.keyPair()
    }
    
    /// Get client's public key as base64 string.
    /// Sent to node with each request.
    func getPublicKeyB64() throws -> String {
        guard let keyPair = keyPair else {
            throw CryptoError.keypairNotInitialized
        }
        return keyPair.publicKey.base64EncodedString()
    }
    
    /// Encrypt plaintext for a specific node.
    ///
    /// - Parameters:
    ///   - plaintext: Message to encrypt
    ///   - nodePubKeyB64: Node's public key (base64)
    /// - Returns: Base64-encoded encrypted message
    func encryptForNode(plaintext: String, nodePubKeyB64: String) throws -> String {
        guard let keyPair = keyPair else {
            throw CryptoError.keypairNotInitialized
        }
        
        guard let plaintextData = plaintext.data(using: .utf8) else {
            throw CryptoError.invalidPlaintext
        }
        
        guard let nodePubKey = Data(base64Encoded: nodePubKeyB64) else {
            throw CryptoError.invalidPublicKey
        }
        
        // Encrypt with NaCl Box
        guard let encrypted = sodium.box.seal(
            message: Bytes(plaintextData),
            recipientPublicKey: Bytes(nodePubKey),
            senderSecretKey: keyPair.secretKey
        ) else {
            throw CryptoError.encryptionFailed
        }
        
        return Data(encrypted).base64EncodedString()
    }
    
    /// Decrypt message from node.
    ///
    /// - Parameters:
    ///   - encryptedB64: Base64-encoded encrypted message
    ///   - nodePubKeyB64: Node's public key (base64)
    /// - Returns: Decrypted plaintext
    func decryptFromNode(encryptedB64: String, nodePubKeyB64: String) throws -> String {
        guard let keyPair = keyPair else {
            throw CryptoError.keypairNotInitialized
        }
        
        guard let encryptedData = Data(base64Encoded: encryptedB64) else {
            throw CryptoError.invalidCiphertext
        }
        
        guard let nodePubKey = Data(base64Encoded: nodePubKeyB64) else {
            throw CryptoError.invalidPublicKey
        }
        
        // Decrypt with NaCl Box
        guard let decrypted = sodium.box.open(
            authenticatedCipherText: Bytes(encryptedData),
            senderPublicKey: Bytes(nodePubKey),
            recipientSecretKey: keyPair.secretKey
        ) else {
            throw CryptoError.decryptionFailed
        }
        
        guard let plaintext = String(data: Data(decrypted), encoding: .utf8) else {
            throw CryptoError.invalidPlaintext
        }
        
        return plaintext
    }
    
    /// Clear keypair from memory when done.
    /// Called automatically when object is deallocated.
    deinit {
        // Zero out key bytes
        if var keyPair = keyPair {
            keyPair.publicKey.withUnsafeMutableBytes { $0.initializeMemory(as: UInt8.self, repeating: 0) }
            keyPair.secretKey.withUnsafeMutableBytes { $0.initializeMemory(as: UInt8.self, repeating: 0) }
        }
        keyPair = nil
    }
}

enum CryptoError: LocalizedError {
    case keypairNotInitialized
    case invalidPlaintext
    case invalidPublicKey
    case invalidCiphertext
    case encryptionFailed
    case decryptionFailed
    
    var errorDescription: String? {
        switch self {
        case .keypairNotInitialized: return "Keypair not initialized"
        case .invalidPlaintext: return "Invalid plaintext"
        case .invalidPublicKey: return "Invalid public key"
        case .invalidCiphertext: return "Invalid ciphertext"
        case .encryptionFailed: return "Encryption failed"
        case .decryptionFailed: return "Decryption failed - wrong key or corrupted data"
        }
    }
}
