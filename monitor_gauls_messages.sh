#!/bin/bash
echo "📊 Monitoring Gauls Message System Status"
echo "========================================="
echo ""

# Check listener
if pgrep -f "live_telegram_listener.py" > /dev/null; then
    echo "✅ Telegram Listener: RUNNING (PID: $(pgrep -f "live_telegram_listener.py"))"
else
    echo "❌ Telegram Listener: NOT RUNNING"
fi

# Check dashboard
if pgrep -f "gauls_dashboard_enhanced.py" > /dev/null; then
    echo "✅ Dashboard: RUNNING on http://185.107.90.42:7777"
else
    echo "❌ Dashboard: NOT RUNNING"
fi

echo ""
echo "📨 Latest Messages in Database:"
sqlite3 /gauls-copy-trading-system/databases/gauls_trading.db "SELECT datetime(timestamp) as time, substr(message_text, 1, 60) as snippet FROM gauls_messages ORDER BY timestamp DESC LIMIT 3;"

echo ""
echo "🎯 Listener Status:"
tail -3 /gauls-copy-trading-system/logs/telegram_listener.log

echo ""
echo "System is ready to capture new Gauls messages when they arrive!"
