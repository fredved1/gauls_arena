#!/bin/bash

################################################
# Gauls Trading System - SystemD Installation
# Installs and configures all services
################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
SYSTEM_DIR="/gauls-copy-trading-system"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_DIR="$SYSTEM_DIR/systemd"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  GAULS TRADING SYSTEM - SYSTEMD INSTALLATION${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Function to install service
install_service() {
    local service_file=$1
    local service_name=$(basename "$service_file")
    
    echo -n -e "${YELLOW}Installing $service_name...${NC}"
    
    # Copy service file to systemd directory
    cp "$SERVICE_DIR/$service_name" "$SYSTEMD_DIR/"
    
    # Set proper permissions
    chmod 644 "$SYSTEMD_DIR/$service_name"
    
    echo -e " ${GREEN}[OK]${NC}"
}

# Function to stop existing processes
stop_existing() {
    echo -e "${YELLOW}Stopping existing processes...${NC}"
    
    # Kill existing Python processes for Gauls
    pkill -f "gauls-copy-trading-system.*\.py" 2>/dev/null || true
    
    # Stop any existing systemd services
    systemctl stop gauls-trading.target 2>/dev/null || true
    systemctl stop gauls-*.service 2>/dev/null || true
    
    sleep 2
    echo -e "${GREEN}Existing processes stopped${NC}"
}

# Main installation process
main() {
    echo "Starting installation..."
    echo ""
    
    # Step 1: Stop existing processes
    stop_existing
    
    # Step 2: Create necessary directories
    echo -e "${YELLOW}Creating directories...${NC}"
    mkdir -p "$SYSTEM_DIR/logs"
    mkdir -p "$SYSTEM_DIR/databases"
    mkdir -p "$SERVICE_DIR"
    chmod +x "$SERVICE_DIR/watchdog.sh" 2>/dev/null || true
    echo -e "${GREEN}Directories created${NC}"
    
    # Step 3: Install target file
    echo -e "${YELLOW}Installing systemd target...${NC}"
    install_service "gauls-trading.target"
    
    # Step 4: Install service files
    echo -e "${YELLOW}Installing service files...${NC}"
    install_service "gauls-telegram-listener.service"
    install_service "gauls-copy-trader.service"
    install_service "gauls-exit-monitor.service"
    install_service "gauls-update-processor.service"
    install_service "gauls-dashboard.service"
    install_service "gauls-health-monitor.service"
    install_service "gauls-watchdog.service"
    
    # Step 5: Reload systemd daemon
    echo -e "${YELLOW}Reloading systemd daemon...${NC}"
    systemctl daemon-reload
    echo -e "${GREEN}Systemd daemon reloaded${NC}"
    
    # Step 6: Enable services
    echo -e "${YELLOW}Enabling services...${NC}"
    systemctl enable gauls-trading.target
    systemctl enable gauls-telegram-listener.service
    systemctl enable gauls-copy-trader.service
    systemctl enable gauls-exit-monitor.service
    systemctl enable gauls-update-processor.service
    systemctl enable gauls-dashboard.service
    systemctl enable gauls-health-monitor.service
    systemctl enable gauls-watchdog.service
    echo -e "${GREEN}Services enabled${NC}"
    
    # Step 7: Start services
    echo -e "${YELLOW}Starting services...${NC}"
    systemctl start gauls-trading.target
    sleep 5
    echo -e "${GREEN}Services started${NC}"
    
    # Step 8: Check status
    echo ""
    echo -e "${BLUE}SERVICE STATUS:${NC}"
    echo "================================"
    
    services=(
        "gauls-telegram-listener"
        "gauls-copy-trader"
        "gauls-exit-monitor"
        "gauls-update-processor"
        "gauls-dashboard"
        "gauls-watchdog"
    )
    
    all_running=true
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service"; then
            echo -e "$service: ${GREEN}● Running${NC}"
        else
            echo -e "$service: ${RED}● Not Running${NC}"
            all_running=false
        fi
    done
    
    echo ""
    if $all_running; then
        echo -e "${GREEN}✅ All services installed and running successfully!${NC}"
    else
        echo -e "${YELLOW}⚠️ Some services are not running. Check logs for details.${NC}"
    fi
    
    # Show useful commands
    echo ""
    echo -e "${BLUE}USEFUL COMMANDS:${NC}"
    echo "================================"
    echo "View all services status:    systemctl status 'gauls-*'"
    echo "Stop all services:           systemctl stop gauls-trading.target"
    echo "Start all services:          systemctl start gauls-trading.target"
    echo "Restart all services:        systemctl restart gauls-trading.target"
    echo "View logs:                   journalctl -u gauls-copy-trader -f"
    echo "Check system health:         $SYSTEM_DIR/check_system_health.py"
    echo "Monitor dashboard:           $SYSTEM_DIR/system_monitor.py"
    echo ""
    echo "Logs directory:              $SYSTEM_DIR/logs/"
    echo ""
}

# Run if not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi