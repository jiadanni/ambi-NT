package com.ambient.client.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.ambient.client.R
import com.ambient.client.data.SettingsRepository
import kotlinx.coroutines.launch

/**
 * Settings screen: node URL + voice privacy consent.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: AmbientViewModel,
    onBackClick: () -> Unit
) {
    val nodeUrl by viewModel.nodeUrl.collectAsState()
    val voiceEnabled by viewModel.voiceEnabled.collectAsState()
    val voiceConsent by viewModel.voiceConsentGiven.collectAsState()
    
    var editedNodeUrl by remember { mutableStateOf(nodeUrl) }
    val scope = rememberCoroutineScope()
    
    // Sync when nodeUrl changes
    LaunchedEffect(nodeUrl) {
        editedNodeUrl = nodeUrl
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings)) },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.Default.ArrowBack, "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // Node URL
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        stringResource(R.string.settings_node_url),
                        style = MaterialTheme.typography.titleMedium
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    OutlinedTextField(
                        value = editedNodeUrl,
                        onValueChange = { editedNodeUrl = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { 
                            Text(stringResource(R.string.settings_node_url_hint)) 
                        },
                        singleLine = true
                    )
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Button(
                        onClick = {
                            viewModel.updateNodeUrl(editedNodeUrl)
                        },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = editedNodeUrl != nodeUrl && editedNodeUrl.isNotBlank()
                    ) {
                        Text("Save")
                    }
                }
            }
            
            // Voice input settings
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        stringResource(R.string.settings_voice_enabled),
                        style = MaterialTheme.typography.titleMedium
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Text(
                        stringResource(R.string.privacy_voice_warning),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Enable voice input")
                        Switch(
                            checked = voiceEnabled,
                            onCheckedChange = { enabled ->
                                viewModel.updateVoiceEnabled(enabled)
                            },
                            enabled = voiceConsent
                        )
                    }
                    
                    if (!voiceConsent) {
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                stringResource(R.string.settings_voice_privacy),
                                modifier = Modifier.weight(1f),
                                style = MaterialTheme.typography.bodySmall
                            )
                            Checkbox(
                                checked = false,
                                onCheckedChange = { checked ->
                                    viewModel.updateVoiceConsent(checked)
                                }
                            )
                        }
                    }
                }
            }
            
            // About
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        stringResource(R.string.settings_about),
                        style = MaterialTheme.typography.titleMedium
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        stringResource(R.string.settings_about_text),
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}
