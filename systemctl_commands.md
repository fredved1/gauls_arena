# Gauls Trading System - SystemD Commands Reference

## Installation
```bash
# Install all services (run once)
sudo /gauls-copy-trading-system/install_systemd.sh
```

## Basic Controls

### Start/Stop/Restart All Services
```bash
# Start entire system
sudo systemctl start gauls-trading.target

# Stop entire system  
sudo systemctl stop gauls-trading.target

# Restart entire system
sudo systemctl restart gauls-trading.target

# Check overall status
sudo systemctl status gauls-trading.target
```

### Individual Service Control
```bash
# Start specific service
sudo systemctl start gauls-copy-trader
sudo systemctl start gauls-telegram-listener
sudo systemctl start gauls-exit-monitor
sudo systemctl start gauls-update-processor
sudo systemctl start gauls-dashboard

# Stop specific service
sudo systemctl stop gauls-copy-trader

# Restart specific service
sudo systemctl restart gauls-copy-trader

# Check service status
sudo systemctl status gauls-copy-trader
```

## Monitoring

### View Logs
```bash
# Follow logs for specific service
sudo journalctl -u gauls-copy-trader -f

# View last 100 lines
sudo journalctl -u gauls-copy-trader -n 100

# View logs since last boot
sudo journalctl -u gauls-copy-trader -b

# View all Gauls services logs
sudo journalctl -u 'gauls-*' -f

# View logs with timestamps
sudo journalctl -u gauls-copy-trader --since "2025-01-01 00:00:00"
```

### Check Service Status
```bash
# Quick status of all services
sudo systemctl status 'gauls-*'

# List all Gauls services
sudo systemctl list-units 'gauls-*'

# Check failed services
sudo systemctl --failed | grep gauls
```

## Troubleshooting

### Reset Failed Services
```bash
# Reset failed state
sudo systemctl reset-failed gauls-copy-trader

# Force reload configuration
sudo systemctl daemon-reload

# Restart after reset
sudo systemctl restart gauls-copy-trader
```

### Disable/Enable Services
```bash
# Disable service (won't start on boot)
sudo systemctl disable gauls-dashboard

# Enable service (will start on boot)
sudo systemctl enable gauls-dashboard
```

### Kill Stuck Processes
```bash
# Kill all Gauls Python processes
sudo pkill -f "gauls-copy-trading-system.*\.py"

# Force kill
sudo pkill -9 -f "gauls-copy-trading-system.*\.py"
```

## Health Checks

### System Health
```bash
# Run health check
/gauls-copy-trading-system/check_system_health.py

# Monitor live status
/gauls-copy-trading-system/system_monitor.py

# Check watchdog logs
sudo journalctl -u gauls-watchdog -f
```

### Resource Usage
```bash
# Check CPU/Memory usage
sudo systemctl status gauls-copy-trader | grep Memory

# Show resource consumption
systemd-cgtop
```

## Auto-Restart Configuration

All services are configured with:
- **Restart=always**: Automatically restart on failure
- **RestartSec=10**: Wait 10 seconds before restart
- **StartLimitBurst=5**: Max 5 restarts in StartLimitInterval
- **StartLimitInterval=60s**: Reset counter after 60 seconds

The watchdog service monitors all components and will:
1. Check every 30 seconds
2. Restart individual failed services
3. Perform full system restart if 3+ services fail

## Emergency Commands

### Full System Reset
```bash
# Stop everything
sudo systemctl stop gauls-trading.target

# Clear logs
sudo rm -rf /gauls-copy-trading-system/logs/*

# Reset all failed states
sudo systemctl reset-failed 'gauls-*'

# Reload daemon
sudo systemctl daemon-reload

# Start everything
sudo systemctl start gauls-trading.target
```

### Check Boot Configuration
```bash
# Verify services will start on boot
sudo systemctl is-enabled gauls-trading.target
sudo systemctl list-dependencies gauls-trading.target
```

## Service Dependencies

The services start in this order:
1. `gauls-trading.target` (master target)
2. `gauls-telegram-listener` (message receiver)
3. `gauls-copy-trader` (main trader)
4. `gauls-exit-monitor` (SL/TP monitor)
5. `gauls-update-processor` (1R/2R handler)
6. `gauls-dashboard` (web interface)
7. `gauls-watchdog` (auto-recovery)

## Important Files

- Service files: `/etc/systemd/system/gauls-*.service`
- Logs: `/gauls-copy-trading-system/logs/`
- Health logs: `/gauls-copy-trading-system/logs/health.log`
- Alert logs: `/gauls-copy-trading-system/logs/alerts.log`
- Watchdog script: `/gauls-copy-trading-system/systemd/watchdog.sh`