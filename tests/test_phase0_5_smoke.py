"""
Phase 0.5 Smoke Test - Encryption Privacy Validation

This test validates the core privacy guarantee BEFORE building networking:

Privacy Guarantee Test:
1. Client generates ephemeral keypair
2. Client encrypts "Hello, Ollama"  
3. Node receives encrypted bytes
4. Node processes through Ollama (unencrypted internally)
5. Node encrypts response
6. Client decrypts response
7. CRITICAL: Node logs show ONLY base64 blobs, NO plaintext

This proves the privacy guarantee works before we add complexity.
"""

import sys
import base64
import logging
import io
from typing import List, Tuple

# Import crypto modules
sys.path.insert(0, '/Users/daniel.jatto/Source/mine/ambi-NT-Phase3')

from node.crypto import NodeCrypto, generate_keypair
from node.key_lifecycle import EphemeralKeyPair


class LogCapture:
    """Capture and analyze log output."""
    
    def __init__(self):
        self.logs: List[str] = []
        self.handler = None
        self.stream = None
    
    def __enter__(self):
        # Create string stream to capture logs
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setLevel(logging.DEBUG)
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.handler)
        root_logger.setLevel(logging.DEBUG)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Remove handler
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.handler)
        
        # Get captured logs
        self.logs = self.stream.getvalue().split('\n')
        self.stream.close()
    
    def contains_plaintext(self, plaintext: str) -> bool:
        """Check if any log contains the plaintext string."""
        for log in self.logs:
            if plaintext.lower() in log.lower():
                return True
        return False
    
    def contains_pattern(self, pattern: str) -> bool:
        """Check if any log matches pattern."""
        import re
        for log in self.logs:
            if re.search(pattern, log, re.IGNORECASE):
                return True
        return False


def test_encryption_privacy():
    """
    Test 1: Verify that encryption/decryption works and no plaintext leaks.
    """
    print("=" * 70)
    print("TEST 1: Basic Encryption Privacy")
    print("=" * 70)
    
    # Test payload (this should NEVER appear in logs)
    secret_prompt = "Hello, Ollama! This is a secret message."
    
    # Capture logs during test
    with LogCapture() as log_capture:
        # Step 1: Client generates ephemeral keypair
        print("\n[Client] Generating ephemeral keypair...")
        with EphemeralKeyPair() as client_key:
            client_pubkey = client_key.public_key_b64
            print(f"[Client] Public key: {client_pubkey[:32]}...")
            
            # Step 2: Node has long-lived keypair
            print("\n[Node] Initializing node crypto...")
            node_crypto = NodeCrypto()
            node_pubkey = node_crypto.get_public_key()
            print(f"[Node] Public key: {node_pubkey[:32]}...")
            
            # Step 3: Client encrypts prompt
            print("\n[Client] Encrypting prompt...")
            encrypted_prompt = client_key.encrypt(secret_prompt, node_pubkey)
            print(f"[Client] Encrypted (base64): {encrypted_prompt[:64]}...")
            
            # Step 4: Node receives and decrypts (simulating network transfer)
            print("\n[Node] Receiving encrypted prompt...")
            print(f"[Node] Received (base64): {encrypted_prompt[:64]}...")
            
            try:
                decrypted_prompt = node_crypto.decrypt_prompt(encrypted_prompt, client_pubkey)
                print(f"[Node] Decrypted prompt: {'*' * len(decrypted_prompt)} (length: {len(decrypted_prompt)})")
                
                # Verify decryption worked
                assert decrypted_prompt == secret_prompt, "Decryption failed!"
                
                # Step 5: Simulate Ollama processing (in real impl, this is internal)
                print(f"[Node] Processing with Ollama (internal only)...")
                ollama_response = f"Echo: {decrypted_prompt}"
                
                # Step 6: Node encrypts response
                print(f"\n[Node] Encrypting response...")
                encrypted_response = node_crypto.encrypt_response(ollama_response, client_pubkey)
                print(f"[Node] Encrypted response (base64): {encrypted_response[:64]}...")
                
                # Step 7: Client decrypts response
                print(f"\n[Client] Receiving encrypted response...")
                print(f"[Client] Received (base64): {encrypted_response[:64]}...")
                
                decrypted_response = client_key.decrypt(encrypted_response, node_pubkey)
                print(f"[Client] Decrypted response: {decrypted_response}")
                
                # Verify response
                assert ollama_response in decrypted_response, "Response decryption failed!"
                
            except Exception as e:
                print(f"[ERROR] {e}")
                raise
    
    # Step 8: Analyze logs for privacy leaks
    print("\n" + "=" * 70)
    print("PRIVACY ANALYSIS")
    print("=" * 70)
    
    # Check if secret prompt appears in logs
    leaked = log_capture.contains_plaintext(secret_prompt)
    
    if leaked:
        print("❌ PRIVACY VIOLATION: Plaintext found in logs!")
        print("\nLogs containing plaintext:")
        for log in log_capture.logs:
            if secret_prompt.lower() in log.lower():
                print(f"  {log}")
        return False
    else:
        print("✅ PASS: No plaintext found in logs")
    
    # Verify base64 encoding is present (we SHOULD log encrypted blobs)
    has_base64 = any(len(log) > 64 and log.count('=') > 0 for log in log_capture.logs)
    if has_base64:
        print("✅ PASS: Encrypted (base64) data present in logs")
    else:
        print("⚠️  WARNING: No base64 data found in logs")
    
    return True


