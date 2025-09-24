#!/bin/bash

# Gauls Copy Trading System Startup Script

echo "=============================================="
echo "🚀 STARTING GAULS COPY TRADING SYSTEM"
echo "=============================================="

# Set the base directory
BASE_DIR="/gauls-copy-trading-system"
cd $BASE_DIR

# Kill any existing processes
echo "⏹️ Stopping any existing processes..."
pkill -f "gauls_copy_trader.py"
pkill -f "live_telegram_listener.py"
pkill -f "exit_monitor_v2.py"
sleep 2

# Set environment variables
export TRADING_MODE=${1:-experimental}  # Default to experimental, pass 'production' as first arg for real trading
echo "📊 Trading Mode: $TRADING_MODE"

if [ "$TRADING_MODE" == "production" ]; then
    echo "🔴 WARNING: PRODUCTION MODE - REAL MONEY TRADING!"
    echo "Press Ctrl+C in next 5 seconds to cancel..."
    sleep 5
fi

# Start Telegram Listener
echo "📡 Starting Telegram Listener..."
nohup $BASE_DIR/venv/bin/python live_telegram_listener.py > logs/telegram_listener.log 2>&1 &
echo $! > pids/telegram_listener.pid

# Start Gauls Copy Trader
echo "💰 Starting Gauls Copy Trader..."
nohup $BASE_DIR/venv/bin/python gauls_copy_trader.py > logs/gauls_copy_trader.log 2>&1 &
echo $! > pids/gauls_copy_trader.pid

# Start Exit Monitor
echo "🎯 Starting Exit Monitor V2..."
nohup $BASE_DIR/venv/bin/python exit_monitor_v2.py > logs/exit_monitor.log 2>&1 &
echo $! > pids/exit_monitor.pid

# Start Dashboard (Enhanced with Exchange Integration)
echo "🖥️ Starting Enhanced Gauls Dashboard with Exchange Integration..."
nohup $BASE_DIR/venv/bin/python gauls_dashboard_enhanced.py > logs/dashboard.log 2>&1 &
echo $! > pids/dashboard.pid

sleep 3

echo "=============================================="
echo "✅ GAULS COPY TRADING SYSTEM STARTED"
echo "=============================================="
echo ""
echo "📋 Monitor logs:"
echo "  tail -f logs/gauls_copy_trader.log"
echo "  tail -f logs/telegram_listener.log"
echo "  tail -f logs/exit_monitor.log"
echo ""
echo "🖥️ Dashboard:"
echo "  http://localhost:7777"
echo ""
echo "📊 Check status:"
echo "  ./monitor_gauls_system.sh"
echo ""
echo "🛑 Stop system:"
echo "  ./stop_gauls_system.sh"
echo "=============================================="