# 🚀 Gauls Copy Trading System

A focused, clean implementation of the Gauls copy trading system - extracting only the essential components from SAGE Trading System.

## 📋 System Overview

This is a standalone Gauls copy trading system that:
- **Monitors** Gauls Telegram signals in real-time
- **Executes** trades automatically with proper risk management
- **Manages** positions with partial exits and stop loss adjustments
- **Processes** trade updates (target achieved, move to breakeven, etc.)

## 🏗️ Architecture

```
/gauls-copy-trading-system/
├── gauls_copy_trader.py      # Main trading engine
├── live_telegram_listener.py  # Real-time Telegram monitoring
├── exit_monitor_v2.py         # Position exit management
├── gauls_llm_analyzer.py      # AI signal interpretation
├── gauls_memory_system.py     # Trade history & learning
├── unified_exchange.py        # Exchange connectivity
├── databases/
│   ├── gauls_trading.db      # Messages & signals
│   └── trades.db              # Trade execution records
├── logs/                      # System logs
└── pids/                      # Process IDs
```

## 🚀 Quick Start

### Start the system:
```bash
# Experimental mode (paper trading)
./start_gauls_system.sh

# Production mode (REAL MONEY)
./start_gauls_system.sh production
```

### Monitor status:
```bash
./monitor_gauls_system.sh
```

### Stop the system:
```bash
./stop_gauls_system.sh
```

## 📊 Features

### ✅ Signal Processing
- Real-time Gauls signal detection
- Multiple format support (CMP, limit orders)
- Smart entry adjustment with AI
- Duplicate signal prevention

### ✅ Trade Management
- Partial exit support (40% at TP1, 30% at TP2, 30% at TP3)
- Dynamic stop loss adjustment
- Risk-free trade creation (move SL to breakeven)
- Trade update processing (target achieved, etc.)

### ✅ Risk Management
- 2% risk per trade
- Position sizing based on stop loss
- Portfolio heat monitoring
- Maximum position limits

## 💾 Database Schema

### gauls_trading.db
- `gauls_messages` - Raw Telegram messages
- `processed_gauls_signals` - Processed signal tracking
- `trade_updates` - Trade update history

### trades.db
- `trades` - Main trade records
- `partial_exits` - Partial exit history

## 📈 Trading Modes

- **Experimental**: Paper trading for testing
- **Production**: Real money trading on WooX exchange

## 🔍 Monitoring

### View real-time logs:
```bash
tail -f logs/gauls_copy_trader.log
tail -f logs/telegram_listener.log
tail -f logs/exit_monitor.log
```

### Check open positions:
```bash
sqlite3 databases/trades.db "SELECT * FROM trades WHERE status='open';"
```

### View recent signals:
```bash
sqlite3 databases/gauls_trading.db "SELECT * FROM gauls_messages ORDER BY timestamp DESC LIMIT 10;"
```

## ⚙️ Configuration

Environment variables in `.env`:
```
TRADING_MODE=experimental
WOOX_API_KEY=your_key
WOOX_API_SECRET=your_secret
TELEGRAM_API_ID=your_id
TELEGRAM_API_HASH=your_hash
```

## 🎯 Key Improvements

This focused system provides:
- **Clean separation** from other strategies
- **Dedicated databases** for Gauls trading only
- **Simplified monitoring** and management
- **Optimized for Gauls signals** specifically

## 🛡️ Safety Features

- Duplicate signal detection
- Position size limits
- Stop loss enforcement
- Trade update processing
- Automatic error recovery

## 📝 Notes

- System automatically processes "Target achieved" messages
- Handles partial exits at multiple TP levels
- Moves stops to breakeven when instructed
- Maintains trade history for learning