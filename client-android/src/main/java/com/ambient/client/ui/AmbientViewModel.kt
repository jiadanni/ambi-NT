package com.ambient.client.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ambient.client.data.Conversation
import com.ambient.client.data.Message
import com.ambient.client.data.SettingsRepository
import com.ambient.client.network.AmbientClient
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Main view model for the Ambient client.
 * 
 * Manages ephemeral conversations (in-memory only).
 */
class AmbientViewModel(
    private val settingsRepository: SettingsRepository
) : ViewModel() {
    
    // Settings flows
    val nodeUrl = settingsRepository.nodeUrl.stateIn(
        viewModelScope,
        SharingStarted.Eagerly,
        SettingsRepository.DEFAULT_NODE_URL
    )
    
    val voiceEnabled = settingsRepository.voiceEnabled.stateIn(
        viewModelScope,
        SharingStarted.Eagerly,
        false
    )
    
    val voiceConsentGiven = settingsRepository.voiceConsent.stateIn(
        viewModelScope,
        SharingStarted.Eagerly,
        false
    )

    // Current conversation (ephemeral - cleared on app close)
    var currentConversation by mutableStateOf(Conversation())
        private set

    // UI state
    var isLoading by mutableStateOf(false)
        private set
    
    var errorMessage by mutableStateOf<String?>(null)
        private set

    /**
     * Submit a prompt to the network.
     */
    fun submitPrompt(prompt: String) {
        if (prompt.isBlank()) return
        
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            
            // Add user message immediately
            val userMessage = Message(text = prompt, isFromUser = true)
            currentConversation = currentConversation.copy(
                messages = currentConversation.messages + userMessage
            )
            
            try {
                // Create client and submit
                val client = AmbientClient(nodeUrl.value)
                val response = client.submitAndWait(prompt)
                client.close()
                
                // Add assistant response
                val assistantMessage = Message(text = response, isFromUser = false)
                currentConversation = currentConversation.copy(
                    messages = currentConversation.messages + assistantMessage
                )
                
            } catch (e: Exception) {
                errorMessage = e.message ?: "Unknown error"
            } finally {
                isLoading = false
            }
        }
    }

    /**
     * Start a new conversation (clears current messages).
     */
    fun newConversation() {
        currentConversation = Conversation()
        errorMessage = null
    }

    /**
     * Clear error message.
     */
    fun clearError() {
        errorMessage = null
    }
    
    /**
     * Update settings.
     */
    fun updateNodeUrl(url: String) {
        viewModelScope.launch {
            settingsRepository.setNodeUrl(url)
        }
    }
    
    fun updateVoiceEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.setVoiceEnabled(enabled)
        }
    }
    
    fun updateVoiceConsent(given: Boolean) {
        viewModelScope.launch {
            settingsRepository.setVoiceConsent(given)
        }
    }
}
