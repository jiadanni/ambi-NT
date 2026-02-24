import SwiftUI
import Speech

/// Main chat screen with minimal UI:
/// - Swipe up to reveal text input
/// - Long press center button to use voice (with privacy warning)
/// - + button center for new conversation
/// - 3-dot menu top-right for settings
struct ChatScreen: View {
    @ObservedObject var viewModel: AmbientViewModel
    @ObservedObject var settings: SettingsRepository
    @State private var showSettings = false
    @State private var showInputSheet = false
    @State private var inputText = ""
    @State private var showVoiceInput = false
    
    var body: some View {
        NavigationStack {
            ZStack {
                if viewModel.currentConversation.messages.isEmpty && !viewModel.isLoading {
                    EmptyStateView(
                        voiceEnabled: settings.voiceEnabled,
                        onSwipeUp: { showInputSheet = true },
                        onVoiceInput: { showVoiceInput = true }
                    )
                } else {
                    MessagesListView(
                        messages: viewModel.currentConversation.messages,
                        isLoading: viewModel.isLoading
                    )
                }
                
                // Error message
                if let error = viewModel.errorMessage {
                    VStack {
                        Spacer()
                        ErrorBanner(message: error) {
                            viewModel.clearError()
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("Ambient")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    VStack(spacing: 2) {
                        Text("Ambient")
                            .font(.headline)
                        Text("Ephemeral · No history")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .overlay(alignment: .bottom) {
                if !viewModel.currentConversation.messages.isEmpty && !viewModel.isLoading {
                    NewConversationButton {
                        viewModel.newConversation()
                    }
                    .padding(.bottom, 20)
                }
            }
            .sheet(isPresented: $showInputSheet) {
                InputSheet(
                    text: $inputText,
                    isLoading: viewModel.isLoading
                ) {
                    viewModel.submitPrompt(inputText)
                    inputText = ""
                    showInputSheet = false
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsScreen(settings: settings)
            }
            .sheet(isPresented: $showVoiceInput) {
                VoiceInputSheet { transcript in
                    viewModel.submitPrompt(transcript)
                }
            }
        }
    }
}

/// Empty state with privacy notice and swipe-up hint
struct EmptyStateView: View {
    let voiceEnabled: Bool
    let onSwipeUp: () -> Void
    let onVoiceInput: () -> Void
    
    @State private var dragOffset: CGFloat = 0
    
    var body: some View {
        VStack(spacing: 32) {
            // Privacy notice
            GroupBox {
                VStack(alignment: .leading, spacing: 8) {
                    Label("Privacy-First", systemImage: "lock.fill")
                        .font(.headline)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("• Ephemeral keys · No history")
                        Text("• End-to-end encrypted")
                        Text("• No tracking or analytics")
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal)
            
            // Swipe up hint
            VStack(spacing: 8) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 48))
                    .foregroundStyle(.secondary)
                Text("Swipe up to type")
                    .font(.body)
                    .foregroundStyle(.secondary)
            }
            .opacity(0.6 + Double(abs(dragOffset)) / 500.0)
            
            // Voice input (if enabled)
            if voiceEnabled {
                HoldToTalkButton(onTrigger: onVoiceInput)
            }
        }
        .padding()
        .gesture(
            DragGesture()
                .onChanged { value in
                    dragOffset = value.translation.height
                }
                .onEnded { value in
                    if value.translation.height < -100 {
                        onSwipeUp()
                    }
                    dragOffset = 0
                }
        )
    }
}

/// Hold-to-talk button with privacy warning
struct HoldToTalkButton: View {
    let onTrigger: () -> Void
    @State private var isPressed = false
    
    var body: some View {
        VStack(spacing: 12) {
            Button {
                // No-op, uses long press gesture
            } label: {
                Image(systemName: "mic.fill")
                    .font(.system(size: 32))
                    .frame(width: 80, height: 80)
                    .background(Color.accentColor.opacity(0.2))
                    .clipShape(Circle())
            }
            .scaleEffect(isPressed ? 1.1 : 1.0)
            .onLongPressGesture(minimumDuration: 0.5) {
                onTrigger()
            } onPressingChanged: { pressing in
                withAnimation(.spring(response: 0.3)) {
                    isPressed = pressing
                }
            }
            
            Text("Hold to talk")
                .font(.caption)
            
            Text("⚠️ Voice input sends audio to device speech service")
                .font(.caption2)
                .foregroundColor(.red)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
        }
    }
}

/// Messages list view
struct MessagesListView: View {
    let messages: [Message]
    let isLoading: Bool
    
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }
                    
                    if isLoading {
                        LoadingIndicator()
                    }
                }
                .padding()
            }
            .onChange(of: messages.count) { _ in
                if let lastMessage = messages.last {
                    withAnimation {
                        proxy.scrollTo(lastMessage.id, anchor: .bottom)
                    }
                }
            }
        }
    }
}

