import Foundation

/// Minimal persistent settings (node URL, voice consent).
///
/// Only stores necessary configuration, no tracking data.
@MainActor
class SettingsRepository: ObservableObject {
    static let defaultNodeURL = "http://localhost:8000"
    
    @Published var nodeUrl: String {
        didSet {
            UserDefaults.standard.set(nodeUrl, forKey: "nodeUrl")
        }
    }
    
    @Published var voiceEnabled: Bool {
        didSet {
            UserDefaults.standard.set(voiceEnabled, forKey: "voiceEnabled")
        }
    }
    
    @Published var voiceConsentGiven: Bool {
        didSet {
            UserDefaults.standard.set(voiceConsentGiven, forKey: "voiceConsentGiven")
        }
    }
    
    init() {
        self.nodeUrl = UserDefaults.standard.string(forKey: "nodeUrl") ?? Self.defaultNodeURL
        self.voiceEnabled = UserDefaults.standard.bool(forKey: "voiceEnabled")
        self.voiceConsentGiven = UserDefaults.standard.bool(forKey: "voiceConsentGiven")
    }
}