def test_key_destruction():
    """
    Test 2: Verify ephemeral keys are destroyed after use.
    """
    print("\n" + "=" * 70)
    print("TEST 2: Ephemeral Key Destruction")
    print("=" * 70)
    
    node_crypto = NodeCrypto()
    node_pubkey = node_crypto.get_public_key()
    
    # Create and use ephemeral key
    print("\n[Test] Creating ephemeral keypair...")
    keypair = EphemeralKeyPair()
    pubkey = keypair.public_key_b64
    
    encrypted = keypair.encrypt("test", node_pubkey)
    print(f"[Test] Encrypted with keypair: {encrypted[:32]}...")
    
    # Destroy key
    print("[Test] Destroying keypair...")
    keypair.destroy()
    
    # Try to use destroyed key
    print("[Test] Attempting to use destroyed key...")
    try:
        keypair.encrypt("should fail", node_pubkey)
        print("❌ FAIL: Was able to use destroyed key!")
        return False
    except ValueError as e:
        if "destroyed" in str(e).lower():
            print(f"✅ PASS: Destroyed key rejected: {e}")
            return True
        else:
            print(f"❌ FAIL: Unexpected error: {e}")
            return False


def test_multiple_clients():
    """
    Test 3: Verify multiple clients can encrypt to same node.
    """
    print("\n" + "=" * 70)
    print("TEST 3: Multiple Clients")
    print("=" * 70)
    
    # Single node
    node_crypto = NodeCrypto()
    node_pubkey = node_crypto.get_public_key()
    print(f"\n[Node] Public key: {node_pubkey[:32]}...")
    
    # Multiple clients
    clients = []
    for i in range(3):
        with EphemeralKeyPair() as client:
            message = f"Message from client {i+1}"
            print(f"\n[Client {i+1}] Encrypting: {message}")
            
            encrypted = client.encrypt(message, node_pubkey)
            client_pubkey = client.public_key_b64
            
            # Node decrypts
            decrypted = node_crypto.decrypt_prompt(encrypted, client_pubkey)
            print(f"[Node] Decrypted from client {i+1}: {decrypted}")
            
            # Verify
            if decrypted != message:
                print(f"❌ FAIL: Decryption mismatch for client {i+1}")
                return False
            
            # Node responds
            response = f"Reply to {message}"
            encrypted_response = node_crypto.encrypt_response(response, client_pubkey)
            
            # Client decrypts
            decrypted_response = client.decrypt(encrypted_response, node_pubkey)
            print(f"[Client {i+1}] Received: {decrypted_response}")
            
            if response not in decrypted_response:
                print(f"❌ FAIL: Response mismatch for client {i+1}")
                return False
    
    print("\n✅ PASS: All clients communicated successfully")
    return True


def test_malformed_data():
    """
    Test 4: Verify graceful handling of malformed/malicious data.
    """
    print("\n" + "=" * 70)
    print("TEST 4: Malformed Data Handling")
    print("=" * 70)
    
    node_crypto = NodeCrypto()
    
    test_cases = [
        ("Invalid base64", "not-valid-base64!@#", "fake_pubkey"),
        ("Empty string", "", "fake_pubkey"),
        ("Wrong key", "dmFsaWRiYXNlNjQ=", "aW52YWxpZHB1YmtleQ=="),  # valid base64, wrong key
    ]
    
    all_passed = True
    
    for test_name, encrypted, pubkey in test_cases:
        print(f"\n[Test] {test_name}...")
        try:
            result = node_crypto.decrypt_prompt(encrypted, pubkey)
            print(f"  ❌ FAIL: Should have raised exception, got: {result}")
            all_passed = False
        except ValueError as e:
            print(f"  ✅ PASS: Correctly rejected: {str(e)[:60]}...")
        except Exception as e:
            print(f"  ✅ PASS: Rejected with error: {type(e).__name__}")
    
    return all_passed


def run_all_tests():
    """Run complete Phase 0.5 smoke test suite."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "PHASE 0.5 ENCRYPTION SMOKE TEST" + " " * 21 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    print("This test validates encryption privacy BEFORE implementing networking.")
    print("The goal: Ensure NO PLAINTEXT ever appears in node logs.")
    print()
    
    results = []
    
    # Run tests
    try:
        results.append(("Basic Encryption Privacy", test_encryption_privacy()))
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        results.append(("Basic Encryption Privacy", False))
    
    try:
        results.append(("Key Destruction", test_key_destruction()))
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        results.append(("Key Destruction", False))
    
    try:
        results.append(("Multiple Clients", test_multiple_clients()))
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        results.append(("Multiple Clients", False))
    
    try:
        results.append(("Malformed Data", test_malformed_data()))
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        results.append(("Malformed Data", False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Encryption privacy verified.")
        print("   Safe to proceed with Phase 1 networking implementation.")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED! Fix issues before proceeding.")
        return False


if __name__ == "__main__":
    import sys
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
