package com.ambient.client

import android.Manifest
import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.*
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ambient.client.data.SettingsRepository
import com.ambient.client.ui.AmbientViewModel
import com.ambient.client.ui.ChatScreen
import com.ambient.client.ui.SettingsScreen

/**
 * Main activity for Ambient Intelligence client.
 * 
 * Minimal UI with privacy-first design.
 */
class MainActivity : ComponentActivity() {
    
    private val settingsRepository by lazy { SettingsRepository(applicationContext) }
    
    private val voiceInputLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val matches = result.data?.getStringArrayListExtra(
                RecognizerIntent.EXTRA_RESULTS
            )
            matches?.firstOrNull()?.let { text ->
                // Handle voice input result
                // Will be passed to ViewModel
            }
        }
    }
    
    private val micPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            launchVoiceInput()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        setContent {
            AmbientTheme {
                AmbientApp(
                    settingsRepository = settingsRepository,
                    onVoiceInput = { handleVoiceInput() }
                )
            }
        }
    }
    
    private fun handleVoiceInput() {
        // Check permission first
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) 
            != android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        } else {
            launchVoiceInput()
        }
    }
    
    private fun launchVoiceInput() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak your prompt")
        }
        
        try {
            voiceInputLauncher.launch(intent)
        } catch (e: Exception) {
            // Speech recognition not available
        }
    }
}

@Composable
fun AmbientApp(
    settingsRepository: SettingsRepository,
    onVoiceInput: () -> Unit
) {
    var showSettings by remember { mutableStateOf(false) }
    
    // Create ViewModel with repository
    val viewModel = viewModel<AmbientViewModel>(
        factory = AmbientViewModelFactory(settingsRepository)
    )
    
    if (showSettings) {
        SettingsScreen(
            viewModel = viewModel,
            onBackClick = { showSettings = false }
        )
    } else {
        ChatScreen(
            viewModel = viewModel,
            onSettingsClick = { showSettings = true },
            onVoiceInput = onVoiceInput
        )
    }
}

@Composable
fun AmbientTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) {
        darkColorScheme()
    } else {
        lightColorScheme()
    }
    
    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