/// Message bubble
struct MessageBubble: View {
    let message: Message
    
    var body: some View {
        HStack {
            if message.isFromUser { Spacer() }
            
            VStack(alignment: message.isFromUser ? .trailing : .leading, spacing: 4) {
                Text(message.isFromUser ? "You" : "Assistant")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                
                Text(message.text)
                    .padding(12)
                    .background(message.isFromUser ? Color.accentColor.opacity(0.2) : Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .frame(maxWidth: 280, alignment: message.isFromUser ? .trailing : .leading)
            
            if !message.isFromUser { Spacer() }
        }
    }
}

/// Loading indicator
struct LoadingIndicator: View {
    var body: some View {
        HStack {
            HStack(spacing: 8) {
                ProgressView()
                    .scaleEffect(0.8)
                Text("Processing…")
                    .font(.body)
            }
            .padding(12)
            .background(Color(.systemGray6))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            
            Spacer()
        }
    }
}

/// New conversation button
struct NewConversationButton: View {
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Image(systemName: "plus")
                .font(.title2)
                .foregroundColor(.white)
                .frame(width: 56, height: 56)
                .background(Color.accentColor)
                .clipShape(Circle())
                .shadow(radius: 4)
        }
    }
}

/// Error banner
struct ErrorBanner: View {
    let message: String
    let onDismiss: () -> Void
    
    var body: some View {
        HStack {
            Text(message)
                .font(.callout)
            Spacer()
            Button("Dismiss", action: onDismiss)
                .font(.callout)
        }
        .padding()
        .background(Color.red.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

/// Input sheet (swipe up to reveal)
struct InputSheet: View {
    @Binding var text: String
    let isLoading: Bool
    let onSubmit: () -> Void
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                TextEditor(text: $text)
                    .frame(minHeight: 100)
                    .padding(8)
                    .background(Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                
                Button {
                    onSubmit()
                } label: {
                    Text("Submit")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(text.isEmpty || isLoading ? Color.gray : Color.accentColor)
                        .foregroundColor(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(text.isEmpty || isLoading)
                
                Spacer()
            }
            .padding()
            .navigationTitle("Type your prompt")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

/// Voice input sheet
struct VoiceInputSheet: View {
    let onTranscript: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var transcript = ""
    @State private var isRecording = false
    @State private var errorMessage: String?
    
    private let speechRecognizer = SFSpeechRecognizer()
    private let audioEngine = AVAudioEngine()
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.red)
                        .padding()
                }
                
                if !transcript.isEmpty {
                    ScrollView {
                        Text(transcript)
                            .padding()
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color(.systemGray6))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }
                
                Spacer()
                
                Button {
                    if transcript.isEmpty {
                        startRecording()
                    } else {
                        onTranscript(transcript)
                        dismiss()
                    }
                } label: {
                    Text(transcript.isEmpty ? "Start Recording" : "Submit")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accentColor)
                        .foregroundColor(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
            .padding()
            .navigationTitle("Voice Input")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
    
    private func startRecording() {
        // Request speech recognition permission
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                switch status {
                case .authorized:
                    // Permission granted - would implement actual recording here
                    // For now, just show placeholder
                    errorMessage = "Voice recording not implemented in this demo"
                default:
                    errorMessage = "Speech recognition permission denied"
                }
            }
        }
    }
}
