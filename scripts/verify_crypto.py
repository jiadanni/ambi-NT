#!/usr/bin/env python3
"""
Verify that cryptographic operations work correctly.

This script can be run without Ollama to verify the core encryption
functionality is working.
"""

import sys
import os
import importlib.util

def load_module_from_file(module_name, file_path):
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Ambient Intelligence - Crypto Verification             ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    # Get paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    node_crypto_path = os.path.join(parent_dir, 'node', 'crypto.py')
    client_crypto_path = os.path.join(parent_dir, 'client-cli', 'crypto.py')

    # Load modules
    try:
        print("Loading crypto modules...")
        node_crypto = load_module_from_file('node_crypto', node_crypto_path)
        client_crypto = load_module_from_file('client_crypto', client_crypto_path)

        NodeCrypto = node_crypto.NodeCrypto
        generate_keypair = node_crypto.generate_keypair
        ClientCrypto = client_crypto.ClientCrypto

        print("✅ Modules loaded successfully")
    except Exception as e:
        print(f"❌ Error loading modules: {e}")
        print("\nPlease ensure:")
        print("  1. You're in the project root directory")
        print("  2. Dependencies are installed:")
        print("     cd node && pip install -r requirements.txt")
        print("     cd client-cli && pip install -r requirements.txt")
        return 1

    print()

    # Test 1: Generate keypair
    print("Test 1: Generating node keypair...")
    try:
        priv, pub = generate_keypair()
        print(f"  Private key: {priv[:20]}...")
        print(f"  Public key:  {pub[:20]}...")
        print("  ✅ Keypair generation works")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return 1

    print()

    # Test 2: Create node and client
    print("Test 2: Creating node and client instances...")
    try:
        node = NodeCrypto()
        client = ClientCrypto()
        print(f"  Node public key:   {node.get_public_key()[:20]}...")
        print(f"  Client public key: {client.get_public_key_b64()[:20]}...")
        print("  ✅ Instances created successfully")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return 1

    print()

    # Test 3: Encrypt/decrypt round-trip
    print("Test 3: Testing encryption round-trip...")
    try:
        test_message = "Hello, Ambient Intelligence! 🚀"
        print(f"  Original message: {test_message}")

        # Client encrypts for node
        encrypted = client.encrypt_for_node(test_message, node.get_public_key())
        print(f"  Encrypted: {encrypted[:40]}...")

        # Node decrypts
        decrypted = node.decrypt_prompt(encrypted, client.get_public_key_b64())
        print(f"  Decrypted: {decrypted}")

        if decrypted == test_message:
            print("  ✅ Encryption/decryption works!")
        else:
            print(f"  ❌ Decryption failed: got '{decrypted}'")
            return 1
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()

    # Test 4: Node encrypts response
    print("Test 4: Testing response encryption...")
    try:
        response = "The answer is 42."
        print(f"  Original response: {response}")

        # Node encrypts response
        encrypted_response = node.encrypt_response(response, client.get_public_key_b64())
        print(f"  Encrypted: {encrypted_response[:40]}...")

        # Client decrypts
        decrypted_response = client.decrypt_from_node(encrypted_response, node.get_public_key())
        print(f"  Decrypted: {decrypted_response}")

        if decrypted_response == response:
            print("  ✅ Response encryption works!")
        else:
            print(f"  ❌ Decryption failed: got '{decrypted_response}'")
            return 1
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()

    # Test 5: Security - wrong key fails
    print("Test 5: Testing security (wrong key should fail)...")
    try:
        other_client = ClientCrypto()
        message = "Secret message"

        encrypted = client.encrypt_for_node(message, node.get_public_key())

        try:
            # Try to decrypt with wrong key
            node.decrypt_prompt(encrypted, other_client.get_public_key_b64())
            print("  ❌ Security failure: decryption with wrong key succeeded!")
            return 1
        except ValueError:
            print("  ✅ Decryption with wrong key correctly failed")
    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        return 1

    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║              All Tests Passed! ✅                          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("Your cryptographic setup is working correctly!")
    print()
    print("Next steps:")
    print("1. Install Ollama: https://ollama.com/download")
    print("2. Pull a model: ollama pull llama3:8b")
    print("3. Start Ollama: ollama serve")
    print("4. Start the node: python node/server.py")
    print("5. Test with client: python client-cli/client.py 'What is 2+2?'")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
