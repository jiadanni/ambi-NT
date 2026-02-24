# Ambient Intelligence - Android Client

**Privacy-first AI inference client for Android**

Ultra-minimal design with no tracking, ephemeral conversations, and end-to-end encryption.

## Features

- 🔒 **End-to-End Encryption**: NaCl/libsodium (Curve25519 + XSalsa20-Poly1305)
- 👻 **Ephemeral by Default**: Conversations cleared when app closes
- 🚫 **Zero Tracking**: No analytics, ads, or telemetry
- 📱 **Minimal UI**: Swipe up to type, hold to talk (opt-in)
- 🔑 **Ephemeral Keys**: Forward secrecy with in-memory-only keypairs
- 🎯 **Small APK**: ~5-8 MB optimized build

## Privacy Guarantees

### What We DON'T Do
- ❌ No data persistence (conversations deleted on app close)
- ❌ No cloud backup
- ❌ No analytics or crash reporting
- ❌ No third-party SDKs (except core crypto/HTTP)
- ❌ No advertising
- ❌ No location tracking

### What We DO
- ✅ INTERNET permission (required for network communication)
- ✅ RECORD_AUDIO permission (ONLY if you enable voice input)
- ✅ Minimal settings stored locally (node URL, voice consent)
- ✅ Ephemeral keypairs generated per session, cleared on exit

### Voice Input Privacy Risk ⚠️

If you enable voice input:
- Audio is sent to your device's speech recognition service (Google/Samsung/etc.)
- This is OUTSIDE our control and may be stored by the provider
- The app explicitly warns you before enabling
- Voice input is OPT-IN only

## UI Design

### Main Screen (Empty State)
```
┌─────────────────────────┐
│ Ambient            [⋮]  │
│ Ephemeral · No history  │
├─────────────────────────┤
│                         │
│   🔒 Privacy-First      │
│   • Ephemeral keys      │
│   • E2E encryption      │
│   • No tracking         │
│                         │
│         ↑               │
│   Swipe up to type      │
│                         │
│      [🎤 Hold]          │
│   Hold to talk          │
│   ⚠️ Audio sent to      │
│   device speech service │
│                         │
└─────────────────────────┘
```

### Main Screen (With Messages)
```
┌─────────────────────────┐
│ Ambient            [⋮]  │
│ Ephemeral · No history  │
├─────────────────────────┤
│                         │
│ ┌─────────────────┐     │
│ │ You             │     │
│ │ What is 2+2?    │     │
│ └─────────────────┘     │
│                         │
│     ┌─────────────────┐ │
│     │ Assistant       │ │
│     │ 2+2 equals 4.   │ │
│     └─────────────────┘ │
│                         │
│              [+]        │
└─────────────────────────┘
```

### Input Sheet (Swipe Up)
```
┌─────────────────────────┐
│                         │
│ ┌─────────────────────┐ │
│ │ Type your prompt... │ │
│ │                     │ │
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
│ [←] Settings            │
├─────────────────────────┤
│                         │
│ Node URL                │
│ ┌─────────────────────┐ │
│ │ http://localhost:80…│ │
│ └─────────────────────┘ │
│ [Save]                  │
│                         │
│ Enable voice input      │
│ ⚠️ Audio sent to device │
│ speech service          │
│                         │
│ □ I understand          │
│                    [⚪] │
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

## Build Instructions

### Prerequisites
- Android Studio Hedgehog or later
- JDK 17+
- Android SDK 34
- Gradle 8.2+

### Build APK

```bash
cd client-android

# Debug build (includes debugging symbols)
./gradlew assembleDebug

# Release build (optimized, minified)
./gradlew assembleRelease

# Output: app/build/outputs/apk/
```

### Install on Device

```bash
# Via ADB
adb install app/build/outputs/apk/debug/app-debug.apk

# Or use Android Studio: Run > Run 'app'
```

## Configuration

### Node URL
Default: `http://localhost:8000`

To connect to a different node:
1. Open app
2. Tap 3-dot menu (top right)
3. Enter node URL
4. Tap "Save"

For local testing on emulator:
- Use `http://10.0.2.2:8000` (emulator host)

