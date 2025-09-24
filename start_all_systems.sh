#!/bin/bash

#################################################
# Gauls Trading System - Complete Startup Script
# Starts all required components and monitors status
#################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# System directories
SYSTEM_DIR="/gauls-copy-trading-system"
VENV_PATH="$SYSTEM_DIR/venv"
LOG_DIR="$SYSTEM_DIR/logs"

# Create logs directory if it doesn't exist
mkdir -p $LOG_DIR

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   GAULS TRADING SYSTEM STARTUP${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if process is running
check_process() {
    local script_name=$1
    if pgrep -f "$script_name.*gauls-copy-trading-system" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to start a process
start_process() {
    local script_name=$1
    local description=$2
    local log_file=$3
    
    echo -n -e "${YELLOW}Starting $description...${NC}"
    
    if check_process "$script_name"; then
        echo -e " ${GREEN}[ALREADY RUNNING]${NC}"
        return 0
    fi
    
    cd $SYSTEM_DIR
    source $VENV_PATH/bin/activate
    
    nohup python $script_name > $LOG_DIR/$log_file 2>&1 &
    local pid=$!
    
    sleep 2  # Give process time to start
    
    if check_process "$script_name"; then
        echo -e " ${GREEN}[OK] (PID: $pid)${NC}"
        return 0
    else
        echo -e " ${RED}[FAILED]${NC}"
        echo "Check log: $LOG_DIR/$log_file"
        return 1
    fi
}

# Function to stop all processes
stop_all() {
    echo -e "${YELLOW}Stopping all Gauls trading processes...${NC}"
    
    pkill -f "gauls-copy-trading-system.*\.py" 2>/dev/null || true
    
    sleep 2
    echo -e "${GREEN}All processes stopped.${NC}"
}

# Parse command line arguments
ACTION=${1:-start}

case $ACTION in
    start)
        echo "Starting all Gauls trading system components..."
        echo ""
        
        # Start each component
        start_process "live_telegram_listener.py" "Telegram Message Monitor" "telegram_listener.log"
        start_process "exit_monitor_v2.py" "Exit Condition Monitor" "exit_monitor.log"
        start_process "gauls_copy_trader.py" "Main Copy Trader" "copy_trader.log"
        start_process "gauls_trade_update_processor.py" "Trade Update Handler" "update_processor.log"
        start_process "gauls_dashboard_enhanced.py" "Dashboard Interface" "dashboard.log"
        
        echo ""
        echo -e "${GREEN}Startup complete!${NC}"
        echo ""
        
        # Run health check
        echo "Running system health check..."
        sleep 3
        python3 $SYSTEM_DIR/check_system_health.py
        ;;
        
    stop)
        stop_all
        ;;
        
    restart)
        stop_all
        echo ""
        $0 start
        ;;
        
    status)
        python3 $SYSTEM_DIR/check_system_health.py
        ;;
        
    logs)
        echo -e "${BLUE}Recent logs from all components:${NC}"
        echo ""
        
        for log_file in $LOG_DIR/*.log; do
            if [ -f "$log_file" ]; then
                echo -e "${YELLOW}=== $(basename $log_file) ===${NC}"
                tail -n 10 "$log_file"
                echo ""
            fi
        done
        ;;
        
    monitor)
        # Continuous monitoring mode
        echo -e "${BLUE}Monitoring mode - Press Ctrl+C to exit${NC}"
        echo ""
        
        while true; do
            clear
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}   GAULS TRADING SYSTEM MONITOR${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo ""
            
            # Show process status
            echo -e "${YELLOW}Process Status:${NC}"
            for script in "live_telegram_listener.py" "exit_monitor_v2.py" "gauls_copy_trader.py" "gauls_trade_update_processor.py" "gauls_dashboard_enhanced.py"; do
                if check_process "$script"; then
                    echo -e "  $script: ${GREEN}[RUNNING]${NC}"
                else
                    echo -e "  $script: ${RED}[STOPPED]${NC}"
                fi
            done
            
            echo ""
            echo -e "${YELLOW}Recent Activity:${NC}"
            
            # Show recent trades
            sqlite3 $SYSTEM_DIR/databases/trades.db "SELECT entry_time, symbol, side, status FROM trades ORDER BY id DESC LIMIT 3;" 2>/dev/null || echo "No trades database"
            
            echo ""
            echo "Last update: $(date '+%Y-%m-%d %H:%M:%S')"
            echo "Press Ctrl+C to exit"
            
            sleep 10
        done
        ;;
        
    help)
        echo "Usage: $0 [start|stop|restart|status|logs|monitor|help]"
        echo ""
        echo "Commands:"
        echo "  start    - Start all trading system components"
        echo "  stop     - Stop all trading system components"
        echo "  restart  - Restart all components"
        echo "  status   - Show system health status"
        echo "  logs     - Show recent logs from all components"
        echo "  monitor  - Continuous monitoring mode"
        echo "  help     - Show this help message"
        ;;
        
    *)
        echo -e "${RED}Invalid command: $ACTION${NC}"
        echo "Use: $0 help"
        exit 1
        ;;
esac