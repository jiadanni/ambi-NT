#!/bin/bash
# Ambient Intelligence - Initial Setup Script
# This script helps you configure your node for the first time

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Ambient Intelligence - Node Setup                  ║"
echo "║        Privacy-First Decentralized AI Inference           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed."
    echo "Please install Python 3.11 or higher first."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python 3.11 or higher is required."
    echo "You have Python $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama is not installed."
    echo ""
    echo "Ollama is required to run AI models locally."
    echo "Would you like to install it now? (y/n)"
    read -r install_ollama

    if [ "$install_ollama" = "y" ]; then
        echo "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
        echo "✅ Ollama installed"
    else
        echo "Please install Ollama manually: https://ollama.com/download"
        exit 1
    fi
else
    echo "✅ Ollama found"
fi

echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists."
    echo "Would you like to regenerate it? This will overwrite your existing keys! (y/n)"
    read -r regenerate

    if [ "$regenerate" != "y" ]; then
        echo "Keeping existing .env file."
        echo "Setup complete!"
        exit 0
    fi
fi

echo "Creating .env file..."
cp .env.example .env

# Generate node ID
NODE_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")

# Install node dependencies temporarily to generate keys
echo "Installing dependencies to generate keys..."
cd node
pip install -q PyNaCl

# Generate keypair
echo "Generating cryptographic keypair..."
KEYPAIR_OUTPUT=$(python3 crypto.py | tail -n 2)
NODE_PRIVATE_KEY=$(echo "$KEYPAIR_OUTPUT" | grep "NODE_PRIVATE_KEY" | cut -d'=' -f2)
NODE_PUBLIC_KEY=$(echo "$KEYPAIR_OUTPUT" | grep "NODE_PUBLIC_KEY" | cut -d'=' -f2)

cd ..

# Update .env file
echo "Updating .env file with generated keys..."
sed -i "s/NODE_ID=.*/NODE_ID=$NODE_ID/" .env
sed -i "s/NODE_PRIVATE_KEY=.*/NODE_PRIVATE_KEY=$NODE_PRIVATE_KEY/" .env
sed -i "s/NODE_PUBLIC_KEY=.*/NODE_PUBLIC_KEY=$NODE_PUBLIC_KEY/" .env

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete! ✅                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Your node has been configured with:"
echo "  • Node ID: $NODE_ID"
echo "  • Public Key: ${NODE_PUBLIC_KEY:0:20}..."
echo ""
echo "⚠️  IMPORTANT: Your private key has been saved to .env"
echo "   NEVER share this file or commit it to version control!"
echo ""
echo "Next steps:"
echo "1. Pull an Ollama model: ollama pull llama3:8b"
echo "2. Start Ollama: ollama serve"
echo "3. In another terminal, install node dependencies: cd node && pip install -r requirements.txt"
echo "4. Start the node: python node/server.py"
echo "5. In another terminal, try the client: cd client-cli && pip install -r requirements.txt"
echo "6. Submit a query: python client-cli/client.py 'What is 2+2?'"
echo ""
echo "For detailed instructions, see README.md"
echo ""
