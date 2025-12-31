
#!/bin/bash

set -e

echo "================================================="
echo "Trading Hydra System Installation Script"
echo "For Linux Mint VM Environment"
echo "================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root. Please run as a regular user."
fi

log "Updating system packages..."
sudo apt update && sudo apt upgrade -y

log "Installing system dependencies..."
sudo apt install -y \
    curl \
    wget \
    git \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    jq \
    libyaml-dev \
    libssl-dev \
    libffi-dev \
    python3-dev \
    python3-pip \
    python3-venv \
    sqlite3 \
    libsqlite3-dev

# Install Python 3.11 (required by pyproject.toml)
log "Installing Python 3.11..."
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3.11-pip

# Make Python 3.11 default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/python3.11 -m pip 1

# Install Node.js 22 (required by .replit config)
log "Installing Node.js 22..."
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Verify Node.js version
NODE_VERSION=$(node --version)
log "Node.js version installed: $NODE_VERSION"

# Install PostgreSQL 16
log "Installing PostgreSQL 16..."
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-16 postgresql-contrib-16 postgresql-client-16

# Install pgvector extension for PostgreSQL (needed for Mastra memory)
log "Installing pgvector extension..."
sudo apt install -y postgresql-16-pgvector

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Set up PostgreSQL user and database
log "Setting up PostgreSQL database..."
sudo -u postgres createuser --interactive --pwprompt tradinghydra || warn "User may already exist"
sudo -u postgres createdb -O tradinghydra trading_hydra_db || warn "Database may already exist"

# Enable pgvector extension
sudo -u postgres psql -d trading_hydra_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Install UV (Python package manager used by Replit)
log "Installing UV package manager..."
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.cargo/env

# Install Inngest CLI (for workflow durability)
log "Installing Inngest CLI..."
curl -sfL https://inngest.com/install.sh | sudo sh

# Create project directory
PROJECT_DIR="$HOME/trading_hydra"
log "Creating project directory at $PROJECT_DIR..."
mkdir -p "$PROJECT_DIR"

log "Setting up environment variables..."
cat > "$PROJECT_DIR/.env.example" << 'EOF'
# Alpaca Trading API Keys
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Database Configuration
DATABASE_URL=postgresql://tradinghydra:your_password@localhost:5432/trading_hydra_db

# Development Settings
ENVIRONMENT=development
LOG_LEVEL=INFO

# Mastra Configuration (optional)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Risk Management
MAX_DAILY_RISK=0.02
MAX_POSITION_SIZE=0.05
ENABLE_PAPER_TRADING=true
EOF

log "Creating systemd service file..."
sudo tee /etc/systemd/system/trading-hydra.service > /dev/null << EOF
[Unit]
Description=Trading Hydra Automated Trading System
After=network.target postgresql.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$PROJECT_DIR
Environment=PATH=/home/$(whoami)/.cargo/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

log "Creating startup script..."
cat > "$PROJECT_DIR/start_trading_hydra.sh" << 'EOF'
#!/bin/bash

# Activate environment and start Trading Hydra
cd "$(dirname "$0")"

echo "Starting Trading Hydra System..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from .env.example"
    cp .env.example .env
    echo "Please edit .env with your actual API keys before running the system!"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
uv sync

# Start the system
echo "Starting Trading Hydra..."
python3 main.py
EOF

chmod +x "$PROJECT_DIR/start_trading_hydra.sh"

log "Creating development server startup script..."
cat > "$PROJECT_DIR/start_dev_server.sh" << 'EOF'
#!/bin/bash

cd "$(dirname "$0")"

echo "Starting Development Environment..."

# Start Inngest server in background
echo "Starting Inngest server..."
inngest-cli dev -u http://localhost:5000/api/inngest --host 0.0.0.0 --port 3000 &

# Start main application
echo "Starting Trading Hydra application..."
python3 main.py
EOF

chmod +x "$PROJECT_DIR/start_dev_server.sh"

log "Setting up firewall rules..."
sudo ufw allow 3000/tcp  # Inngest
sudo ufw allow 5000/tcp  # Main app
sudo ufw allow 5432/tcp  # PostgreSQL

log "Creating log rotation configuration..."
sudo tee /etc/logrotate.d/trading-hydra > /dev/null << EOF
$PROJECT_DIR/logs/*.log $PROJECT_DIR/logs/*.jsonl {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $(whoami) $(whoami)
}
EOF

# Create basic project structure if it doesn't exist
log "Setting up project structure..."
mkdir -p "$PROJECT_DIR"/{config,logs,src,state,tests}

log "Installing global npm packages..."
sudo npm install -g typescript ts-node nodemon

echo ""
echo "================================================="
echo "Installation Complete!"
echo "================================================="
echo ""
echo "Next steps:"
echo "1. Copy your Trading Hydra project files to: $PROJECT_DIR"
echo "2. Edit $PROJECT_DIR/.env with your actual API keys"
echo "3. Install Python dependencies: cd $PROJECT_DIR && uv sync"
echo "4. Test the connection: python3 test_alpaca_connection.py"
echo "5. Start the system: ./start_trading_hydra.sh"
echo ""
echo "System service commands:"
echo "- Enable service: sudo systemctl enable trading-hydra"
echo "- Start service: sudo systemctl start trading-hydra"
echo "- Check status: sudo systemctl status trading-hydra"
echo "- View logs: sudo journalctl -u trading-hydra -f"
echo ""
echo "Development:"
echo "- Start dev server: ./start_dev_server.sh"
echo "- Inngest UI: http://localhost:3000"
echo "- Main app: http://localhost:5000"
echo ""
echo "PostgreSQL connection string:"
echo "postgresql://tradinghydra:your_password@localhost:5432/trading_hydra_db"
echo ""
warn "Remember to set strong passwords and secure your API keys!"
log "Installation script completed successfully."
EOF
