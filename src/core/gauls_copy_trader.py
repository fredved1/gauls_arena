#!/usr/bin/env python3
"""
🚨 Gauls Copy Trader - Pure Signal Following
Directly executes Gauls' trading calls without technical analysis
"""

import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')

from core.unified_exchange import UnifiedExchange
from utils.gauls_memory_system import GaulsMemorySystem
from utils.gauls_llm_analyzer import GaulsLLMAnalyzer
from parsers.gauls_signal_parser import GaulsSignalParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/gauls-copy-trading-system/logs/copy_trader.log')
    ]
)
logger = logging.getLogger("GAULS_COPY")

# ⚙️ CONFIGURATION - Easy to adjust
MAX_LOSS_PER_TRADE_EUR = 25.0  # Maximum loss per trade in EUR
GAULS_LEVERAGE = 10.0  # Leverage for all Gauls trades
MARGIN_USAGE_PCT = 0.9  # Use 90% of available margin when scaling down

class GaulsCopyTrader:
    """Directly execute Gauls trading signals"""
    
    def __init__(self, balance: float = 5000.0):
        self.exchange = UnifiedExchange()  # Uses TRADING_MODE env variable
        self.parser = GaulsSignalParser()
        self.memory = GaulsMemorySystem()
        self.llm_analyzer = GaulsLLMAnalyzer()  # AI enhancement
        
        # Use different database based on trading mode
        trading_mode = os.environ.get('TRADING_MODE', 'mock')
        if trading_mode == 'production':
            self.trades_db = '/gauls-copy-trading-system/databases/trades.db'
            self.sage_db = '/gauls-copy-trading-system/databases/gauls_trading.db'
        else:
            self.trades_db = '/gauls-copy-trading-system/databases/trades.db'
            self.sage_db = '/gauls-copy-trading-system/databases/gauls_trading.db'
        self.positions = {}
        
        # Load existing positions from database on startup
        self._load_existing_positions()
        
        logger.info(f"🚨 Gauls Copy Trader initialized with ${balance} USDT")
    
    def _load_existing_positions(self):
        """Load existing open positions from database on startup"""
        try:
            conn = sqlite3.connect(self.trades_db)
            cursor = conn.cursor()
            
            # Get all open Gauls positions
            cursor.execute("""
                SELECT id, symbol, side, entry_price, quantity, stop_loss, take_profit_1, take_profit_2, 
                       leverage, entry_time, notes
                FROM trades 
                WHERE strategy = 'gauls_copy' AND status = 'open'
                ORDER BY entry_time DESC
            """)
            
            positions = cursor.fetchall()
            conn.close()
            
            # Rebuild positions dictionary
            for pos in positions:
                trade_id, symbol, side, entry_price, quantity, stop_loss, tp1, tp2, leverage, entry_time, notes = pos
                
                # Create position key
                position_key = f"{symbol}_{trade_id}"
                
                # Reconstruct signal data for position tracking
                signal_data = {
                    'symbol': symbol,
                    'side': side,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': tp1,
                    'take_profit_2': tp2,
                    'leverage': leverage or 10,  # 10x leverage for Gauls trades
                    'source': 'gauls_copy'
                }
                
                # Add to positions tracking
                self.positions[position_key] = {
                    'trade_id': trade_id,
                    'signal': signal_data,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'side': side,
                    'entry_time': entry_time,
                    'notes': notes
                }
            
            if len(positions) > 0:
                logger.info(f"🔄 Restored {len(positions)} existing Gauls positions from database")
            else:
                logger.info("✅ No existing Gauls positions to restore")
                
        except Exception as e:
            logger.error(f"Error loading existing positions: {e}")
    
    def scan_for_new_signals(self, hours: int = 24) -> List[Dict]:
        """Scan for new REAL Gauls trading signals from Telegram"""
        try:
            conn = sqlite3.connect(self.sage_db)
            cursor = conn.cursor()
            
            # Look for REAL Gauls messages with trading setups
            cutoff_time = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            
            rows = []
            # First try gauls_market_insights table if it exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gauls_market_insights'")
            if cursor.fetchone():
                cursor.execute('''
                    SELECT id, raw_text, timestamp 
                    FROM gauls_market_insights
                    WHERE is_active = 1 
                    AND (message_type = 'real' OR message_type = 'signal')
                    AND timestamp > ?
                    AND (raw_text LIKE '%Setup%' OR raw_text LIKE '%setup%')
                    AND (raw_text LIKE '%Entry:%' OR raw_text LIKE '%ENTRY :%' OR raw_text LIKE '%Entry :%' OR raw_text LIKE '%Entry: %')
                    AND (raw_text LIKE '%TP:%' OR raw_text LIKE '%Target:%' OR raw_text LIKE '%TARGET :%' OR raw_text LIKE '%target:%' OR raw_text LIKE '%TP: %')
                    AND (raw_text LIKE '%SL:%' OR raw_text LIKE '%Invalidation:%' OR raw_text LIKE '%invalidation:%' OR raw_text LIKE '%SL: %')
                    ORDER BY timestamp DESC
                ''', (cutoff_time,))
                
                rows = cursor.fetchall()
                logger.info(f"📊 Found {len(rows)} signals in gauls_market_insights table")
            else:
                logger.debug("gauls_market_insights table not found, using gauls_messages only")
            
            # Also check gauls_messages table and combine results
            cursor.execute('''
                SELECT message_id, message_text, timestamp 
                FROM gauls_messages
                WHERE timestamp > ?
                AND (message_text LIKE '%Setup%' OR message_text LIKE '%setup%')
                AND (message_text LIKE '%Entry:%' OR message_text LIKE '%ENTRY:%' OR message_text LIKE '%entry:%' OR message_text LIKE '%Entry %' OR message_text LIKE '%ENTRY %' OR message_text LIKE '%entry %' OR message_text LIKE '%Enter:%' OR message_text LIKE '%ENTER:%' OR message_text LIKE '%enter:%' OR message_text LIKE '%Buy:%' OR message_text LIKE '%BUY:%' OR message_text LIKE '%buy:%' OR message_text LIKE '%Long:%' OR message_text LIKE '%LONG:%' OR message_text LIKE '%long:%' OR message_text LIKE '%CMP:%' OR message_text LIKE '%Current:%' OR message_text LIKE '%CURRENT:%' OR message_text LIKE '%Market:%' OR message_text LIKE '%MARKET:%')
                AND (message_text LIKE '%TP:%' OR message_text LIKE '%TP %' OR message_text LIKE '%Target:%' OR message_text LIKE '%Target %' OR message_text LIKE '%TARGET:%' OR message_text LIKE '%TARGET %' OR message_text LIKE '%target:%' OR message_text LIKE '%target %' OR message_text LIKE '%Take Profit:%' OR message_text LIKE '%Take profit:%' OR message_text LIKE '%TAKE PROFIT:%' OR message_text LIKE '%Profit Target:%' OR message_text LIKE '%PT:%' OR message_text LIKE '%PT %' OR message_text LIKE '%Final:%' OR message_text LIKE '%FINAL:%' OR message_text LIKE '%Exit:%' OR message_text LIKE '%EXIT:%' OR message_text LIKE '%Sell:%' OR message_text LIKE '%SELL:%')
                AND (message_text LIKE '%SL:%' OR message_text LIKE '%SL %' OR message_text LIKE '%Stop Loss:%' OR message_text LIKE '%Stop loss:%' OR message_text LIKE '%STOP LOSS:%' OR message_text LIKE '%Stop-Loss:%' OR message_text LIKE '%StopLoss:%' OR message_text LIKE '%Invalidation:%' OR message_text LIKE '%invalidation:%' OR message_text LIKE '%INVALIDATION:%' OR message_text LIKE '%Cut Loss:%' OR message_text LIKE '%Cut loss:%' OR message_text LIKE '%CUT LOSS:%' OR message_text LIKE '%Risk:%' OR message_text LIKE '%RISK:%' OR message_text LIKE '%Exit SL:%' OR message_text LIKE '%Stop:%' OR message_text LIKE '%STOP:%' OR message_text LIKE '%Loss:%' OR message_text LIKE '%LOSS:%')
                ORDER BY timestamp DESC
            ''', (cutoff_time,))
            additional_rows = cursor.fetchall()
            logger.info(f"📊 Found {len(additional_rows)} additional signals in gauls_messages table")
            
            # Combine both result sets
            rows.extend(additional_rows)
            
            signals = []
            for row in rows:
                insight_id, raw_text, timestamp = row
                
                # Parse the signal
                signal = self.parser.parse_signal(raw_text)
                if signal:
                    signal['insight_id'] = insight_id
                    signal['timestamp'] = timestamp
                    signals.append(signal)
            
            conn.close()
            
            if signals:
                logger.info(f"📈 Found {len(signals)} Gauls trading signals in last {hours}h")
            
            return signals
            
        except Exception as e:
            logger.error(f"Error scanning for signals: {e}")
            return []
    
    def scan_for_trade_updates(self, hours: int = 6) -> List[Dict]:
        """Scan for Gauls trade update messages for position management"""
        try:
            conn = sqlite3.connect(self.sage_db)
            cursor = conn.cursor()
            
            cutoff_time = int((datetime.now() - timedelta(hours=hours)).timestamp())
            
            rows = []
            
            # Try gauls_market_insights table if it exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gauls_market_insights'")
            if cursor.fetchone():
                cursor.execute('''
                    SELECT id, raw_text, timestamp 
                    FROM gauls_market_insights
                    WHERE is_active = 1 
                    AND (message_type = 'real' OR message_type = 'signal' OR message_type = 'risk')
                    AND timestamp > ?
                    AND (raw_text LIKE '%TRADE UPDATE%' OR raw_text LIKE '%Trade Update%' 
                         OR raw_text LIKE '%Target achieved%' OR raw_text LIKE '%target hit%')
                    ORDER BY timestamp DESC
                ''', (cutoff_time,))
                rows = cursor.fetchall()
            
            # Check all_gauls_messages table for trade updates
            cursor.execute('''
                SELECT message_id, message_text, timestamp 
                FROM all_gauls_messages
                WHERE timestamp > ?
                AND message_type = 'trade_update'
                ORDER BY timestamp DESC
            ''', (cutoff_time,))
            
            additional_rows = cursor.fetchall()
            rows.extend(additional_rows)
            
            updates = []
            for row in rows:
                update_id, raw_text, timestamp = row
                
                # Parse trade update
                update = self._parse_trade_update(raw_text)
                if update:
                    update['update_id'] = update_id
                    update['timestamp'] = timestamp
                    updates.append(update)
            
            conn.close()
            
            if updates:
                logger.info(f"📊 Found {len(updates)} trade updates in last {hours}h")
            
            return updates
            
        except Exception as e:
            logger.error(f"Error scanning for trade updates: {e}")
            return []
    
    def _parse_trade_update(self, text: str) -> Optional[Dict]:
        """Parse trade update messages for position management"""
        try:
            # Extract symbol - handle multiple formats
            symbol_match = re.search(r'\$([A-Z]{2,10})\s*(?:TRADE UPDATE|Trade Update)', text, re.IGNORECASE)
            if not symbol_match:
                # Try format like "$AI Trade Update" or "AI Trade Update"
                symbol_match = re.search(r'\$?([A-Z]{2,10})\*?\*?\s*Trade\s*Update', text, re.IGNORECASE)
            
            if not symbol_match:
                return None
            
            symbol = symbol_match.group(1)
            
            update = {
                'symbol': f"{symbol}/USDT",
                'type': 'trade_update',
                'raw_text': text
            }
            
            # Check for target achieved messages
            if 'target achieved' in text.lower() or 'target hit' in text.lower() or 'tp hit' in text.lower():
                update['action'] = 'close_position'
                update['reason'] = 'target_achieved'
                
                # Extract R value if mentioned
                r_match = re.search(r'([0-9.]+)R', text, re.IGNORECASE)
                if r_match:
                    update['close_r'] = float(r_match.group(1))
                else:
                    update['close_r'] = 2.0  # Default to 2R if not specified
                    
                update['close_type'] = 'gain'
            
            # Check for profit notifications (+1R, +2R, etc.)
            profit_match = re.search(r'\+([0-9.]+)R\s*(?:DONE|done|achieved)', text, re.IGNORECASE)
            if profit_match:
                update['profit_r'] = float(profit_match.group(1))
                if 'action' not in update:
                    update['action'] = 'profit_taken'
            
            # Check for risk-free instructions
            if 'risk free' in text.lower() or 'move your stop to entry' in text.lower() or 'sl at be' in text.lower():
                if 'action' not in update or update['action'] != 'close_position':
                    update['action'] = 'move_to_breakeven'
            
            # Check for percentage gains
            pct_match = re.search(r'(?:up |gained |[\+])([0-9]+)%', text, re.IGNORECASE)
            if pct_match:
                update['percentage_gain'] = float(pct_match.group(1))
            
            # Check for closing/exit instructions
            closing_match = re.search(r'closing.*in.*?(-?[0-9.]+)R\s*(loss|gain)', text, re.IGNORECASE)
            if closing_match:
                r_value = float(closing_match.group(1))
                loss_gain = closing_match.group(2).lower()
                update['action'] = 'close_position'
                update['close_r'] = r_value
                update['reason'] = 'gauls_instruction'
                update['close_type'] = loss_gain
            
            return update
            
        except Exception as e:
            logger.error(f"Error parsing trade update: {e}")
            return None
    
    async def process_trade_update(self, update: Dict):
        """Process trade update messages for position management"""
        try:
            symbol = update['symbol']
            action = update.get('action')
            
            logger.info(f"📊 Processing trade update for {symbol}: {action}")
            
            if action == 'move_to_breakeven':
                # Move stop loss to entry price for risk-free trading
                await self._move_stop_to_breakeven(symbol)
                logger.info(f"🛡️ Moved {symbol} stop to breakeven (risk-free)")
            
            elif action == 'profit_taken':
                profit_r = update.get('profit_r', 0)
                logger.info(f"💰 {symbol} profit taken: +{profit_r}R")
                # Could implement partial profit taking here
            
            elif action == 'close_position':
                close_r = update.get('close_r', 0)
                close_type = update.get('close_type', 'unknown')
                reason = update.get('reason', 'gauls_instruction')
                logger.info(f"🚨 Gauls instruction: Close {symbol} at {close_r:+}R {close_type}")
                await self._close_all_positions(symbol, reason, close_r)
            
            # Log the update in database for tracking
            self._record_trade_update(update)
            
        except Exception as e:
            logger.error(f"Error processing trade update: {e}")
    
    async def _move_stop_to_breakeven(self, symbol: str):
        """Move stop loss to entry price for risk-free trading"""
        try:
            # Find matching position
            for position_key, position in self.positions.items():
                if position['signal']['symbol'] == symbol:
                    entry_price = position['entry_price']
                    
                    # Update stop loss in signal
                    position['signal']['stop_loss'] = entry_price
                    
                    # Update database record
                    conn = sqlite3.connect(self.trades_db)
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE trades 
                        SET stop_loss = ?, notes = notes || ' | RISK-FREE: SL moved to entry'
                        WHERE symbol = ? AND strategy = 'gauls_copy' AND status = 'open'
                        ORDER BY entry_time DESC LIMIT 1
                    ''', (entry_price, symbol))
                    conn.commit()
                    conn.close()
                    
                    logger.info(f"🛡️ Updated {symbol} SL to entry: ${entry_price:.4f}")
                    break
                    
        except Exception as e:
            logger.error(f"Error moving stop to breakeven: {e}")
    
    async def _close_all_positions(self, symbol: str, reason: str, close_r: float):
        """Close all open positions for a symbol per Gauls instruction"""
        try:
            positions_closed = 0
            
            # Get current market price for execution
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # Find and close all matching positions
            conn = sqlite3.connect(self.trades_db)
            cursor = conn.cursor()
            
            # Get all open positions for this symbol
            cursor.execute('''
                SELECT id, entry_price, quantity, leverage 
                FROM trades 
                WHERE symbol = ? AND strategy = 'gauls_copy' AND status = 'open'
            ''', (symbol,))
            
            open_positions = cursor.fetchall()
            
            for position in open_positions:
                position_id, entry_price, quantity, leverage = position
                
                # Calculate P&L
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                leveraged_pnl = pnl_pct * leverage
                
                # Execute market sell order (simulation)
                logger.info(f"📊 Closing position {position_id}: {quantity:.2f} {symbol} @ ${current_price:.4f}")
                
                # Update position status in database
                cursor.execute('''
                    UPDATE trades 
                    SET status = 'closed', 
                        exit_price = ?, 
                        exit_time = datetime('now'), 
                        pnl = ?,
                        notes = COALESCE(notes, '') || ? 
                    WHERE id = ?
                ''', (current_price, leveraged_pnl, f' | GAULS EXIT: {close_r:+}R {reason}', position_id))
                
                positions_closed += 1
                logger.info(f"✅ Position {position_id} closed: {leveraged_pnl:+.2f}% P&L")
            
            conn.commit()
            conn.close()
            
            if positions_closed > 0:
                logger.info(f"🚨 Closed {positions_closed} {symbol} positions per Gauls instruction ({close_r:+}R)")
            else:
                logger.warning(f"⚠️ No open {symbol} positions found to close")
                
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
    
    def _record_trade_update(self, update: Dict):
        """Record trade update in database for tracking"""
        try:
            conn = sqlite3.connect(self.sage_db)
            cursor = conn.cursor()
            
            # Create trade_updates table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    action TEXT,
                    profit_r REAL,
                    percentage_gain REAL,
                    raw_text TEXT,
                    timestamp TEXT,
                    processed_at TEXT
                )
            ''')
            
            cursor.execute('''
                INSERT INTO trade_updates (
                    symbol, action, profit_r, percentage_gain, raw_text, timestamp, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                update['symbol'],
                update.get('action', ''),
                update.get('profit_r', 0),
                update.get('percentage_gain', 0),
                update['raw_text'],
                update['timestamp'],
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error recording trade update: {e}")
    
    def _is_signal_already_processed(self, signal: Dict) -> bool:
        """Check if this signal has already been processed"""
        try:
            conn = sqlite3.connect(self.sage_db)
            cursor = conn.cursor()
            
            # Create a unique hash for the signal based on content
            import hashlib
            signal_text = signal.get('raw_text', '')
            signal_hash = hashlib.md5(signal_text.encode()).hexdigest()
            
            # Check if signal already processed
            cursor.execute('''
                SELECT id FROM processed_gauls_signals 
                WHERE signal_hash = ? OR (symbol = ? AND signal_timestamp = ?)
            ''', (signal_hash, signal['symbol'], signal.get('timestamp', '')))
            
            result = cursor.fetchone()
            conn.close()
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error checking processed signals: {e}")
            return False
    
    def _has_recent_trade(self, symbol: str, cooldown_minutes: int = 5) -> bool:
        """Check if there's a recent trade on this symbol within cooldown period"""
        try:
            conn = sqlite3.connect(self.trades_db)
            cursor = conn.cursor()
            
            # Check for trades within the cooldown period
            cutoff_time = (datetime.now() - timedelta(minutes=cooldown_minutes)).isoformat()
            cursor.execute('''
                SELECT COUNT(*) FROM trades 
                WHERE symbol = ? AND strategy = 'gauls_copy' 
                AND entry_time > ? AND status = 'open'
            ''', (symbol, cutoff_time))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking recent trades: {e}")
            return False
    
    def _record_processed_signal(self, signal: Dict, trade_id: int = None):
        """Record that a signal has been processed"""
        try:
            conn = sqlite3.connect(self.sage_db)
            cursor = conn.cursor()
            
            import hashlib
            signal_text = signal.get('raw_text', '')
            signal_hash = hashlib.md5(signal_text.encode()).hexdigest()
            
            cursor.execute('''
                INSERT OR IGNORE INTO processed_gauls_signals 
                (signal_id, symbol, signal_timestamp, signal_hash, raw_text, trade_ids)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                signal.get('insight_id'),
                signal['symbol'],
                signal.get('timestamp', ''),
                signal_hash,
                signal_text,
                str(trade_id) if trade_id else ''
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Recorded processed signal for {signal['symbol']}")
            
        except Exception as e:
            logger.error(f"Error recording processed signal: {e}")
    
    async def execute_gauls_signal(self, signal: Dict) -> Optional[Dict]:
        """Execute a Gauls trading signal with LLM analysis"""
        try:
            symbol = signal['symbol']
            side = signal['side']
            
            # Check if signal was already processed (persistent check)
            if self._is_signal_already_processed(signal):
                logger.info(f"Signal already processed for {symbol} (timestamp: {signal.get('timestamp')})")
                return None
            
            # Check for recent trades on same symbol (cooldown period)
            if self._has_recent_trade(symbol, cooldown_minutes=5):
                logger.info(f"Cooldown active for {symbol} - skipping to prevent duplicate trades")
                return None
            
            # Check if we already have a position for this signal
            signal_key = f"{symbol}_{signal.get('insight_id', '')}"
            if signal_key in self.positions:
                logger.info(f"Already have active position for {symbol} (ID: {signal.get('insight_id')})")
                # Mark signal as processed to avoid re-checking it
                self._record_processed_signal(signal, None)
                return None
            
            # 🚨 CMP SPEED OPTIMIZATION: Skip LLM analysis for time-critical signals
            if signal.get('entry_type') == 'market':
                logger.info(f"🚨 CMP SIGNAL DETECTED - SKIPPING LLM ANALYSIS FOR MAXIMUM SPEED!")
                # Use default high-confidence execution plan
                enhanced_analysis = {'signal_confidence': 'high', 'execution_recommendation': 'proceed'}
                execution_plan = {'should_execute': True, 'position_size_modifier': 1.0}
            else:
                # 🤖 LLM ANALYSIS for non-CMP signals (where speed is less critical)
                logger.info(f"🤖 Analyzing {symbol} signal with AI...")
                analysis = self.llm_analyzer.analyze_signal_quality(signal, signal['raw_text'])
                enhanced_analysis = self.llm_analyzer.validate_against_market_conditions(signal, analysis)
                execution_plan = self.llm_analyzer.generate_execution_plan(signal, enhanced_analysis)
                
                # Log LLM insights
                logger.info(f"🤖 LLM Analysis: {enhanced_analysis['signal_confidence']} confidence, {enhanced_analysis['execution_recommendation']} recommendation")
                if enhanced_analysis.get('warnings'):
                    logger.warning(f"⚠️ LLM Warnings: {enhanced_analysis['warnings']}")
                if enhanced_analysis.get('enhancements'):
                    logger.info(f"💡 LLM Suggestions: {enhanced_analysis['enhancements']}")
                
                # Check if LLM recommends avoiding the trade
                if not execution_plan['should_execute']:
                    logger.warning(f"🚫 LLM recommends avoiding {symbol} trade: {execution_plan.get('reason', 'High risk')}")
                    return None
            
            # Get current price and target entry
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 🤖 LLM ENTRY PRICE ADJUSTMENT - Apply intelligent hint interpretation (SKIP for CMP)
            base_entry = signal.get('entry_price', current_price)
            if signal.get('entry_type') == 'market':
                # CMP signals: Use current price immediately, no adjustments needed
                target_entry = current_price
                logger.info(f"🚨 CMP: Using current market price ${current_price:,.2f} (no adjustment for speed)")
            elif signal.get('entry_hint'):
                logger.info(f"🤖 Applying LLM entry adjustment for hint: '{signal['entry_hint']}'")
                target_entry = self.llm_analyzer.adjust_entry_price_with_llm(signal, current_price)
                if target_entry != base_entry:
                    logger.info(f"🎯 Entry Adjusted: ${base_entry:,.2f} → ${target_entry:,.2f} (hint: '{signal['entry_hint']}')")
            else:
                target_entry = base_entry
            
            # 🎯 SMART ENTRY LOGIC - Check if we should use limit or market order
            
            # 🚨 CMP PRIORITY: Immediate execution for speed-critical signals
            if signal.get('entry_type') == 'market':
                order_type = 'market'
                execution_price = current_price
                should_wait = False
                logger.info(f"🚨 CMP SIGNAL - IMMEDIATE EXECUTION: {symbol} @ ${current_price:,.2f} (speed is crucial!)")
            else:
                # Standard limit order logic for specific entry prices
                price_difference_pct = abs(current_price - target_entry) / target_entry * 100
                order_type = 'market'
                execution_price = current_price
                should_wait = False
                
                if signal.get('entry_type') == 'limit' and price_difference_pct > 1.0:  # More than 1% away
                    if side == 'buy' and current_price > target_entry:
                        # Price is above target - set limit order to buy lower
                        order_type = 'limit'
                        execution_price = target_entry
                        should_wait = True
                        logger.info(f"💡 {symbol} @ ${current_price:,.0f} > Entry ${target_entry:,.0f} → Setting LIMIT BUY order")
                    elif side == 'sell' and current_price < target_entry:
                        # Price is below target - set limit order to sell higher  
                        order_type = 'limit'
                        execution_price = target_entry
                        should_wait = True
                        logger.info(f"💡 Price ${current_price:,.0f} < Entry ${target_entry:,.0f} → Setting LIMIT SELL order")
                    else:
                        logger.info(f"💰 Price ${current_price:,.0f} near Entry ${target_entry:,.0f} → Executing MARKET order")
            
            # 💰 FIXED RISK POSITION SIZING - Max loss per trade from config
            MAX_LOSS_EUR = MAX_LOSS_PER_TRADE_EUR
            
            # Get Gauls' stop loss (MANDATORY for risk calculation)
            stop_loss = signal.get('stop_loss')
            if not stop_loss:
                logger.error(f"❌ Cannot execute trade without stop loss! Signal: {signal}")
                return None
            
            # Calculate position size based on stop loss distance
            balance = self.exchange.fetch_balance()
            available = balance['USDT']['free']
            
            # Calculate risk per unit (distance to stop loss)
            risk_per_unit = abs(execution_price - stop_loss)
            if risk_per_unit == 0:
                logger.error(f"❌ Invalid stop loss: same as entry price!")
                return None
            
            # Calculate maximum units we can buy with 25 EUR risk
            # If SL is hit, we lose exactly 25 EUR (before leverage consideration)
            max_units = MAX_LOSS_EUR / risk_per_unit
            
            # 🚀 GAULS SIGNALS USE HIGH LEVERAGE - High confidence trades!
            leverage = GAULS_LEVERAGE
            
            # Position value (notional) and required margin
            position_value = max_units * execution_price
            margin_required = position_value / leverage
            
            # Safety check: Do we have enough margin?
            if margin_required > available:
                # Scale down to what we can afford
                affordable_margin = available * MARGIN_USAGE_PCT
                position_value = affordable_margin * leverage
                max_units = position_value / execution_price
                actual_risk = max_units * risk_per_unit
                logger.warning(f"⚠️ Insufficient margin! Scaling down: Risk ${MAX_LOSS_EUR:.0f} → ${actual_risk:.2f}")
            else:
                actual_risk = MAX_LOSS_EUR
            
            quantity = max_units
            
            # Apply LLM position size modifier if recommended
            position_modifier = execution_plan.get('position_size_modifier', 1.0)
            if position_modifier != 1.0:
                quantity = quantity * position_modifier
                actual_risk = actual_risk * position_modifier
                logger.info(f"🤖 LLM modifier: {position_modifier:.1f}x → Risk: ${actual_risk:.2f}")
            
            logger.info(f"📊 Position Sizing: Risk ${actual_risk:.2f} | SL distance: ${risk_per_unit:.4f} | Units: {quantity:.6f} | Margin: ${margin_required:.2f} | Leverage: {leverage}x")
            
            # Execute the order with smart order type
            if order_type == 'limit':
                logger.info(f"⏳ Setting LIMIT {side.upper()}: {quantity:.6f} {symbol} @ ${execution_price:,.2f} (LEV: {leverage}x)")
                order = self.exchange.create_order(
                    symbol=symbol,
                    order_type='limit',
                    side=side,
                    amount=quantity,
                    price=execution_price,
                    leverage=leverage  # Pass leverage to exchange
                )
                order_status = 'pending'
            else:
                logger.info(f"🚨 Executing MARKET {side.upper()}: {quantity:.6f} {symbol} @ ${execution_price:,.2f} (LEV: {leverage}x) 🚀")
                order = self.exchange.create_order(
                    symbol=symbol,
                    order_type='market',
                    side=side,
                    amount=quantity,
                    price=execution_price,
                    leverage=leverage  # Pass leverage to exchange
                )
                order_status = 'open'
            
            # Record the trade with Gauls-specific info and LLM analysis
            self._record_gauls_trade(signal, order, execution_price, enhanced_analysis, execution_plan, order_status)
            
            # Track position
            self.positions[signal_key] = {
                'entry_price': current_price,
                'quantity': quantity,
                'side': side,
                'leverage': leverage,
                'signal': signal,
                'entry_time': datetime.now()
            }
            
            logger.info(f"✅ Gauls copy trade executed: {order['id']}")
            return order
            
        except Exception as e:
            logger.error(f"Failed to execute Gauls signal: {e}")
            return None
    
    def _record_gauls_trade(self, signal: Dict, order: Dict, entry_price: float, 
                          analysis: Dict = None, execution_plan: Dict = None, status: str = 'open'):
        """Record Gauls copy trade with LLM analysis in database"""
        try:
            conn = sqlite3.connect(self.trades_db)
            cursor = conn.cursor()
            
            # Calculate Gauls-specific parameters
            stop_loss = signal.get('stop_loss', 0)
            
            # Handle take profit - it might be a single value or array
            take_profit = signal.get('take_profit', 0)
            take_profits = signal.get('take_profits', [])
            
            if take_profit and not take_profits:
                # Single TP value from signal
                tp1 = take_profit
                tp2 = 0
            else:
                # Array of TP values
                tp1 = take_profits[0] if len(take_profits) > 0 else 0
                tp2 = take_profits[1] if len(take_profits) > 1 else 0
            
            leverage = GAULS_LEVERAGE
            
            # Calculate risk/reward if we have stop loss and TP
            risk_reward = 0
            if stop_loss and tp1:
                risk = abs(entry_price - stop_loss)
                reward = abs(tp1 - entry_price)
                if risk > 0:
                    risk_reward = reward / risk
            
            # Build enhanced notes with LLM analysis
            base_notes = f"Gauls Copy Trade - {signal.get('conviction', 'high')} conviction"
            if analysis:
                llm_info = f" | LLM: {analysis['signal_confidence']} confidence, {analysis['execution_recommendation']} rec"
                if execution_plan.get('position_size_modifier', 1.0) != 1.0:
                    llm_info += f", {execution_plan['position_size_modifier']:.1f}x sizing"
                base_notes += llm_info
            
            cursor.execute('''
                INSERT INTO trades (
                    symbol, side, entry_price, entry_time, quantity, remaining_quantity, status, 
                    strategy, notes, stop_loss, take_profit_1, take_profit_2, 
                    leverage, risk_reward, trade_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal['symbol'],
                signal['side'],
                entry_price,
                datetime.now().isoformat(),
                order['amount'],
                order['amount'],  # Set remaining_quantity = quantity initially
                status,
                'gauls_copy',  # Special strategy tag
                base_notes,  # Enhanced notes with LLM insights
                stop_loss,
                tp1, 
                tp2,
                leverage,
                risk_reward,
                'gauls_copy'  # Trade type for dashboard filtering
            ))
            
            # Get the trade ID we just inserted
            trade_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            # Record this signal as processed
            self._record_processed_signal(signal, trade_id)
            
            logger.info(f"📝 Recorded Gauls copy trade #{trade_id}: SL:{stop_loss} TP1:{tp1} TP2:{tp2}")
            
        except Exception as e:
            logger.error(f"Error recording Gauls trade: {e}")
    
    async def check_gauls_exits(self):
        """Check if any Gauls positions should be closed based on their signals"""
        for position_key, position in list(self.positions.items()):
            try:
                symbol = position['signal']['symbol']
                signal = position['signal']
                
                # Get current price
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                entry_price = position['entry_price']
                side = position['side']
                
                # Check stop loss
                stop_loss = signal.get('stop_loss')
                if stop_loss:
                    if side == 'long' and current_price <= stop_loss:
                        logger.warning(f"🛑 Gauls Stop Loss hit: {symbol} @ ${current_price:,.2f}")
                        await self._close_gauls_position(position_key, current_price, "Stop Loss")
                        continue
                    elif side == 'short' and current_price >= stop_loss:
                        logger.warning(f"🛑 Gauls Stop Loss hit: {symbol} @ ${current_price:,.2f}")
                        await self._close_gauls_position(position_key, current_price, "Stop Loss")
                        continue
                
                # Check take profits
                take_profits = signal.get('take_profits', [])
                for i, tp_level in enumerate(take_profits):
                    if side == 'long' and current_price >= tp_level:
                        logger.info(f"💰 Gauls TP{i+1} hit: {symbol} @ ${current_price:,.2f}")
                        await self._close_gauls_position(position_key, current_price, f"Take Profit {i+1}")
                        break
                    elif side == 'short' and current_price <= tp_level:
                        logger.info(f"💰 Gauls TP{i+1} hit: {symbol} @ ${current_price:,.2f}")
                        await self._close_gauls_position(position_key, current_price, f"Take Profit {i+1}")
                        break
                        
            except Exception as e:
                logger.error(f"Error checking Gauls exit for {position_key}: {e}")
    
    async def _close_gauls_position(self, position_key: str, exit_price: float, reason: str):
        """Close a Gauls copy trading position"""
        try:
            position = self.positions[position_key]
            symbol = position['signal']['symbol']
            
            # Close position
            close_order = self.exchange.create_order(
                symbol=symbol,
                order_type='market',
                side='sell' if position['side'] == 'long' else 'buy',
                amount=position['quantity'],
                price=exit_price
            )
            
            # Update database
            conn = sqlite3.connect(self.trades_db)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE trades 
                SET status = 'closed', exit_price = ?, exit_time = ?, notes = ?
                WHERE symbol = ? AND strategy = 'gauls_copy' AND status = 'open'
                ORDER BY entry_time DESC LIMIT 1
            ''', (exit_price, datetime.now().isoformat(), f"Gauls Copy Trade - {reason}", symbol))
            
            conn.commit()
            conn.close()
            
            # Remove from tracking
            del self.positions[position_key]
            
            logger.info(f"✅ Closed Gauls position: {symbol} @ ${exit_price:,.2f} - {reason}")
            
        except Exception as e:
            logger.error(f"Error closing Gauls position: {e}")
    
    async def trading_loop(self):
        """Main loop for Gauls copy trading"""
        logger.info("🚨 Starting Gauls Copy Trading loop...")
        
        while True:
            try:
                # Scan for new Gauls signals
                new_signals = self.scan_for_new_signals(hours=24)  # Check last 24 hours
                
                # Execute new signals
                for signal in new_signals:
                    await self.execute_gauls_signal(signal)
                
                # Process trade updates for position management
                trade_updates = self.scan_for_trade_updates(hours=6)
                for update in trade_updates:
                    await self.process_trade_update(update)
                
                # Check exit conditions for existing positions
                await self.check_gauls_exits()
                
                # Show status
                balance = self.exchange.fetch_balance()
                logger.info(f"🚨 Gauls Copy Balance: ${balance['USDT']['total']:,.2f} | Positions: {len(self.positions)}")
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute for faster Gauls response
                
            except Exception as e:
                logger.error(f"Error in Gauls copy trading loop: {e}")
                await asyncio.sleep(30)

async def main():
    trader = GaulsCopyTrader()
    await trader.trading_loop()

if __name__ == "__main__":
    trading_mode = os.environ.get('TRADING_MODE', 'mock')
    print("="*60)
    print("🚨 GAULS COPY TRADER - Direct Signal Following")
    print("="*60)
    if trading_mode == 'production':
        print("🔴 PRODUCTION MODE - REAL MONEY TRADING ON WOOX")
    else:
        print(f"🟢 EXPERIMENTAL/MOCK MODE - Paper trading (TRADING_MODE={trading_mode})")
    print("Strategy: Pure signal execution (no technical analysis)")
    print("-"*60)
    
    asyncio.run(main())