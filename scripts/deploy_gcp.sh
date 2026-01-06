#!/bin/bash
# =============================================================================
# Phinan Finance Suite - GCP Deployment Script
# Target: Google Compute Engine e2-micro (Debian/Ubuntu)
# =============================================================================
set -euo pipefail

echo "=============================================="
echo "Phinan Finance Suite - GCP Setup"
echo "=============================================="

# -----------------------------------------------------------------------------
# 1. System Update
# -----------------------------------------------------------------------------
echo "[1/6] Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# -----------------------------------------------------------------------------
# 2. Install Docker
# -----------------------------------------------------------------------------
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "  -> Docker installed. You may need to log out and back in for group changes."
else
    echo "  -> Docker already installed."
fi

# -----------------------------------------------------------------------------
# 3. Install Docker Compose (v2 plugin)
# -----------------------------------------------------------------------------
echo "[3/6] Installing Docker Compose..."
if ! docker compose version &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
    echo "  -> Docker Compose plugin installed."
else
    echo "  -> Docker Compose already installed."
fi

# -----------------------------------------------------------------------------
# 4. Setup Swap File (2GB)
# -----------------------------------------------------------------------------
echo "[4/6] Configuring 2GB Swap File..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "  -> Swap file created and enabled."
else
    echo "  -> Swap file already exists."
fi

# Verify swap
echo "  -> Current memory status:"
free -h

# -----------------------------------------------------------------------------
# 5. Configure Firewall (allow HTTP/HTTPS)
# -----------------------------------------------------------------------------
echo "[5/6] Configuring firewall rules..."
# GCE uses its own firewall, but if ufw is active:
if command -v ufw &> /dev/null && sudo ufw status | grep -q "active"; then
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    echo "  -> UFW rules added for ports 80 and 443."
else
    echo "  -> UFW not active (using GCE firewall rules instead)."
fi

# -----------------------------------------------------------------------------
# 6. Create App Directory & Set Permissions
# -----------------------------------------------------------------------------
echo "[6/6] Setting up application directory..."
APP_DIR="/opt/phinan"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR
echo "  -> Created $APP_DIR"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "Setup Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Clone or copy your project to $APP_DIR"
echo "  2. Create .env file with your API keys"
echo "  3. Pull your Docker image:"
echo "       docker pull <your-dockerhub-user>/phinan:latest"
echo "  4. Or build locally and push, then pull here"
echo "  5. Start the app:"
echo "       cd $APP_DIR && docker compose up -d"
echo ""
echo "For HTTPS, set these in your .env:"
echo "  DOMAIN=yourdomain.com"
echo "  API_URL=https://yourdomain.com"
echo ""
echo "Monitor with:"
echo "  docker compose logs -f"
echo "  htop"
echo ""
