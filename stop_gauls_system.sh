#!/bin/bash

# Gauls Copy Trading System Stop Script

echo "=============================================="
echo "🛑 STOPPING GAULS COPY TRADING SYSTEM"
echo "=============================================="

BASE_DIR="/gauls-copy-trading-system"
cd $BASE_DIR

# Kill processes using PID files
if [ -f pids/gauls_copy_trader.pid ]; then
    PID=$(cat pids/gauls_copy_trader.pid)
    kill $PID 2>/dev/null
    echo "✅ Stopped Gauls Copy Trader (PID: $PID)"
    rm pids/gauls_copy_trader.pid
fi

if [ -f pids/telegram_listener.pid ]; then
    PID=$(cat pids/telegram_listener.pid)
    kill $PID 2>/dev/null
    echo "✅ Stopped Telegram Listener (PID: $PID)"
    rm pids/telegram_listener.pid
fi

if [ -f pids/exit_monitor.pid ]; then
    PID=$(cat pids/exit_monitor.pid)
    kill $PID 2>/dev/null
    echo "✅ Stopped Exit Monitor (PID: $PID)"
    rm pids/exit_monitor.pid
fi

if [ -f pids/dashboard.pid ]; then
    PID=$(cat pids/dashboard.pid)
    kill $PID 2>/dev/null
    echo "✅ Stopped Dashboard (PID: $PID)"
    rm pids/dashboard.pid
fi

# Kill any remaining processes
pkill -f "gauls_copy_trader.py"
pkill -f "live_telegram_listener.py"
pkill -f "exit_monitor_v2.py"
pkill -f "gauls_dashboard.py"
pkill -f "gauls_dashboard_enhanced.py"

echo "=============================================="
echo "✅ GAULS COPY TRADING SYSTEM STOPPED"
echo "=============================================="