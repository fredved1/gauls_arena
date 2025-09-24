#!/usr/bin/env python3
"""
Enhanced Exit Monitor with Partial Exits and Free Trade Support
Monitors all open trades and executes partial exits at TP levels
"""

import asyncio
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional
import ccxt
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/gauls-copy-trading-system/src')

from core.unified_exchange import UnifiedExchange

# Configure logging
logger = logging.getLogger('EXIT_MONITOR_V2')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('logs/exit_monitor.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(console_handler)

class EnhancedExitMonitor:
    """Enhanced monitor with partial exits and free trade support"""
    
    def __init__(self):
        self.trades_db = '/gauls-copy-trading-system/databases/trades.db'
        self.exchange = UnifiedExchange()  # Use WooX instead of Binance
        self.check_interval = 5  # seconds
        
        # Partial exit configuration
        self.tp1_exit_percent = 0.4  # Exit 40% at TP1
        self.tp2_exit_percent = 0.3  # Exit 30% at TP2
        self.tp3_exit_percent = 0.3  # Exit remaining 30%
        
        logger.info("🚀 Enhanced Exit Monitor V2 initialized with partial exit support")
    
    async def get_open_trades(self) -> List[Dict]:
        """Get all open trades from database"""
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, symbol, side, entry_price, stop_loss,
                   take_profit_1, take_profit_2, leverage, entry_time, strategy,
                   quantity, original_quantity, remaining_quantity, 
                   partial_exits_done, partial_pnl
            FROM trades
            WHERE status = 'open'
            ORDER BY entry_time ASC
        """)
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'id': row[0],
                'symbol': row[1],
                'side': row[2],
                'entry_price': row[3],
                'stop_loss': row[4],
                'take_profit_1': row[5],
                'take_profit_2': row[6],
                'leverage': row[7] or 1.0,
                'entry_time': row[8],
                'strategy': row[9],
                'quantity': row[10],
                'original_quantity': row[11] or row[10],
                'remaining_quantity': row[12] or row[10],
                'partial_exits_done': row[13] or 0,
                'partial_pnl': row[14] or 0
            })
        
        conn.close()
        return trades
    
    async def check_exit_conditions(self, trade: Dict, current_price: float) -> Optional[str]:
        """Check if trade should exit (partial or full)"""
        
        trade_id = trade['id']
        symbol = trade['symbol']
        side = trade['side']
        entry_price = trade['entry_price']
        stop_loss = trade['stop_loss']
        tp1 = trade['take_profit_1']
        tp2 = trade['take_profit_2']
        partial_exits = trade['partial_exits_done']
        
        # LONG positions
        if side == 'buy':
            # Stop Loss Check (could be at breakeven!)
            if stop_loss and current_price <= stop_loss:
                is_free_trade = stop_loss >= entry_price
                if is_free_trade:
                    await self.close_remaining_position(trade_id, current_price, "Breakeven Stop (Free Trade)")
                    return f"✅ FREE TRADE closed at breakeven @ ${current_price:.4f}"
                else:
                    await self.close_remaining_position(trade_id, current_price, "Stop Loss Hit")
                    return f"❌ Stop Loss Hit @ ${current_price:.4f}"
            
            # TP2 Check (if already took TP1)
            if partial_exits == 1 and tp2 and current_price >= tp2:
                await self.execute_partial_exit(
                    trade_id=trade_id,
                    exit_price=current_price,
                    exit_percent=self.tp2_exit_percent,
                    tp_level=2,
                    new_stop_loss=tp1  # Move stop to TP1
                )
                return f"🎯 TP2 Hit @ ${current_price:.4f} - {self.tp2_exit_percent*100:.0f}% closed, stop→TP1"
            
            # TP1 Check (first partial exit)
            if partial_exits == 0 and tp1 and current_price >= tp1:
                await self.execute_partial_exit(
                    trade_id=trade_id,
                    exit_price=current_price,
                    exit_percent=self.tp1_exit_percent,
                    tp_level=1,
                    new_stop_loss=entry_price  # FREE TRADE!
                )
                return f"🎯 TP1 Hit @ ${current_price:.4f} - {self.tp1_exit_percent*100:.0f}% closed, stop→entry (FREE TRADE!)"
        
        # SHORT positions
        else:
            # Stop Loss Check
            if stop_loss and current_price >= stop_loss:
                is_free_trade = stop_loss <= entry_price
                if is_free_trade:
                    await self.close_remaining_position(trade_id, current_price, "Breakeven Stop (Free Trade)")
                    return f"✅ FREE TRADE closed at breakeven @ ${current_price:.4f}"
                else:
                    await self.close_remaining_position(trade_id, current_price, "Stop Loss Hit")
                    return f"❌ Stop Loss Hit @ ${current_price:.4f}"
            
            # TP2 Check for shorts
            if partial_exits == 1 and tp2 and current_price <= tp2:
                await self.execute_partial_exit(
                    trade_id=trade_id,
                    exit_price=current_price,
                    exit_percent=self.tp2_exit_percent,
                    tp_level=2,
                    new_stop_loss=tp1
                )
                return f"🎯 TP2 Hit @ ${current_price:.4f} - {self.tp2_exit_percent*100:.0f}% closed, stop→TP1"
            
            # TP1 Check for shorts
            if partial_exits == 0 and tp1 and current_price <= tp1:
                await self.execute_partial_exit(
                    trade_id=trade_id,
                    exit_price=current_price,
                    exit_percent=self.tp1_exit_percent,
                    tp_level=1,
                    new_stop_loss=entry_price
                )
                return f"🎯 TP1 Hit @ ${current_price:.4f} - {self.tp1_exit_percent*100:.0f}% closed, stop→entry (FREE TRADE!)"
        
        return None
    
    async def execute_partial_exit(self, trade_id: int, exit_price: float,
                                  exit_percent: float, tp_level: int, new_stop_loss: float):
        """Execute a partial exit and update stop loss"""
        
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        try:
            # Get current trade details
            cursor.execute("""
                SELECT symbol, side, entry_price, quantity, original_quantity,
                       remaining_quantity, partial_exits_done, strategy, leverage
                FROM trades WHERE id = ?
            """, (trade_id,))
            
            result = cursor.fetchone()
            if not result:
                return
            
            symbol, side, entry_price, qty, orig_qty, remaining_qty, partial_exits, strategy, leverage = result
            leverage = leverage or 1.0
            
            # Calculate quantities
            orig_qty = orig_qty or qty
            remaining_qty = remaining_qty or qty
            exit_quantity = orig_qty * exit_percent
            exit_quantity = min(exit_quantity, remaining_qty)  # Don't exit more than available
            
            # Calculate PNL
            if side == 'buy':
                pnl_per_unit = exit_price - entry_price
            else:
                pnl_per_unit = entry_price - exit_price
            
            pnl = pnl_per_unit * exit_quantity
            
            # 🚨 CRITICAL FIX: Execute actual partial exit on exchange before database update
            try:
                logger.info(f"🔄 Executing TP{tp_level} partial exit for {symbol}: {exit_quantity} units")
                
                # Determine order side (opposite of entry)
                close_side = 'sell' if side == 'buy' else 'buy'
                
                # Execute the partial exit order on WooX
                order_result = self.exchange.create_market_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=exit_quantity
                )
                
                logger.info(f"✅ TP{tp_level} exchange order executed: {order_result}")
                
            except Exception as exchange_error:
                logger.error(f"❌ CRITICAL: Failed to execute TP{tp_level} partial exit on exchange: {exchange_error}")
                # Continue with database update to prevent desync
                # But mark it clearly in the notes for manual intervention
                pnl_note = f" - EXCHANGE ERROR: {str(exchange_error)[:50]}"
            else:
                pnl_note = ""
            
            # Record partial exit
            cursor.execute("""
                INSERT INTO partial_exits (trade_id, exit_price, quantity_exited, pnl, tp_level, new_stop_loss, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (trade_id, exit_price, exit_quantity, pnl, tp_level, new_stop_loss,
                  f"TP{tp_level} partial exit - {exit_percent*100:.0f}%{pnl_note}"))
            
            # Update main trade
            new_remaining = remaining_qty - exit_quantity
            new_partial_exits = partial_exits + 1
            
            if new_remaining <= 0.0001:  # Fully closed
                cursor.execute("""
                    UPDATE trades
                    SET status = 'closed',
                        exit_price = ?,
                        exit_time = CURRENT_TIMESTAMP,
                        remaining_quantity = 0,
                        partial_exits_done = ?,
                        partial_pnl = partial_pnl + ?,
                        pnl = partial_pnl + ?,
                        notes = 'Closed via partial exits'
                    WHERE id = ?
                """, (exit_price, new_partial_exits, pnl, pnl, trade_id))
                
                logger.info(f"✅ Trade #{trade_id} {symbol} fully closed via partial exits - Total PNL: ${pnl:.2f}")
            else:
                # Partial close - update stop to create FREE TRADE
                is_free_trade = (side == 'buy' and new_stop_loss >= entry_price) or \
                               (side == 'sell' and new_stop_loss <= entry_price)
                
                notes = f"🆓 FREE TRADE - Stop at entry" if is_free_trade else f"TP{tp_level} hit - Stop at ${new_stop_loss:.2f}"
                
                cursor.execute("""
                    UPDATE trades
                    SET stop_loss = ?,
                        remaining_quantity = ?,
                        partial_exits_done = ?,
                        partial_pnl = partial_pnl + ?,
                        notes = ?
                    WHERE id = ?
                """, (new_stop_loss, new_remaining, new_partial_exits, pnl, notes, trade_id))
                
                if is_free_trade:
                    logger.info(f"🆓 FREE TRADE Created! #{trade_id} {symbol} - {exit_percent*100:.0f}% closed for ${pnl:.2f} - Stop→Entry")
                else:
                    logger.info(f"🎯 TP{tp_level} Hit! #{trade_id} {symbol} - {exit_percent*100:.0f}% closed for ${pnl:.2f} - Stop→${new_stop_loss:.2f}")
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error in partial exit: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def close_remaining_position(self, trade_id: int, exit_price: float, reason: str):
        """Close any remaining position"""
        
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT remaining_quantity, entry_price, side, symbol, leverage, partial_pnl
                FROM trades WHERE id = ?
            """, (trade_id,))
            
            result = cursor.fetchone()
            if not result:
                return
            
            remaining_qty, entry_price, side, symbol, leverage, partial_pnl = result
            leverage = leverage or 1.0
            partial_pnl = partial_pnl or 0
            
            # CRITICAL FIX: Handle NULL remaining_quantity
            # If remaining_quantity is NULL, we need to get it from quantity field
            if remaining_qty is None:
                cursor.execute("SELECT quantity FROM trades WHERE id = ?", (trade_id,))
                qty_result = cursor.fetchone()
                if qty_result:
                    remaining_qty = qty_result[0]
                else:
                    logger.error(f"Cannot determine quantity for trade #{trade_id}")
                    return
            
            # Calculate final PNL on remaining
            if side == 'buy':
                final_pnl = (exit_price - entry_price) * remaining_qty
            else:
                final_pnl = (entry_price - exit_price) * remaining_qty
            
            total_pnl = partial_pnl + final_pnl
            
            # 🚨 CRITICAL FIX: Execute actual exchange order before database update
            try:
                logger.info(f"🔄 Executing close order for {symbol}: {remaining_qty} units")
                
                # Determine order side (opposite of entry)
                close_side = 'sell' if side == 'buy' else 'buy'
                
                # Execute the close order on WooX
                order_result = self.exchange.create_market_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=remaining_qty
                )
                
                logger.info(f"✅ Exchange order executed: {order_result}")
                
            except Exception as exchange_error:
                logger.error(f"❌ CRITICAL: Failed to execute close order on exchange: {exchange_error}")
                # Continue with database update anyway to prevent desync
                # But mark it clearly in the notes
                reason = f"{reason} - EXCHANGE ERROR: {str(exchange_error)[:100]}"
            
            # Close the trade in database
            cursor.execute("""
                UPDATE trades
                SET status = 'closed',
                    exit_price = ?,
                    exit_time = CURRENT_TIMESTAMP,
                    remaining_quantity = 0,
                    pnl = ?,
                    notes = ?
                WHERE id = ?
            """, (exit_price, total_pnl, reason, trade_id))
            
            conn.commit()
            
            if "Breakeven" in reason:
                logger.info(f"✅ #{trade_id} {symbol} - {reason} @ ${exit_price:.4f} - Total PNL: ${total_pnl:.2f}")
            else:
                logger.info(f"📊 #{trade_id} {symbol} - {reason} @ ${exit_price:.4f} - Total PNL: ${total_pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def calculate_portfolio_heat(self) -> Dict:
        """Calculate portfolio heat excluding FREE TRADES"""
        
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT entry_price, stop_loss, remaining_quantity, leverage, symbol, partial_exits_done
            FROM trades
            WHERE status = 'open'
        """)
        
        total_risk = 0
        free_trades = []
        risky_trades = []
        account_balance = 5000.0
        
        for row in cursor.fetchall():
            entry, stop, qty, leverage, symbol, partials = row
            leverage = leverage or 1.0
            qty = qty or 0
            
            if stop and stop > 0 and qty:
                # Check if FREE TRADE
                if stop >= entry:  # Long position with stop at/above entry
                    free_trades.append(symbol)
                    risk = 0
                else:
                    risk = abs(entry - stop) * qty * leverage
                    risky_trades.append(symbol)
            elif qty:
                # No stop = full risk
                risk = entry * qty * leverage * 0.03  # Assume 3% risk if no stop
                risky_trades.append(symbol)
            else:
                risk = 0
            
            total_risk += risk
        
        conn.close()
        
        heat_percent = (total_risk / account_balance) * 100
        
        return {
            'total_risk': total_risk,
            'heat_percent': heat_percent,
            'free_trades_count': len(free_trades),
            'risky_trades_count': len(risky_trades),
            'free_trades': free_trades[:5],  # Show first 5
            'can_open_more': heat_percent < 2.0
        }
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("🔄 Starting enhanced monitoring loop...")
        
        check_counter = 0
        while True:
            try:
                trades = await self.get_open_trades()
                
                if not trades:
                    logger.info("📭 No open trades found")
                    await asyncio.sleep(self.check_interval)
                    continue
                
                # Log portfolio heat every 10 checks (about 50 seconds)
                check_counter += 1
                if check_counter % 10 == 0:
                    heat_stats = self.calculate_portfolio_heat()
                    logger.info(f"📊 Portfolio Heat: {heat_stats['heat_percent']:.2f}% | "
                              f"Free Trades: {heat_stats['free_trades_count']} | "
                              f"At Risk: {heat_stats['risky_trades_count']}")
                
                # Process each trade
                logger.debug(f"🔍 Checking {len(trades)} trades...")
                checked = 0
                errors = 0
                
                for trade in trades:
                    try:
                        ticker = self.exchange.fetch_ticker(trade['symbol'])
                        current_price = ticker['last']
                        checked += 1
                        
                        # Log every 10th trade check for monitoring
                        if checked % 10 == 0:
                            logger.debug(f"✅ Checked {checked}/{len(trades)} trades")
                        
                        result = await self.check_exit_conditions(trade, current_price)
                        if result:
                            logger.info(f"🎯 #{trade['id']} {trade['symbol']}: {result}")
                            
                    except Exception as e:
                        if "does not have market symbol" not in str(e):
                            errors += 1
                            logger.error(f"❌ Error checking trade {trade['id']} {trade['symbol']}: {e}")
                
                if errors > 0:
                    logger.warning(f"⚠️ Checked {checked} trades with {errors} errors")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(self.check_interval)

async def main():
    """Main entry point"""
    monitor = EnhancedExitMonitor()
    
    # Show initial stats
    heat_stats = monitor.calculate_portfolio_heat()
    logger.info("="*60)
    logger.info("🚀 ENHANCED EXIT MONITOR V2 STARTING")
    logger.info("="*60)
    logger.info(f"💰 Account Balance: $5,000")
    logger.info(f"🔥 Portfolio Heat: {heat_stats['heat_percent']:.2f}%")
    logger.info(f"🆓 Free Trades: {heat_stats['free_trades_count']}")
    logger.info(f"⚠️  At Risk Trades: {heat_stats['risky_trades_count']}")
    if heat_stats['can_open_more']:
        logger.info(f"✅ Can open more trades (heat < 2%)")
    else:
        logger.info(f"❌ Cannot open more trades (heat >= 2%)")
    logger.info("="*60)
    
    # Start monitoring
    await monitor.monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())