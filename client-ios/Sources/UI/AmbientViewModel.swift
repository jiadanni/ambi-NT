import SwiftUI
import Combine

/// Main view model for the Ambient client.
///
/// Manages ephemeral conversations (in-memory only).
@MainActor
class AmbientViewModel: ObservableObject {
    @Published var currentConversation = Conversation()
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let settings: SettingsRepository
    
    init(settings: SettingsRepository) {
        self.settings = settings
    }
    
    /// Submit a prompt to the network.
    func submitPrompt(_ prompt: String) {
        guard !prompt.isEmpty else { return }
        
        Task {
            isLoading = true
            errorMessage = nil
            
            // Add user message immediately
            let userMessage = Message(text: prompt, isFromUser: true)
            currentConversation.messages.append(userMessage)
            
            do {
                // Create client and submit
                let client = AmbientClient(nodeUrl: settings.nodeUrl)
                let response = try await client.submitAndWait(prompt: prompt)
                
                // Add assistant response
                let assistantMessage = Message(text: response, isFromUser: false)
                currentConversation.messages.append(assistantMessage)
                
            } catch {
                errorMessage = error.localizedDescription
            }
            
            isLoading = false
        }
    }
    
    /// Start a new conversation (clears current messages).
    func newConversation() {
        currentConversation = Conversation()
        errorMessage = nil
    }
    
    /// Clear error message.
    func clearError() {
        errorMessage = nil
    }
}
