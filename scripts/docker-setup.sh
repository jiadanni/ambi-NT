#!/bin/bash
# Ambient Intelligence - Docker Setup Script
# Automated one-command deployment for Phase 1

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Ambient Intelligence - Docker Deployment Setup          ║"
echo "║   Phase 1: Trusted Network                                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed."
    echo ""
    echo "Please install Docker first:"
    echo "  Ubuntu/Debian: curl -fsSL https://get.docker.com | sh"
    echo "  macOS: Download from https://www.docker.com/products/docker-desktop"
    echo ""
    exit 1
fi

print_success "Docker found: $(docker --version)"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed."
    echo ""
    echo "Please install Docker Compose:"
    echo "  https://docs.docker.com/compose/install/"
    echo ""
    exit 1
fi

print_success "Docker Compose found"
echo ""

# Check if .env exists
if [ -f .env ]; then
    print_warning ".env file already exists."
    echo "Do you want to regenerate it? This will overwrite your existing keys! (y/n)"
    read -r regenerate

    if [ "$regenerate" != "y" ]; then
        print_info "Using existing .env file."
    else
        rm .env
    fi
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    print_info "Creating .env file from template..."
    cp .env.example .env

    # Generate node ID
    NODE_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))" 2>/dev/null || uuidgen)

    # Install PyNaCl temporarily to generate keys
    print_info "Installing dependencies to generate cryptographic keys..."
    pip3 install -q PyNaCl 2>/dev/null || {
        print_error "Failed to install PyNaCl. Please install it manually:"
        echo "  pip3 install PyNaCl"
        exit 1
    }

    # Generate keypair
    print_info "Generating cryptographic keypair..."
    cd node
    KEYPAIR_OUTPUT=$(python3 crypto.py | tail -n 2)
    NODE_PRIVATE_KEY=$(echo "$KEYPAIR_OUTPUT" | grep "NODE_PRIVATE_KEY" | cut -d'=' -f2)
    NODE_PUBLIC_KEY=$(echo "$KEYPAIR_OUTPUT" | grep "NODE_PUBLIC_KEY" | cut -d'=' -f2)
    cd ..

    # Update .env file
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/NODE_ID=.*/NODE_ID=$NODE_ID/" .env
        sed -i '' "s/NODE_PRIVATE_KEY=.*/NODE_PRIVATE_KEY=$NODE_PRIVATE_KEY/" .env
        sed -i '' "s/NODE_PUBLIC_KEY=.*/NODE_PUBLIC_KEY=$NODE_PUBLIC_KEY/" .env
    else
        # Linux
        sed -i "s/NODE_ID=.*/NODE_ID=$NODE_ID/" .env
        sed -i "s/NODE_PRIVATE_KEY=.*/NODE_PRIVATE_KEY=$NODE_PRIVATE_KEY/" .env
        sed -i "s/NODE_PUBLIC_KEY=.*/NODE_PUBLIC_KEY=$NODE_PUBLIC_KEY/" .env
    fi

    print_success ".env file created with generated keys"
fi

echo ""
print_info "Building Docker images..."
docker-compose build

echo ""
print_success "Build complete!"

echo ""
print_info "Starting services..."
docker-compose up -d

echo ""
print_info "Waiting for services to be ready..."
sleep 5

# Check if node is healthy
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_success "Node is healthy and ready!"
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Deployment Complete! 🚀                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_info "Your Ambient Intelligence node is now running!"
echo ""
echo "Access points:"
echo "  • Node API:    http://localhost:8000"
echo "  • Web Client:  http://localhost:8080"
echo "  • Health:      http://localhost:8000/health"
echo "  • Metrics:     http://localhost:8000/metrics"
echo ""
print_info "Node Information:"
echo "  • Node ID:     $(grep NODE_ID .env | cut -d'=' -f2)"
echo "  • Public Key:  $(grep NODE_PUBLIC_KEY .env | cut -d'=' -f2 | cut -c1-30)..."
echo ""
echo "Commands:"
echo "  • View logs:      docker-compose logs -f"
echo "  • Stop services:  docker-compose down"
echo "  • Restart:        docker-compose restart"
echo "  • Update:         git pull && docker-compose build && docker-compose up -d"
echo ""
print_warning "Important:"
echo "  • Your private key is in .env - NEVER share this file!"
echo "  • The .env file is gitignored - keep it safe"
echo "  • First run will download the Ollama model (may take 5-10 minutes)"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:8080 in your browser"
echo "  2. Enter your question and submit"
echo "  3. Try the voice input feature!"
echo ""
print_success "For detailed documentation, see docs/DEPLOYMENT.md"
echo ""
