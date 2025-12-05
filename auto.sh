# This is the master automation script for the Reactor Stabilizer project
# Authors: Keshwith Pyla (pylak)

VENV_DIR="venv"
PORT=3000
SERVER_PID=""

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(dirname "$0")"

setup_environment() {
    echo -e "${BLUE}[*] Checking system environment...${NC}"
    
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}[!] Error: python3 is not installed.${NC}"
        exit 1
    fi

    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}[*] Creating virtual environment ($VENV_DIR)...${NC}"
        python3 -m venv "$VENV_DIR"
    fi

    source "$VENV_DIR/bin/activate"

    echo -e "${YELLOW}[*] Checking dependencies...${NC}"
    if [ -f "requirements.txt" ]; then
        pip install -q -r requirements.txt
        pip install -q google-generativeai
    fi

    if [ ! -f ".env" ]; then
        echo "GEMINI_API_KEY=your_api_key_here" > .env
        echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
        echo -e "${YELLOW}[!] Created .env file. Add your API Key to run the Gemini attacker.${NC}"
    fi
}

start_server_bg() {
    echo -e "${BLUE}[*] Starting Flask Server (Port $PORT)...${NC}"
    export PORT=$PORT
    python app.py > logs/server_output.log 2>&1 &
    SERVER_PID=$!
    
    echo -e "${YELLOW}[*] Waiting for server...${NC}"
    for i in {1..30}; do
        if lsof -i :$PORT > /dev/null; then
            echo -e "${GREEN}[+] Server is UP.${NC}"
            return 0
        fi
        sleep 1
    done
    
    echo -e "${RED}[!] Server failed to start.${NC}"
    exit 1
}

stop_server() {
    if [ -n "$SERVER_PID" ]; then
        echo -e "${BLUE}[*] Shutting down server (PID: $SERVER_PID)...${NC}"
        kill $SERVER_PID 2>/dev/null
        wait $SERVER_PID 2>/dev/null
    fi
}

cleanup() {
    stop_server
    echo -e "${GREEN}[*] Automation complete.${NC}"
    exit 0
}

trap cleanup SIGINT EXIT


setup_environment
start_server_bg

echo -e "\n${GREEN}=== 1. Running PID Attacker (Mechanical Bot) ===${NC}"
python attackers/attacker_pid.py
echo -e "${BLUE}[*] PID Attack complete.${NC}"
sleep 2

echo -e "\n${GREEN}=== 2. Running RL Attacker (Q-Learning Bot) ===${NC}"
(cd attackers && python attacker_rl.py)
echo -e "${BLUE}[*] RL Attack complete.${NC}"
sleep 2


echo -e "\n${GREEN}=== 3. Running Gemini Attacker (AI Vision Bot) ===${NC}"
if grep -q "your_api_key_here" .env; then
    echo -e "${RED}[!] SKIPPING: GEMINI_API_KEY not set in .env file.${NC}"
else
    python attackers/attacker_gemini.py
fi
echo -e "${BLUE}[*] Gemini Attack complete.${NC}"

