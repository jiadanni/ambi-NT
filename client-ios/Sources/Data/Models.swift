import Foundation

/// Ephemeral conversation model.
///
/// Lives only in memory - never persisted.
/// Cleared when app closes.
struct Message: Identifiable {
    let id = UUID()
    let text: String
    let isFromUser: Bool
    let timestamp: Date = Date()
}

struct Conversation: Identifiable {
    let id = UUID()
    var messages: [Message] = []
    let createdAt: Date = Date()
}
