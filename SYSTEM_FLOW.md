# Gauls Copy Trading System - Signal Flow Documentation

## System Architecture

### 1. Message Capture (Telegram Listener)
**File:** `/gauls-copy-trading-system/live_telegram_listener.py`
- Connects to Telegram using Telethon
- Monitors Gauls' channel for new messages
- Stores messages in THREE database tables:
  - `raw_telegram_messages` - Archive of all messages
  - `gauls_messages` - Messages for copy trader processing  
  - `all_gauls_messages` - Messages for dashboard display

### 2. Signal Analysis Pipeline

#### 2.1 Memory System
**File:** `/opt/gauls-bot/gauls_memory_system.py`
- Processes raw messages for context and insights
- Stores trading insights and market analysis
- Maintains historical context

#### 2.2 Signal Parser
**File:** `/opt/gauls-bot/signal_parser.py`
- Extracts trading parameters from messages:
  - Symbol (BTC, ETH, etc.)
  - Entry price or "CMP" (Current Market Price)
  - Take Profit (TP) levels
  - Stop Loss (SL) levels
  - Trade type (Spot/Futures)

#### 2.3 LLM Analyzer
**File:** `/gauls-copy-trading-system/gauls_llm_analyzer.py`
- Analyzes signal quality and confidence
- Validates against market conditions
- Generates execution recommendations
- Falls back to pattern matching if OpenAI unavailable

### 3. Copy Trading Execution
**File:** `/gauls-copy-trading-system/gauls_copy_trader.py`

**Polling Process:**
1. Checks `gauls_messages` table every few minutes
2. Identifies new trading signals
3. Verifies signal hasn't been processed (via `processed_gauls_signals`)
4. Analyzes signal with LLM Analyzer
5. Executes trade on WooX exchange
6. Records trade in `trades.db`

### 4. Trade Management

#### 4.1 Exit Monitor
**File:** `/gauls-copy-trading-system/exit_monitor_v2.py`
- Monitors open positions
- Checks for TP/SL hits
- Executes exits automatically

#### 4.2 Update Processor  
**File:** `/gauls-copy-trading-system/gauls_trade_update_processor.py`
- Processes Gauls' trade updates (1R, 2R, breakeven)
- Adjusts positions accordingly
- Records updates in `trade_updates` table

### 5. Dashboard
**File:** `/gauls-copy-trading-system/gauls_dashboard_enhanced.py`
- Web interface on port 5000
- Displays recent messages from `all_gauls_messages`
- Shows open positions and P&L
- System health monitoring

## Database Schema

### gauls_trading.db
- `raw_telegram_messages` - Raw message archive
- `gauls_messages` - Messages for copy trader
- `all_gauls_messages` - Messages for dashboard
- `processed_gauls_signals` - Processed signal tracking
- `processed_gauls_updates` - Processed update tracking
- `trade_updates` - Trade update history

### trades.db
- `trades` - Executed trades and positions
- `trade_history` - Historical trade data

## Signal Flow Example

1. **Gauls posts:** "BTC Buying Setup: Entry CMP, TP 114786, SL 111468"
2. **Telegram Listener** captures and stores in all 3 tables
3. **Memory System** processes for context
4. **Copy Trader** polls and finds new signal
5. **Signal Parser** extracts: BTC, CMP entry, TP=114786, SL=111468
6. **LLM Analyzer** evaluates signal quality
7. **Copy Trader** executes buy order on WooX
8. **Exit Monitor** begins monitoring for TP/SL
9. **Dashboard** displays signal and position

## Key Files Summary

```
/gauls-copy-trading-system/
├── live_telegram_listener.py    # Message capture
├── gauls_copy_trader.py         # Trade execution
├── gauls_llm_analyzer.py        # Signal analysis
├── exit_monitor_v2.py           # Position management
├── gauls_dashboard_enhanced.py  # Web interface
└── databases/
    ├── gauls_trading.db         # Message storage
    └── trades.db                # Trade records

/opt/gauls-bot/
├── gauls_memory_system.py       # Context processing
├── signal_parser.py             # Signal extraction
└── config.py                    # System configuration
```

## SystemD Services

All components run as systemd services:
- `gauls-telegram-listener` - Message monitoring
- `gauls-copy-trader` - Trade execution
- `gauls-exit-monitor` - Exit management
- `gauls-update-processor` - Update handling
- `gauls-dashboard` - Web interface

## Monitoring

Check system status:
```bash
sudo systemctl status 'gauls-*'
```

View logs:
```bash
journalctl -u gauls-copy-trader -f
tail -f /gauls-copy-trading-system/logs/*.log
```

## Database Queries

Check recent signals:
```sql
SELECT * FROM gauls_messages ORDER BY id DESC LIMIT 5;
```

Check open positions:
```sql
SELECT * FROM trades WHERE status='open';
```