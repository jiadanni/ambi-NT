import SwiftUI

/// Settings screen: node URL + voice privacy consent.
struct SettingsScreen: View {
    @ObservedObject var settings: SettingsRepository
    @Environment(\.dismiss) private var dismiss
    @State private var editedNodeUrl: String = ""
    
    var body: some View {
        NavigationStack {
            Form {
                // Node URL
                Section {
                    TextField("Node URL", text: $editedNodeUrl)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    
                    Button("Save") {
                        settings.nodeUrl = editedNodeUrl
                    }
                    .disabled(editedNodeUrl == settings.nodeUrl || editedNodeUrl.isEmpty)
                } header: {
                    Text("Node URL")
                } footer: {
                    Text("Default: http://localhost:8000")
                }
                
                // Voice input settings
                Section {
                    Toggle("Enable voice input", isOn: $settings.voiceEnabled)
                        .disabled(!settings.voiceConsentGiven)
                    
                    if !settings.voiceConsentGiven {
                        Toggle("I understand voice audio is sent to my device's speech service", isOn: $settings.voiceConsentGiven)
                            .toggleStyle(.checkbox)
                    }
                } header: {
                    Text("Voice Input")
                } footer: {
                    Text("⚠️ Voice input sends audio to device speech recognition service (Apple). This is acknowledged as a privacy risk.")
                        .foregroundColor(.red)
                }
                
                // About
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Privacy-first AI inference")
                        Text("• Ephemeral keys (not saved)")
                        Text("• End-to-end encryption")
                        Text("• No tracking or analytics")
                        Text("• Open source")
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                } header: {
                    Text("About")
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .onAppear {
                editedNodeUrl = settings.nodeUrl
            }
        }
    }
}
