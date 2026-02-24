import SwiftUI

@main
struct AmbientApp: App {
    @StateObject private var settings = SettingsRepository()
    
    var body: some Scene {
        WindowGroup {
            ChatScreen(
                viewModel: AmbientViewModel(settings: settings),
                settings: settings
            )
        }
    }
}
