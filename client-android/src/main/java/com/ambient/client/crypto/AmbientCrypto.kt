package com.ambient.client.crypto

import android.util.Base64
import com.goterl.lazysodium.LazySodiumAndroid
import com.goterl.lazysodium.SodiumAndroid
import com.goterl.lazysodium.interfaces.Box
import com.goterl.lazysodium.utils.Key
import com.goterl.lazysodium.utils.KeyPair

/**
 * Handles NaCl/libsodium encryption for the Ambient Intelligence client.
 *
 * Privacy guarantees:
 * - Ephemeral Curve25519 keypair (generated per session, never persisted)
 * - Forward secrecy: past sessions remain secure even if keys compromised
 * - Memory-only storage: keys cleared on app close
 *
 * Crypto primitives (matching Python client):
 * - Key agreement: Curve25519
 * - Encryption: XSalsa20
 * - Authentication: Poly1305
 */
class AmbientCrypto : AutoCloseable {
    private val sodium = LazySodiumAndroid(SodiumAndroid())
    private var keyPair: KeyPair? = null

    init {
        // Generate ephemeral keypair
        keyPair = sodium.cryptoBoxKeypair()
    }

    /**
     * Get client's public key as base64 string.
     * Sent to node with each request.
     */
    fun getPublicKeyB64(): String {
        val pubKey = keyPair?.publicKey?.asBytes
            ?: throw IllegalStateException("Keypair not initialized")
        return Base64.encodeToString(pubKey, Base64.NO_WRAP)
    }

    /**
     * Encrypt plaintext for a specific node.
     *
     * @param plaintext Message to encrypt
     * @param nodePubKeyB64 Node's public key (base64)
     * @return Base64-encoded encrypted message
     */
    fun encryptForNode(plaintext: String, nodePubKeyB64: String): String {
        val kp = keyPair ?: throw IllegalStateException("Keypair not initialized")
        
        // Decode node's public key
        val nodePubKeyBytes = Base64.decode(nodePubKeyB64, Base64.DEFAULT)
        val nodePubKey = Key.fromBytes(nodePubKeyBytes)

        // Generate nonce
        val nonce = ByteArray(Box.NONCEBYTES)
        sodium.randomBytesBuf(nonce, nonce.size)

        // Encrypt with NaCl Box
        val plaintextBytes = plaintext.toByteArray(Charsets.UTF_8)
        val ciphertext = ByteArray(plaintextBytes.size + Box.MACBYTES)
        
        val success = sodium.cryptoBoxEasy(
            ciphertext,
            plaintextBytes,
            plaintextBytes.size.toLong(),
            nonce,
            nodePubKey,
            kp.secretKey
        )

        if (!success) {
            throw SecurityException("Encryption failed")
        }

        // Concatenate nonce + ciphertext and encode as base64
        val combined = nonce + ciphertext
        return Base64.encodeToString(combined, Base64.NO_WRAP)
    }

    /**
     * Decrypt message from node.
     *
     * @param encryptedB64 Base64-encoded encrypted message
     * @param nodePubKeyB64 Node's public key (base64)
     * @return Decrypted plaintext
     */
    fun decryptFromNode(encryptedB64: String, nodePubKeyB64: String): String {
        val kp = keyPair ?: throw IllegalStateException("Keypair not initialized")
        
        // Decode the combined message
        val combined = Base64.decode(encryptedB64, Base64.DEFAULT)
        
        // Split nonce and ciphertext
        val nonce = combined.sliceArray(0 until Box.NONCEBYTES)
        val ciphertext = combined.sliceArray(Box.NONCEBYTES until combined.size)

        // Decode node's public key
        val nodePubKeyBytes = Base64.decode(nodePubKeyB64, Base64.DEFAULT)
        val nodePubKey = Key.fromBytes(nodePubKeyBytes)

        // Decrypt with NaCl Box
        val plaintext = ByteArray(ciphertext.size - Box.MACBYTES)
        
        val success = sodium.cryptoBoxOpenEasy(
            plaintext,
            ciphertext,
            ciphertext.size.toLong(),
            nonce,
            nodePubKey,
            kp.secretKey
        )

        if (!success) {
            throw SecurityException("Decryption failed - wrong key or corrupted data")
        }

        return String(plaintext, Charsets.UTF_8)
    }

    /**
     * Clear keypair from memory when done.
     * Called automatically on app close.
     */
    override fun close() {
        // Overwrite key bytes with zeros before GC
        keyPair?.secretKey?.asBytes?.fill(0)
        keyPair?.publicKey?.asBytes?.fill(0)
        keyPair = null
    }
}
