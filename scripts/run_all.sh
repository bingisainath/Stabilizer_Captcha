#!/bin/bash

###############################################################################
# Reactor Stabilizer - Master Automation Script
# 
# This script:
# 1. Checks dependencies
# 2. Sets up environment
# 3. Starts the Flask application
# 4. Runs all attack bots sequentially
# 5. Collects results and generates report
# 6. Shuts down gracefully

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
VENV_DIR="$PROJECT_ROOT/venv"
PORT=3000
APP_URL="http://localhost:$PORT"
SERVER_PID=""


print_header() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}


check_dependencies() {
    print_header "CHECKING DEPENDENCIES"
    
    local missing_deps=0
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        print_success "Python: $PYTHON_VERSION"
    else
        print_error "Python 3 not found"
        missing_deps=1
    fi
    
    if command -v pip3 &> /dev/null; then
        print_success "pip3: Installed"
    else
        print_error "pip3 not found"
        missing_deps=1
    fi
    
    if command -v google-chrome &> /dev/null || command -v chromium &> /dev/null || command -v chromium-browser &> /dev/null; then
        print_success "Chrome/Chromium: Installed"
    else
        print_warning "Chrome/Chromium not found (required for attackers)"
        print_info "Install with: sudo apt-get install chromium-browser (Linux) or brew install chromium (Mac)"
    fi
    
    if command -v chromedriver &> /dev/null; then
        print_success "ChromeDriver: Installed"
    else
        print_warning "ChromeDriver not found (required for attackers)"
        print_info "Download from: https://chromedriver.chromium.org/"
    fi
    
    if [ $missing_deps -eq 1 ]; then
        print_error "Missing critical dependencies. Please install them first."
        exit 1
    fi
    
    echo ""
}