For device on same network:
- Use node's IP: `http://192.168.1.100:8000`

## Architecture

```
client-android/
├── src/main/
│   ├── java/com/ambient/client/
│   │   ├── crypto/
│   │   │   └── AmbientCrypto.kt          # NaCl encryption wrapper
│   │   ├── network/
│   │   │   ├── ApiModels.kt              # Request/response models
│   │   │   └── AmbientClient.kt          # HTTP client
│   │   ├── data/
│   │   │   ├── Models.kt                 # Ephemeral conversation data
│   │   │   └── SettingsRepository.kt     # Minimal persistent config
│   │   ├── ui/
│   │   │   ├── ChatScreen.kt             # Main swipe-up UI
│   │   │   ├── SettingsScreen.kt         # Settings UI
│   │   │   └── AmbientViewModel.kt       # State management
│   │   ├── MainActivity.kt               # Entry point
│   │   ├── AmbientApplication.kt         # App lifecycle
│   │   └── AmbientViewModelFactory.kt    # DI for ViewModel
│   ├── res/
│   │   ├── values/strings.xml            # UI strings
│   │   └── xml/
│   │       ├── network_security_config.xml  # HTTPS enforcement
│   │       └── data_extraction_rules.xml    # Disable backups
│   └── AndroidManifest.xml               # Minimal permissions
├── build.gradle.kts                      # Dependencies
├── proguard-rules.pro                    # Privacy-focused obfuscation
└── README.md                             # This file
```

## Dependencies

### Cryptography
- **Lazysodium-Android** (5.1.0) - JNA wrapper for libsodium
- **JNA** (5.13.0) - Java Native Access

### Networking
- **OkHttp** (4.12.0) - HTTP client with no-cache configuration

### Serialization
- **kotlinx.serialization** (1.6.2) - JSON parsing

### UI
- **Jetpack Compose** (BOM 2024.01.00) - Modern declarative UI
- **Material3** - Material Design 3 components

### Storage
- **DataStore** (1.0.0) - Minimal settings persistence

All dependencies are open source and auditable.

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
- **Storage**: RAM only (never written to disk)
- **Cleared**: On app close via `ViewModel.onCleared()`

### Network Security
- HTTPS enforced for production nodes
- Cleartext allowed ONLY for localhost/private IPs (testing)
- See `res/xml/network_security_config.xml`

## Testing Against Python Node

### 1. Start Local Node
```bash
cd ../node
python server.py
# Node runs on http://localhost:8000
```

### 2. Test with Android Emulator
```bash
# In client-android/
./gradlew installDebug

# Open app, settings, set node URL to:
# http://10.0.2.2:8000

# Submit a test prompt
```

### 3. Test with Physical Device (Same Network)
```bash
# Find your machine's IP
ifconfig | grep inet  # macOS/Linux
ipconfig             # Windows

# In app settings, use:
# http://YOUR_IP:8000
```

## Known Limitations

1. **No Conversation History**: By design. Conversations are ephemeral.
2. **Single Node**: No coordinator integration yet (planned for v2).
3. **Voice Privacy**: Voice input uses device speech service (Google/Samsung/etc.). This is outside our control.
4. **No Offline Mode**: Requires network connection to submit prompts.

## Roadmap

- [ ] Coordinator integration for dynamic node discovery
- [ ] Conversation export (encrypted, user-initiated)
- [ ] Dark/light theme customization
- [ ] Node health check before submit
- [ ] Retry logic for failed requests
- [ ] F-Droid release (no Google dependencies)

## Privacy Compliance

### GDPR
- ✅ No personal data collected
- ✅ No data retention
- ✅ Explicit consent for voice input
- ✅ User control over all data

### Data Minimization
- Only stores: node URL, voice consent flag
- No user ID, no session tracking, no analytics

### Right to Erasure
- All data cleared on app uninstall
- No server-side data to delete

## License

Same as parent project (see ../LICENSE)

## Contributing

See ../CONTRIBUTING.md

## Questions?

- **Protocol**: See `../protocol/SPECIFICATION.md`
- **Security**: See `../docs/SECURITY.md`
- **API**: See `../docs/API.md`
