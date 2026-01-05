#!/bin/bash
# Phinan Finance Suite - Oracle Cloud VM Deployment Script
# Run with: sudo bash scripts/deploy_oracle.sh
#
# Prerequisites:
#   1. Oracle Cloud VM (Ubuntu 22.04 or Oracle Linux 8/9 recommended)
#   2. VCN Security List: Allow TCP 80 and 443 from 0.0.0.0/0
#   3. Git clone this repo to the VM

set -e

echo "=== Phinan Oracle Cloud Deployment ==="
echo ""

# --- Detect OS ---
if [ -f /etc/oracle-release ] || [ -f /etc/redhat-release ]; then
    PKG_MANAGER="dnf"
    FIREWALL_CMD="firewalld"
elif [ -f /etc/debian_version ]; then
    PKG_MANAGER="apt"
    FIREWALL_CMD="iptables"
else
    echo "Unsupported OS. Please install Docker manually."
    exit 1
fi

# --- Install Docker ---
echo "[1/4] Installing Docker..."
if ! command -v docker &> /dev/null; then
    if [ "$PKG_MANAGER" = "apt" ]; then
        apt-get update
        apt-get install -y docker.io docker-compose-plugin
        systemctl enable --now docker
    else
        dnf install -y dnf-plugins-core
        dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        systemctl enable --now docker
    fi
    echo "Docker installed."
else
    echo "Docker already installed."
fi

# --- Fix Oracle Cloud Firewall (iptables) ---
# Oracle Cloud VMs have iptables rules that block traffic even if VCN allows it
echo "[2/4] Configuring local firewall (iptables)..."
if [ "$PKG_MANAGER" = "apt" ]; then
    # Ubuntu: modify iptables directly
    iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
    iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
    # Persist rules
    if command -v netfilter-persistent &> /dev/null; then
        netfilter-persistent save
    else
        apt-get install -y iptables-persistent
        netfilter-persistent save
    fi
else
    # Oracle Linux: use firewalld
    systemctl enable --now firewalld
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
fi
echo "Firewall configured for ports 80 and 443."

# --- Create .env if missing ---
echo "[3/4] Checking .env file..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Created .env from .env.example. Please edit it with your API keys!"
    else
        echo "WARNING: No .env file found. Create one with your API keys."
    fi
else
    echo ".env file exists."
fi

# --- Deploy with Docker Compose ---
echo "[4/4] Building and starting containers..."
docker compose up -d --build

echo ""
echo "=== Deployment Complete ==="
echo "Your app should be running at http://$(curl -s ifconfig.me)"
echo ""
echo "Next steps:"
echo "  1. Point your domain's A record to this IP."
echo "  2. Update API_URL in .env to https://yourdomain.com"
echo "  3. Redeploy: docker compose up -d --build"
echo ""
