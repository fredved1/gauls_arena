#!/bin/bash

# Gauls Copy Trading System Monitor Script

clear
echo "=============================================="
echo "📊 GAULS COPY TRADING SYSTEM STATUS"
echo "=============================================="
echo "📅 $(date)"
echo ""

BASE_DIR="/gauls-copy-trading-system"
cd $BASE_DIR

# Check processes
echo "🔍 PROCESS STATUS:"
echo "-------------------"

# Gauls Copy Trader
if pgrep -f "gauls_copy_trader.py" > /dev/null; then
    PID=$(pgrep -f "gauls_copy_trader.py")
    echo "✅ Gauls Copy Trader (PID: $PID)"
else
    echo "❌ Gauls Copy Trader (NOT RUNNING)"
fi

# Telegram Listener
if pgrep -f "live_telegram_listener.py" > /dev/null; then
    PID=$(pgrep -f "live_telegram_listener.py")
    echo "✅ Telegram Listener (PID: $PID)"
else
    echo "❌ Telegram Listener (NOT RUNNING)"
fi

# Exit Monitor
if pgrep -f "exit_monitor_v2.py" > /dev/null; then
    PID=$(pgrep -f "exit_monitor_v2.py")
    echo "✅ Exit Monitor V2 (PID: $PID)"
else
    echo "❌ Exit Monitor V2 (NOT RUNNING)"
fi

echo ""
echo "💾 DATABASE STATUS:"
echo "-------------------"

# Check trades
if [ -f "databases/trades.db" ]; then
    OPEN_TRADES=$(sqlite3 databases/trades.db "SELECT COUNT(*) FROM trades WHERE status='open';" 2>/dev/null || echo "0")
    TOTAL_TRADES=$(sqlite3 databases/trades.db "SELECT COUNT(*) FROM trades;" 2>/dev/null || echo "0")
    echo "📈 Open Trades: $OPEN_TRADES"
    echo "📊 Total Trades: $TOTAL_TRADES"
fi

# Check messages
if [ -f "databases/gauls_trading.db" ]; then
    MESSAGES=$(sqlite3 databases/gauls_trading.db "SELECT COUNT(*) FROM gauls_messages;" 2>/dev/null || echo "0")
    UPDATES=$(sqlite3 databases/gauls_trading.db "SELECT COUNT(*) FROM trade_updates;" 2>/dev/null || echo "0")
    echo "💬 Gauls Messages: $MESSAGES"
    echo "🔄 Trade Updates: $UPDATES"
fi

echo ""
echo "📁 LOG FILES:"
echo "-------------------"
for log in logs/*.log; do
    if [ -f "$log" ]; then
        SIZE=$(du -h "$log" | cut -f1)
        LINES=$(tail -1 "$log" | cut -c1-60)
        echo "$(basename $log): $SIZE - $LINES..."
    fi
done

echo ""
echo "🎯 RECENT ACTIVITY:"
echo "-------------------"
if [ -f "logs/gauls_copy_trader.log" ]; then
    echo "Last 5 Gauls trades:"
    grep -E "signal|Signal|TRADE|Trade" logs/gauls_copy_trader.log | tail -5 | cut -c1-80
fi

echo ""
echo "=============================================="
echo "💡 Commands:"
echo "  View logs: tail -f logs/gauls_copy_trader.log"
echo "  Check trades: sqlite3 databases/trades.db 'SELECT * FROM trades;'"
echo "  Stop system: ./stop_gauls_system.sh"
echo "=============================================="