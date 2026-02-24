package com.ambient.client.network

import com.ambient.client.crypto.AmbientCrypto
import kotlinx.coroutines.delay
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * HTTP client for the Ambient Intelligence network.
 *
 * Implements the protocol flow:
 * 1. Get node public key (GET /pubkey)
 * 2. Encrypt prompt with node's key
 * 3. Submit job (POST /submit)
 * 4. Poll for completion (GET /status/{job_id})
 * 5. Decrypt response
 *
 * Privacy: All prompts encrypted before leaving device.
 */
class AmbientClient(private val nodeUrl: String) : AutoCloseable {
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        // Disable caching for privacy
        .cache(null)
        .build()

    private val crypto = AmbientCrypto()
    
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    /**
     * Fetch node's public key for encryption.
     */
    private suspend fun getNodePublicKey(): String {
        val request = Request.Builder()
            .url("$nodeUrl/pubkey")
            .get()
            .build()

        return httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IOException("Failed to get node public key: HTTP ${response.code}")
            }
            
            val body = response.body?.string()
                ?: throw IOException("Empty response from node")
            
            val parsed = json.decodeFromString<PublicKeyResponse>(body)
            parsed.publicKey
        }
    }

    /**
     * Submit encrypted job to node.
     */
    private suspend fun submitJob(encryptedPrompt: String): String {
        val requestBody = SubmitJobRequest(
            encryptedPrompt = encryptedPrompt,
            clientPubkey = crypto.getPublicKeyB64()
        )
        
        val jsonBody = json.encodeToString(requestBody)
        val mediaType = "application/json; charset=utf-8".toMediaType()
        
        val request = Request.Builder()
            .url("$nodeUrl/submit")
            .post(jsonBody.toRequestBody(mediaType))
            .build()

        return httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IOException("Failed to submit job: HTTP ${response.code}")
            }
            
            val body = response.body?.string()
                ?: throw IOException("Empty response from node")
            
            val parsed = json.decodeFromString<SubmitJobResponse>(body)
            parsed.jobId
        }
    }

    /**
     * Poll job status until complete.
     */
    private suspend fun pollJobStatus(
        jobId: String,
        nodePubKey: String,
        maxWaitSeconds: Int = 300,
        pollIntervalMs: Long = 2000
    ): String {
        val startTime = System.currentTimeMillis()
        val maxWaitMs = maxWaitSeconds * 1000L

        while (System.currentTimeMillis() - startTime < maxWaitMs) {
            val request = Request.Builder()
                .url("$nodeUrl/status/$jobId")
                .get()
                .build()

            httpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("Failed to get job status: HTTP ${response.code}")
                }
                
                val body = response.body?.string()
                    ?: throw IOException("Empty response from node")
                
                val status = json.decodeFromString<JobStatusResponse>(body)
                
                when (status.status) {
                    "complete" -> {
                        val encryptedResponse = status.encryptedResponse
                            ?: throw IOException("Job complete but no response")
                        
                        // Decrypt and return
                        return crypto.decryptFromNode(encryptedResponse, nodePubKey)
                    }
                    
                    "failed" -> {
                        throw IOException("Job failed: ${status.errorMessage ?: "Unknown error"}")
                    }
                    
                    "running" -> {
                        // Continue polling
                        delay(pollIntervalMs)
                    }
                    
                    else -> {
                        throw IOException("Unknown job status: ${status.status}")
                    }
                }
            }
        }

        throw IOException("Job timed out after $maxWaitSeconds seconds")
    }

    /**
     * Submit prompt and wait for response.
     *
     * @param prompt User's plaintext prompt
     * @return Decrypted response from AI
     */
    suspend fun submitAndWait(prompt: String): String {
        // 1. Get node's public key
        val nodePubKey = getNodePublicKey()
        
        // 2. Encrypt prompt
        val encryptedPrompt = crypto.encryptForNode(prompt, nodePubKey)
        
        // 3. Submit job
        val jobId = submitJob(encryptedPrompt)
        
        // 4. Poll until complete and decrypt
        return pollJobStatus(jobId, nodePubKey)
    }

    override fun close() {
        crypto.close()
        // OkHttp client cleanup
        httpClient.dispatcher.executorService.shutdown()
        httpClient.connectionPool.evictAll()
    }
}
