# Ambient Intelligence - iOS/iPadOS Client

**Privacy-first AI inference client for iOS and iPadOS**

Ultra-minimal design with no tracking, ephemeral conversations, and end-to-end encryption.

## Features

- 🔒 **End-to-End Encryption**: NaCl/libsodium (Curve25519 + XSalsa20-Poly1305)
- 👻 **Ephemeral by Default**: Conversations cleared when app closes
- 🚫 **Zero Tracking**: No analytics, ads, or telemetry
- 📱 **Minimal UI**: Swipe up to type, long press to talk (opt-in)
- 🔑 **Ephemeral Keys**: Forward secrecy with in-memory-only keypairs
- 📲 **Native SwiftUI**: Modern iOS design, supports iPhone & iPad
- 🎯 **Small Binary**: ~3-5 MB optimized build

## Privacy Guarantees

### What We DON'T Do
- ❌ No data persistence (conversations deleted on app close)
- ❌ No iCloud backup
- ❌ No analytics or crash reporting
- ❌ No third-party SDKs (except libsodium)
- ❌ No advertising
- ❌ No location tracking
- ❌ No Keychain storage (except minimal settings)

### What We DO
- ✅ Network access (required for communication)
- ✅ Microphone access (ONLY if you enable voice input)
- ✅ Speech recognition (ONLY if you enable voice input)
- ✅ Minimal settings in UserDefaults (node URL, voice consent)
- ✅ Ephemeral keypairs generated per session, cleared on exit

### Voice Input Privacy Risk ⚠️

If you enable voice input:
- Audio is sent to Apple's speech recognition service
- This is OUTSIDE our control and may be stored by Apple
- The app explicitly warns you before enabling
- Voice input is OPT-IN only

## UI Design

### Main Screen (Empty State)
```
┌─────────────────────────┐
│    Ambient          ●●● │
│ Ephemeral · No history  │
├─────────────────────────┤
│                         │
│  ┌────────────────────┐ │
│  │ 🔒 Privacy-First   │ │
│  │ • Ephemeral keys   │ │
│  │ • E2E encryption   │ │
│  │ • No tracking      │ │
│  └────────────────────┘ │
│                         │
│         ↑               │
│   Swipe up to type      │
│                         │
│      [🎤 Hold]          │
│   Hold to talk          │
│   ⚠️ Audio sent to      │
│   Apple speech service  │
│                         │
└─────────────────────────┘
```

### Main Screen (With Messages)
```
┌─────────────────────────┐
│    Ambient          ●●● │
│ Ephemeral · No history  │
├─────────────────────────┤
│                         │
│          You            │
│ ┌─────────────────┐     │
│ │ What is 2+2?    │     │
│ └─────────────────┘     │
│                         │
│ Assistant               │
│     ┌─────────────────┐ │
│     │ 2+2 equals 4.   │ │
│     └─────────────────┘ │
│                         │
│              ⊕          │
└─────────────────────────┘
```

### Input Sheet (Swipe Up)
```
┌─────────────────────────┐
│ Cancel  Type your prompt│
├─────────────────────────┤
│                         │
│ ┌─────────────────────┐ │
│ │                     │ │
│ │ [Type here...]      │ │
│ │                     │ │
│ └─────────────────────┘ │
│                         │
│    [Submit]             │
│                         │
└─────────────────────────┘
```

### Settings
```
┌─────────────────────────┐
│ Done        Settings    │
├─────────────────────────┤
│ Node URL                │
│ http://localhost:8000   │
│ [Save]                  │
│ Default: http://local…  │
│                         │
│ Voice Input             │
│ Enable voice input  [ ] │
│ □ I understand voice    │
│   audio is sent to my   │
│   device's speech srv   │
│                         │
│ ⚠️ Audio sent to Apple  │
│ speech recognition      │
│                         │
│ About                   │
│ Privacy-first AI        │
│ • Ephemeral keys        │
│ • E2E encryption        │
│ • No tracking           │
│ • Open source           │
│                         │
└─────────────────────────┘
```

## Requirements

- iOS 16.0+ / iPadOS 16.0+
- Xcode 15+
- Swift 5.9+

## Build Instructions

### Using Xcode

1. Open the project:
```bash
cd client-ios
open Ambient.xcodeproj
```

2. Select target device (iPhone/iPad simulator or physical device)

3. Build and run: `Cmd + R`

### Using Swift Package Manager

```bash
cd client-ios
swift build
```

### Release Build

1. In Xcode: Product > Archive
2. Distribute App > App Store Connect / Ad Hoc / Development
3. Export IPA

## Configuration

### Node URL
Default: `http://localhost:8000`

To connect to a different node:
1. Open app
2. Tap 3-dot menu (top right)
3. Enter node URL
4. Tap "Save"

For local testing on simulator:
- Use `http://localhost:8000` (works on simulator)

For device on same network:
- Use node's IP: `http://192.168.1.100:8000`

## Architecture

