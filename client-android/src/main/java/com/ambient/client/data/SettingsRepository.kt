package com.ambient.client.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * Minimal persistent settings (node URL, voice consent).
 * 
 * Only stores necessary configuration, no tracking data.
 */
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class SettingsRepository(private val context: Context) {
    companion object {
        private val NODE_URL_KEY = stringPreferencesKey("node_url")
        private val VOICE_ENABLED_KEY = booleanPreferencesKey("voice_enabled")
        private val VOICE_CONSENT_KEY = booleanPreferencesKey("voice_consent_given")
        
        const val DEFAULT_NODE_URL = "http://localhost:8000"
    }

    val nodeUrl: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[NODE_URL_KEY] ?: DEFAULT_NODE_URL
    }

    val voiceEnabled: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[VOICE_ENABLED_KEY] ?: false
    }

    val voiceConsentGiven: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[VOICE_CONSENT_KEY] ?: false
    }

    suspend fun setNodeUrl(url: String) {
        context.dataStore.edit { prefs ->
            prefs[NODE_URL_KEY] = url.trim()
        }
    }

    suspend fun setVoiceEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[VOICE_ENABLED_KEY] = enabled
        }
    }

    suspend fun setVoiceConsent(given: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[VOICE_CONSENT_KEY] = given
        }
    }
}
