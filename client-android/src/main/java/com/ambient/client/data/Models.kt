package com.ambient.client.data

/**
 * Ephemeral conversation model.
 * 
 * Lives only in memory - never persisted.
 * Cleared when app closes.
 */
data class Message(
    val text: String,
    val isFromUser: Boolean,
    val timestamp: Long = System.currentTimeMillis()
)

data class Conversation(
    val id: String = java.util.UUID.randomUUID().toString(),
    val messages: List<Message> = emptyList(),
    val createdAt: Long = System.currentTimeMillis()
)
