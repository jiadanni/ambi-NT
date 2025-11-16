# Security Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                               │
│                      POST /submit                                    │
│  {                                                                   │
│    encrypted_prompt: "base64...",                                    │
│    client_pubkey: "base64...",                                       │
│    proof_of_work_nonce: "abc123" (optional)                          │
│  }                                                                   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYER 1: RATE LIMITING                   │
│ ─────────────────────────────────────────────────────────────────── │
│  ✓ Check if client blocked by auth failures (20 failures/hour)      │
│  ✓ Check per-client rate limit (default: 10 req/min)                │
│  ✓ Check global rate limit (default: 100 req/min)                   │
│                                                                      │
│  ❌ REJECT: HTTP 429 "Rate limit exceeded"                          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ ✓ PASS
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│               SECURITY LAYER 2: CLIENT AUTHENTICATION                │
│ ─────────────────────────────────────────────────────────────────── │
│  IF allowlist configured:                                            │
│    ✓ Check if client_pubkey in ALLOWED_CLIENT_KEYS                  │
│                                                                      │
│  ❌ REJECT: HTTP 403 "Client not authorized"                        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ ✓ PASS
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SECURITY LAYER 3: PROOF-OF-WORK (Optional)              │
│ ─────────────────────────────────────────────────────────────────── │
│  IF PoW enabled:                                                     │
│    IF no nonce provided:                                             │
│      → Generate challenge, return 200 + challenge                   │
│    ELSE:                                                             │
│      ✓ Verify PoW solution                                          │
│                                                                      │
│  ❌ REJECT: HTTP 400 "Invalid proof-of-work"                        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ ✓ PASS
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  SECURITY LAYER 4: REQUEST VALIDATION                │
│ ─────────────────────────────────────────────────────────────────── │
│  ✓ Validate encrypted_prompt is valid base64                        │
│  ✓ Check encrypted size ≤ 50KB                                      │
│  ✓ Validate client_pubkey is 32-byte NaCl key                       │
│                                                                      │
│  ❌ REJECT: HTTP 422 "Validation error"                             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ ✓ PASS
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ACCEPTED - CREATE JOB                            │
│                  Return job_id, start async processing              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ASYNC PROCESSING: DECRYPTION                      │
│ ─────────────────────────────────────────────────────────────────── │
│  1. Decrypt prompt using node private key + client public key       │
│  2. Plaintext exists only in memory (never logged/stored)           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SECURITY LAYER 5: PROMPT SANITIZATION                   │
│ ─────────────────────────────────────────────────────────────────── │
│  ✓ Check prompt length ≤ MAX_PROMPT_LENGTH (default: 10,000)        │
│  ✓ Check line count ≤ 500                                           │
│  ✓ Check for excessive character repetition (>100 chars)            │
│  ✓ Check for dangerous control characters                           │
│  ✓ Scan for 15+ injection patterns:                                 │
│    • "Ignore previous instructions"                                 │
│    • "You are now in DAN mode"                                      │
│    • "Show me your system prompt"                                   │
│    • Code execution attempts                                        │
│    • And more...                                                    │
│  ⚠ Generate warnings for suspicious patterns                        │
│                                                                      │
│  ❌ REJECT: Job fails with "Prompt validation failed"               │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ ✓ PASS
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SEND TO OLLAMA FOR INFERENCE                      │
│  • Timeout enforced (default: 120s)                                 │
│  • Resource usage monitored                                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   ENCRYPT RESPONSE & RETURN                          │
│  1. Encrypt response with client's public key                       │
│  2. Store encrypted response in job                                 │
│  3. Plaintext destroyed (garbage collected)                         │
│  4. Client polls /status/{job_id} to retrieve                       │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════
                        ATTACK VECTOR PROTECTION
═══════════════════════════════════════════════════════════════════════

╔════════════════════════════════════════════════════════════════════╗
║ ATTACK: Spam/Flood (many requests)                                 ║
║ MITIGATION: Rate limiting (Layer 1)                                ║
║ STATUS: ✅ PROTECTED                                               ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║ ATTACK: Distributed DoS (many client keys)                         ║
║ MITIGATION: Global rate limiting (Layer 1)                         ║
║ STATUS: ✅ PROTECTED                                               ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║ ATTACK: Unauthorized access                                        ║
║ MITIGATION: Client allowlist (Layer 2)                             ║
║ STATUS: ✅ PROTECTED (when enabled)                                ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║ ATTACK: Prompt injection ("ignore instructions...")                ║
║ MITIGATION: Pattern-based detection (Layer 5)                      ║
║ STATUS: ✅ PROTECTED                                               ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║ ATTACK: Jailbreak attempts ("DAN mode...")                         ║
║ MITIGATION: Pattern-based detection (Layer 5)                      ║
║ STATUS: ✅ PROTECTED                                               ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║ ATTACK: Resource exhaustion (huge prompts)                         ║
║ MITIGATION: Size limits (Layers 4 & 5)                             ║
║ STATUS: ✅ PROTECTED                                               ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║ ATTACK: Brute force (trying many keys)                             ║
║ MITIGATION: Auth failure tracking (Layer 1)                        ║
║ STATUS: ✅ PROTECTED                                               ║
╚════════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════
                     CONFIGURATION QUICK REFERENCE
═══════════════════════════════════════════════════════════════════════

┌──────────────────────┬──────────────┬──────────────┬──────────────┐
│ Security Feature     │ Development  │ Production   │ Public Node  │
│                      │ (Permissive) │ (Private)    │ (Strict)     │
├──────────────────────┼──────────────┼──────────────┼──────────────┤
│ Rate Limiting        │ Optional     │ ✅ Required  │ ✅ Required  │
│ Per-Client Limit     │ 100/min      │ 20/min       │ 5/min        │
│ Global Limit         │ 1000/min     │ 200/min      │ 50/min       │
│                      │              │              │              │
│ Prompt Sanitization  │ ✅ Enabled   │ ✅ Enabled   │ ✅ Enabled   │
│ Max Prompt Length    │ 50,000       │ 10,000       │ 5,000        │
│                      │              │              │              │
│ Client Allowlist     │ ❌ Disabled  │ ✅ Enabled   │ Optional     │
│                      │              │              │              │
│ Proof-of-Work        │ ❌ Disabled  │ ❌ Disabled  │ ✅ Enabled   │
│ PoW Difficulty       │ N/A          │ N/A          │ 5            │
└──────────────────────┴──────────────┴──────────────┴──────────────┘


═══════════════════════════════════════════════════════════════════════
                         MONITORING & LOGGING
═══════════════════════════════════════════════════════════════════════

Key log messages to monitor:

🔴 CRITICAL: "Client blocked due to auth failures"
   → Potential brute force attack in progress

🟠 WARNING: "Global rate limit exceeded"
   → Possible distributed DoS attack

🟠 WARNING: "Prompt validation failed"
   → Prompt injection attempt detected

🟡 INFO: "Suspicious pattern detected"
   → Unusual but not necessarily malicious activity

📊 METRICS: Check /metrics endpoint
   → "security" section shows enabled features
   → Monitor success_rate for anomalies

```