setup_environment() {
    print_header "SETTING UP ENVIRONMENT"
    
    mkdir -p "$LOG_DIR"
    print_success "Log directory: $LOG_DIR"
    
    if [ ! -d "$VENV_DIR" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    else
        print_success "Virtual environment exists"
    fi
    
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    print_success "Virtual environment activated"
    
    print_info "Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r "$PROJECT_ROOT/requirements.txt"
    print_success "Dependencies installed"
    
    if [ -f "$PROJECT_ROOT/.env" ]; then
        print_success ".env file found"
        export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
    else
        print_warning ".env file not found (using defaults)"
    fi
    
    echo ""
}


start_server() {
    print_header "STARTING FLASK SERVER"
    
    cd "$PROJECT_ROOT"
    
    print_info "Checking for existing processes on port $PORT..."
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        print_warning "Port $PORT is in use, killing existing process..."
        kill -9 $(lsof -t -i:$PORT) 2>/dev/null || true
        sleep 2
    fi
    
    print_info "Starting server on port $PORT..."
    
    export FLASK_APP=run.py
    export FLASK_ENV=development
    export PORT=$PORT
    
    python3 run.py > "$LOG_DIR/app.log" 2>&1 &
    SERVER_PID=$!
    
    print_info "Server PID: $SERVER_PID"
    
    print_info "Waiting for server to start..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$APP_URL" > /dev/null 2>&1; then
            print_success "Server is ready at $APP_URL"
            echo ""
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
        echo -n "."
    done
    
    echo ""
    print_error "Server failed to start within 30 seconds"
    print_info "Check logs: tail -f $LOG_DIR/app.log"
    return 1
}

stop_server() {
    print_header "STOPPING FLASK SERVER"
    
    if [ -n "$SERVER_PID" ] && ps -p $SERVER_PID > /dev/null 2>&1; then
        print_info "Stopping server (PID: $SERVER_PID)..."
        kill $SERVER_PID 2>/dev/null || true
        sleep 2
        
        if ps -p $SERVER_PID > /dev/null 2>&1; then
            print_warning "Force killing server..."
            kill -9 $SERVER_PID 2>/dev/null || true
        fi
        
        print_success "Server stopped"
    else
        print_info "Server not running"
    fi
    
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        print_info "Cleaning up remaining processes on port $PORT..."
        kill -9 $(lsof -t -i:$PORT) 2>/dev/null || true
    fi
    
    echo ""
}


run_attacker() {
    local attacker_name=$1
    local attacker_script=$2
    local log_file="$LOG_DIR/attacker_${attacker_name}.log"
    
    print_header "RUNNING $attacker_name ATTACKER"
    
    print_info "Script: $attacker_script"
    print_info "Log: $log_file"
    print_info "Target: $APP_URL"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    if [ "$attacker_name" == "gemini" ] && [ -z "$GEMINI_API_KEY" ]; then
        print_warning "GEMINI_API_KEY not set, skipping Gemini attacker"
        echo "Result: SKIPPED (no API key)" > "$log_file"
        return 2
    fi
    
    timeout 180 python3 "$attacker_script" "$APP_URL" > "$log_file" 2>&1
    local exit_code=$?
    
    echo ""
    
    if [ $exit_code -eq 0 ]; then
        print_error "$attacker_name SUCCEEDED (unexpected!)"
        return 0
    elif [ $exit_code -eq 124 ]; then
        print_warning "$attacker_name TIMEOUT (180s)"
        return 124
    else
        print_success "$attacker_name FAILED (expected)"
        return 1
    fi
}

run_all_attackers() {
    print_header "RUNNING ALL ATTACKERS"
    
    local results=()
    
    run_attacker "RL" "attackers/attacker_rl.py" >&2
    results+=("RL:$?")
    sleep 2
    
    run_attacker "PID" "attackers/attacker_pid.py" >&2
    results+=("PID:$?")
    sleep 2
    
    run_attacker "Gemini" "attackers/attacker_gemini.py" >&2
    results+=("Gemini:$?")
    
    echo "${results[@]}"
}


generate_report() {
    local results=("$@")
    
    print_header "TEST SUMMARY"
    
    local total=0
    local failed=0
    local succeeded=0
    local skipped=0
    local timeout=0
    
    for result in "${results[@]}"; do
        IFS=':' read -r name code <<< "$result"
        total=$((total + 1))
        
        case $code in
            0)
                print_error "  $name: SUCCEEDED (unexpected breach!)"
                succeeded=$((succeeded + 1))
                ;;
            1)
                print_success "  $name: FAILED (expected)"
                failed=$((failed + 1))
                ;;
            2)
                print_warning "  $name: SKIPPED"
                skipped=$((skipped + 1))
                ;;
            124)
                print_warning "  $name: TIMEOUT"
                timeout=$((timeout + 1))
                ;;
            *)
                print_warning "  $name: UNKNOWN ($code)"
                ;;
        esac
    done
    
    echo ""
    print_info "Total Attackers: $total"
    print_success "Failed (Expected): $failed"
    print_error "Succeeded (Breach): $succeeded"
    print_warning "Skipped: $skipped"
    print_warning "Timeout: $timeout"
    echo ""
    
    if [ $succeeded -eq 0 ]; then
        print_success "✓ ALL ATTACKERS DEFEATED - SYSTEM SECURE"
        return 0
    else
        print_error "✗ SECURITY BREACH DETECTED - $succeeded ATTACKER(S) SUCCEEDED"
        return 1
    fi
}


cleanup() {
    print_header "CLEANUP"
    
    stop_server
    
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate 2>/dev/null || true
        print_success "Virtual environment deactivated"
    fi
    
    print_info "Logs saved in: $LOG_DIR"
    print_info "Review with: ls -lh $LOG_DIR"
    echo ""
}


trap cleanup EXIT
trap 'print_error "Interrupted by user"; cleanup; exit 130' INT TERM


main() {
    clear
    
    print_header "REACTOR STABILIZER - AUTOMATED TEST SUITE"
    echo ""
    
    check_dependencies
    
    setup_environment
    
    if ! start_server; then
        print_error "Failed to start server"
        exit 1
    fi
    
    results=($(run_all_attackers))
    
    echo ""
    generate_report "${results[@]}"
    exit_code=$?
    
    cleanup
    
    exit $exit_code
}


case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --check-deps   Only check dependencies"
        echo ""
        echo "Description:"
        echo "  Automated test suite for Reactor Stabilizer CAPTCHA system"
        echo "  Runs all attack bots and verifies system security"
        echo ""
        exit 0
        ;;
    --check-deps)
        check_dependencies
        exit 0
        ;;
    *)
        main
        ;;
esac