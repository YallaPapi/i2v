#!/bin/bash
# VPS Setup Script for i2v
# Run as root on Ubuntu 22.04/24.04

set -e  # Exit on error

echo "=========================================="
echo "  i2v VPS Setup Script"
echo "=========================================="

# Update system
echo "[1/6] Updating system packages..."
apt-get update && apt-get upgrade -y

# Install Docker
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "Docker already installed"
fi

# Install Docker Compose
echo "[3/6] Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    apt-get install -y docker-compose-plugin
else
    echo "Docker Compose already installed"
fi

# Install Git
echo "[4/6] Installing Git..."
apt-get install -y git

# Clone repository
echo "[5/6] Cloning i2v repository..."
cd /opt
if [ -d "i2v" ]; then
    echo "Repository exists, pulling latest..."
    cd i2v
    git pull
else
    git clone https://github.com/YallaPapi/i2v.git
    cd i2v
fi

# Create .env file if it doesn't exist
echo "[6/6] Setting up environment..."
if [ ! -f ".env" ]; then
    echo "Creating .env file - YOU NEED TO EDIT THIS!"
    cat > .env << 'EOF'
# API Keys
FAL_API_KEY=your_fal_api_key
ANTHROPIC_API_KEY=your_anthropic_key

# R2 Storage
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_ENDPOINT=https://your_account_id.r2.cloudflarestorage.com
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_DOMAIN=your_r2_public_domain

# Vast.ai
VAST_API_KEY=your_vast_api_key

# PostgreSQL (auto-configured)
POSTGRES_USER=i2v
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD
POSTGRES_DB=i2v
EOF
    echo ""
    echo "!!! IMPORTANT: Edit /opt/i2v/.env with your actual credentials !!!"
    echo "Run: nano /opt/i2v/.env"
else
    echo ".env file exists"
fi

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env file:  nano /opt/i2v/.env"
echo "  2. Start services:  cd /opt/i2v && docker compose up -d"
echo "  3. Check status:    docker compose ps"
echo "  4. View logs:       docker compose logs -f"
echo ""
echo "App will be available at: http://$(curl -s ifconfig.me)"
echo ""