```
client-ios/
├── Sources/
│   ├── Crypto/
│   │   └── AmbientCrypto.swift          # NaCl encryption wrapper
│   ├── Network/
│   │   ├── ApiModels.swift              # Request/response models
│   │   └── AmbientClient.swift          # HTTP client
│   ├── Data/
│   │   ├── Models.swift                 # Ephemeral conversation data
│   │   └── SettingsRepository.swift     # Minimal persistent config
│   ├── UI/
│   │   ├── ChatScreen.swift             # Main swipe-up UI
│   │   ├── SettingsScreen.swift         # Settings UI
│   │   └── AmbientViewModel.swift       # State management
│   └── AmbientApp.swift                 # Entry point
├── Package.swift                        # SPM dependencies
├── Info.plist                           # App configuration
├── Ambient.entitlements                 # Privacy restrictions
└── README.md                            # This file
```

## Dependencies

### Cryptography
- **swift-sodium** (0.9.1+) - Swift wrapper for libsodium

All dependencies managed via Swift Package Manager. No CocoaPods or proprietary SDKs.

## Security Notes

### Encryption Flow
1. App generates ephemeral Curve25519 keypair (in-memory)
2. Fetches node's public key via `GET /pubkey`
3. Encrypts prompt with NaCl Box (client private + node public)
4. Submits encrypted job via `POST /submit`
5. Polls `GET /status/{job_id}` until complete
6. Decrypts response with NaCl Box (client private + node public)

### Key Lifecycle
- **Generated**: On app start / new session
- **Storage**: RAM only (never written to disk/Keychain)
- **Cleared**: On app close via `deinit`

### Network Security
- App Transport Security (ATS) enforced
- HTTPS required for production nodes
- HTTP allowed ONLY for localhost (testing)
- See `Info.plist` for ATS configuration

## Testing Against Python Node

### 1. Start Local Node
```bash
cd ../node
python server.py
# Node runs on http://localhost:8000
```

### 2. Test with iOS Simulator
```bash
# In client-ios/
open Ambient.xcodeproj
# Xcode: Select iPhone simulator, Run

# In app, settings, node URL is already:
# http://localhost:8000

# Submit a test prompt
```

### 3. Test with Physical Device (Same Network)
```bash
# Find your machine's IP
ifconfig | grep inet  # macOS/Linux

# In app settings, use:
# http://YOUR_IP:8000
```

## iPad Support

The app is **Universal** - runs natively on both iPhone and iPad with adaptive layout:
- iPhone: Compact vertical layout
- iPad: Wider message bubbles, better use of screen space
- Supports multitasking (Split View, Slide Over)

## Known Limitations

1. **No Conversation History**: By design. Conversations are ephemeral.
2. **Single Node**: No coordinator integration yet (planned for v2).
3. **Voice Privacy**: Voice input uses Apple's speech service. This is outside our control.
4. **No Offline Mode**: Requires network connection to submit prompts.
5. **iOS 16+ Only**: Modern SwiftUI features require recent iOS.

## Roadmap

- [ ] Coordinator integration for dynamic node discovery
- [ ] Conversation export (encrypted, user-initiated)
- [ ] macOS Catalyst version
- [ ] Widget extension (quick access)
- [ ] Siri Shortcuts integration
- [ ] Node health check before submit
- [ ] Retry logic for failed requests

## Privacy Compliance

### Apple Privacy Nutrition Label
```
Data Not Collected:
- No data collected from this app

Data Not Linked to You:
- Node URL (stored locally only)
- Voice consent flag (stored locally only)
```

### GDPR
- ✅ No personal data collected
- ✅ No data retention
- ✅ Explicit consent for voice input
- ✅ User control over all data

### Data Minimization
- Only stores: node URL, voice consent flag (UserDefaults)
- No user ID, no session tracking, no analytics
- No iCloud sync

### Right to Erasure
- All data cleared on app uninstall
- No server-side data to delete

## App Store Submission

### Privacy Declaration
```
Does this app collect data?
NO

Does this app use third-party SDKs?
NO (swift-sodium is open source, no tracking)

Does this app use required reason API?
NO
```

### Export Compliance
Uses encryption: **YES** (libsodium)
Export compliance: **Exempt** (publicly available encryption)

## License

Same as parent project (see ../LICENSE)

## Contributing

See ../CONTRIBUTING.md

## Questions?

- **Protocol**: See `../protocol/SPECIFICATION.md`
- **Security**: See `../docs/SECURITY.md`
- **API**: See `../docs/API.md`

## Comparison: iOS vs Android

| Feature | iOS | Android |
|---------|-----|---------|
| **Language** | Swift | Kotlin |
| **UI Framework** | SwiftUI | Jetpack Compose |
| **Crypto** | swift-sodium | Lazysodium |
| **HTTP** | URLSession | OkHttp |
| **Min OS** | iOS 16 | Android 7 (API 24) |
| **Binary Size** | ~3-5 MB | ~5-8 MB |
| **Package Manager** | SPM | Gradle |

Both clients are feature-identical with the same privacy guarantees.
