#!/bin/bash

###############################################################################
# Reactor Stabilizer - Quick Setup Script
# 
# This script sets up the project for first-time use
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}   Reactor Stabilizer - Quick Setup${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# 1. Check Python
echo "Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi
echo -e "${GREEN}✓ Python found: $(python3 --version)${NC}"

# 2. Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# 3. Activate and install dependencies
echo ""
echo "Installing dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# 4. Create .env file
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/your-secret-key-here-generate-with-secrets.token_hex(32)/$SECRET_KEY/" .env
    else
        sed -i "s/your-secret-key-here-generate-with-secrets.token_hex(32)/$SECRET_KEY/" .env
    fi
    
    echo -e "${GREEN}✓ .env file created with generated SECRET_KEY${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

echo ""
echo "Creating logs directory..."
mkdir -p logs
echo -e "${GREEN}✓ Logs directory created${NC}"

echo ""
echo "Making scripts executable..."
chmod +x scripts/*.sh
echo -e "${GREEN}✓ Scripts are executable${NC}"

echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start the application:"
echo -e "     ${GREEN}python run.py${NC}"
echo ""
echo "  2. Or run the full test suite:"
echo -e "     ${GREEN}./scripts/run_all.sh${NC}"
echo ""
echo "  3. Open browser:"
echo -e "     ${GREEN}http://localhost:3000${NC}"