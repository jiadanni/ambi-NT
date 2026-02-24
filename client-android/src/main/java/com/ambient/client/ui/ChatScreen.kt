package com.ambient.client.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.ambient.client.R
import com.ambient.client.data.Message
import kotlinx.coroutines.launch
import kotlin.math.abs

/**
 * Main chat screen with minimal UI:
 * - Swipe up to reveal text input
 * - Hold center button to use voice (with privacy warning)
 * - + button center for new conversation
 * - 3-dot menu top-right for settings
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    viewModel: AmbientViewModel,
    onSettingsClick: () -> Unit,
    onVoiceInput: () -> Unit
) {
    val messages = viewModel.currentConversation.messages
    val isLoading = viewModel.isLoading
    val errorMessage = viewModel.errorMessage
    val voiceEnabled by viewModel.voiceEnabled.collectAsState()
    
    var showInputSheet by remember { mutableStateOf(false) }
    var inputText by remember { mutableStateOf("") }
    
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Ambient")
                        Text(
                            stringResource(R.string.privacy_ephemeral),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onSettingsClick) {
                        Icon(Icons.Default.MoreVert, "Settings")
                    }
                }
            )
        },
        floatingActionButton = {
            // Center FAB for new conversation
            if (messages.isNotEmpty() && !isLoading) {
                FloatingActionButton(
                    onClick = { viewModel.newConversation() },
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                ) {
                    Icon(Icons.Default.Add, stringResource(R.string.new_conversation))
                }
            }
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Messages list
            if (messages.isEmpty() && !isLoading) {
                EmptyState(
                    voiceEnabled = voiceEnabled,
                    onSwipeUp = { showInputSheet = true },
                    onVoiceInput = onVoiceInput
                )
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(messages) { message ->
                        MessageBubble(message)
                    }
                    
                    if (isLoading) {
                        item {
                            LoadingIndicator()
                        }
                    }
                }
                
                // Auto-scroll to bottom when new message arrives
                LaunchedEffect(messages.size) {
                    if (messages.isNotEmpty()) {
                        scope.launch {
                            listState.animateScrollToItem(messages.size - 1)
                        }
                    }
                }
            }

            // Error snackbar
            errorMessage?.let { error ->
                Snackbar(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(16.dp),
                    action = {
                        TextButton(onClick = { viewModel.clearError() }) {
                            Text("Dismiss")
                        }
                    }
                ) {
                    Text(error)
                }
            }
        }
    }

    // Bottom sheet for text input (swipe up to reveal)
    if (showInputSheet) {
        ModalBottomSheet(
            onDismissRequest = { 
                showInputSheet = false
                inputText = ""
            }
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
            ) {
                OutlinedTextField(
                    value = inputText,
                    onValueChange = { inputText = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Type your prompt...") },
                    minLines = 3,
                    maxLines = 10
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                Button(
                    onClick = {
                        viewModel.submitPrompt(inputText)
                        showInputSheet = false
                        inputText = ""
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = inputText.isNotBlank() && !isLoading
                ) {
                    Text("Submit")
                }
                
                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }
}

@Composable
fun EmptyState(
    voiceEnabled: Boolean,
    onSwipeUp: () -> Unit,
    onVoiceInput: () -> Unit
) {
    var dragOffset by remember { mutableStateOf(0f) }
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                detectVerticalDragGestures(
                    onDragEnd = {
                        if (dragOffset < -100f) { // Swipe up threshold
                            onSwipeUp()
                        }
                        dragOffset = 0f
                    },
                    onVerticalDrag = { _, dragAmount ->
                        dragOffset += dragAmount
                    }
                )
            },
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(24.dp),
            modifier = Modifier.padding(32.dp)
        ) {
            // Privacy notice
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        "🔒 Privacy-First",
                        style = MaterialTheme.typography.titleMedium
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "• ${stringResource(R.string.privacy_ephemeral)}",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(
                        "• ${stringResource(R.string.privacy_e2e)}",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(
                        "• ${stringResource(R.string.privacy_no_tracking)}",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
            
            // Swipe up hint
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.alpha(0.6f + (abs(dragOffset) / 500f).coerceIn(0f, 0.4f))
            ) {
                Text(
                    "↑",
                    style = MaterialTheme.typography.displayMedium,
                    textAlign = TextAlign.Center
                )
                Text(
                    stringResource(R.string.swipe_up_hint),
                    style = MaterialTheme.typography.bodyLarge,
                    textAlign = TextAlign.Center
                )
            }
            
            // Voice input (if enabled)
            if (voiceEnabled) {
                Spacer(modifier = Modifier.height(16.dp))
                HoldToTalkButton(onVoiceInput = onVoiceInput)
            }
        }
    }
}

@Composable
fun HoldToTalkButton(onVoiceInput: () -> Unit) {
    var isPressed by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 1.1f else 1f,
        animationSpec = spring(stiffness = Spring.StiffnessLow)
    )
    
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        FilledTonalButton(
            onClick = { /* No-op, uses gesture */ },
            modifier = Modifier
                .size(80.dp)
                .scale(scale)
                .pointerInput(Unit) {
                    detectVerticalDragGestures(
                        onDragStart = {
                            isPressed = true
                            onVoiceInput()
                        },
                        onDragEnd = {
                            isPressed = false
                        },
                        onDragCancel = {
                            isPressed = false
                        },
                        onVerticalDrag = { _, _ -> }
                    )
                },
            shape = CircleShape
        ) {
            Text(
                "🎤",
                style = MaterialTheme.typography.displaySmall
            )
        }
        
        Text(
            stringResource(R.string.hold_to_talk),
            style = MaterialTheme.typography.labelMedium
        )
        
        Text(
            stringResource(R.string.privacy_voice_warning),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.error,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 32.dp)
        )
    }
}

@Composable
fun MessageBubble(message: Message) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (message.isFromUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            colors = CardDefaults.cardColors(
                containerColor = if (message.isFromUser) {
                    MaterialTheme.colorScheme.primaryContainer
                } else {
                    MaterialTheme.colorScheme.secondaryContainer
                }
            ),
            modifier = Modifier
                .widthIn(max = 280.dp)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    if (message.isFromUser) stringResource(R.string.you) 
                    else stringResource(R.string.assistant),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    message.text,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }
    }
}

@Composable
fun LoadingIndicator() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.Start
    ) {
        Card(
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.secondaryContainer
            ),
            modifier = Modifier.widthIn(max = 280.dp)
        ) {
            Row(
                modifier = Modifier.padding(12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    strokeWidth = 2.dp
                )
                Text(
                    stringResource(R.string.processing),
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        }
    }
}
