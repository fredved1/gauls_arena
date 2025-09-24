#!/bin/bash

################################################
# Gauls Trading System Watchdog
# Monitors services and auto-restarts on failure
################################################

# Service list to monitor
SERVICES=(
    "gauls-telegram-listener"
    "gauls-copy-trader"
    "gauls-exit-monitor"
    "gauls-update-processor"
    "gauls-dashboard"
)

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Log function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check and restart service if needed
check_service() {
    local service=$1
    
    if systemctl is-active --quiet "$service"; then
        return 0
    else
        log_message "WARNING: $service is not running. Attempting restart..."
        
        # Try to restart the service
        systemctl restart "$service"
        sleep 5
        
        # Check if restart was successful
        if systemctl is-active --quiet "$service"; then
            log_message "SUCCESS: $service restarted successfully"
            
            # Send alert (you can integrate with notification system)
            echo "[ALERT] Service $service was down and has been restarted" >> /gauls-copy-trading-system/logs/alerts.log
            
            return 0
        else
            log_message "ERROR: Failed to restart $service"
            
            # Try one more time with reset-failed
            systemctl reset-failed "$service"
            systemctl restart "$service"
            sleep 5
            
            if systemctl is-active --quiet "$service"; then
                log_message "SUCCESS: $service restarted after reset-failed"
                return 0
            else
                log_message "CRITICAL: Unable to restart $service after multiple attempts"
                echo "[CRITICAL] Service $service is down and cannot be restarted" >> /gauls-copy-trading-system/logs/alerts.log
                return 1
            fi
        fi
    fi
}

# Health check function
system_health_check() {
    # Check if Python venv is accessible
    if [[ ! -f "/gauls-copy-trading-system/venv/bin/python" ]]; then
        log_message "CRITICAL: Python venv not found!"
        return 1
    fi
    
    # Check database accessibility
    if [[ ! -d "/gauls-copy-trading-system/databases" ]]; then
        log_message "CRITICAL: Databases directory not found!"
        return 1
    fi
    
    # Check if network is up
    if ! ping -c 1 8.8.8.8 &> /dev/null; then
        log_message "WARNING: Network connectivity issue detected"
    fi
    
    return 0
}

# Main monitoring loop
log_message "Starting Gauls Trading System Watchdog..."

while true; do
    # Perform system health check
    if ! system_health_check; then
        log_message "System health check failed. Attempting recovery..."
        
        # Try to recover
        systemctl daemon-reload
        sleep 5
    fi
    
    # Check each service
    failed_services=0
    for service in "${SERVICES[@]}"; do
        if ! check_service "$service"; then
            ((failed_services++))
        fi
    done
    
    # If too many services failed, try full system restart
    if [[ $failed_services -ge 3 ]]; then
        log_message "CRITICAL: Multiple services failed. Attempting full system restart..."
        
        systemctl stop gauls-trading.target
        sleep 10
        systemctl start gauls-trading.target
        
        log_message "Full system restart initiated"
        sleep 30  # Give services time to start
    fi
    
    # Log current status
    if [[ $failed_services -eq 0 ]]; then
        log_message "All services running normally"
    else
        log_message "WARNING: $failed_services service(s) had issues"
    fi
    
    # Wait before next check (30 seconds default)
    sleep 30
done