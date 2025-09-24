#!/usr/bin/env python3
"""
Automated Gauls Partial Executor for WooX Futures
Handles partial profit taking when Gauls signals arrive
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import os
import sqlite3
import logging
import ccxt
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Optional

# Load environment
load_dotenv('/opt/sage-trading-system/.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('GaulsPartialExecutor')

class GaulsPartialExecutor:
    def __init__(self, mode='production'):
        self.mode = mode
        self.trades_db = f'/opt/sage-trading-system/trades{"_production" if mode == "production" else ""}.db'
        
        # Initialize WooX exchange for futures
        self.exchange = ccxt.woo({
            'apiKey': os.getenv('WOOX_API_KEY'),
            'secret': os.getenv('WOOX_API_SECRET'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'  # Use futures/perpetual
            }
        })
        
    def get_position_from_exchange(self, symbol: str) -> Optional[Dict]:
        """Get actual position from WooX futures"""
        try:
            positions = self.exchange.fetch_positions()
            
            # Convert symbol format (AI/USDT -> AI/USDT:USDT for futures)
            futures_symbol = f"{symbol}:USDT" if ':' not in symbol else symbol
            
            for pos in positions:
                if symbol.replace('/USDT', '') in pos['symbol']:
                    return {
                        'symbol': pos['symbol'],
                        'contracts': pos['contracts'],
                        'side': pos['side'],
                        'mark_price': pos.get('markPrice', 0),
                        'entry_price': pos.get('entryPrice', 0),
                        'unrealized_pnl': pos.get('unrealizedPnl', 0)
                    }
        except Exception as e:
            logger.error(f"Error fetching position: {e}")
        return None
    
    def execute_partial_close(self, trade: Dict, partial_percent: float = 40) -> bool:
        """Execute partial close on WooX futures position"""
        try:
            symbol = trade['symbol']
            
            # Get actual position from exchange
            position = self.get_position_from_exchange(symbol)
            if not position:
                logger.error(f"No position found on exchange for {symbol}")
                return False
            
            # Calculate partial quantity
            current_contracts = position['contracts']
            partial_qty = current_contracts * (partial_percent / 100)
            
            logger.info(f"📊 Executing partial close for {symbol}")
            logger.info(f"   Current position: {current_contracts}")
            logger.info(f"   Closing {partial_percent}%: {partial_qty:.4f}")
            
            # Build futures symbol
            futures_symbol = position['symbol']
            
            # Execute reduce-only market sell for long positions
            if position['side'] == 'long':
                order = self.exchange.create_market_sell_order(
                    symbol=futures_symbol,
                    amount=partial_qty,
                    params={'reduce_only': True}
                )
            else:  # short position
                order = self.exchange.create_market_buy_order(
                    symbol=futures_symbol,
                    amount=partial_qty,
                    params={'reduce_only': True}
                )
            
            logger.info(f"✅ Order placed: {order['id']}")
            
            # Calculate remaining position
            remaining_qty = current_contracts - partial_qty
            
            # Update database with partial execution
            self.update_database_partial(
                trade_id=trade['id'],
                partial_qty=partial_qty,
                exit_price=position['mark_price'],
                remaining_qty=remaining_qty,
                partial_number=1 if trade['partial_1_qty'] is None else 2
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error executing partial: {e}")
            return False
    
    def update_database_partial(self, trade_id: int, partial_qty: float, 
                                exit_price: float, remaining_qty: float,
                                partial_number: int = 1):
        """Update database with partial execution details"""
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        try:
            if partial_number == 1:
                # First partial (1R)
                cursor.execute("""
                    UPDATE trades 
                    SET partial_1_qty = ?,
                        partial_1_price = ?,
                        partial_1_time = ?,
                        remaining_qty = ?,
                        notes = COALESCE(notes, '') || ' | +1R partial taken via Gauls signal'
                    WHERE id = ?
                """, (partial_qty, exit_price, datetime.now().isoformat(), remaining_qty, trade_id))
                
            elif partial_number == 2:
                # Second partial (2R)
                cursor.execute("""
                    UPDATE trades 
                    SET partial_2_qty = ?,
                        partial_2_price = ?,
                        partial_2_time = ?,
                        remaining_qty = ?,
                        notes = COALESCE(notes, '') || ' | +2R partial taken via Gauls signal'
                    WHERE id = ?
                """, (partial_qty, exit_price, datetime.now().isoformat(), remaining_qty, trade_id))
            
            conn.commit()
            logger.info(f"✅ Database updated for trade #{trade_id}")
            
        except Exception as e:
            logger.error(f"Database update error: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def move_stop_to_breakeven(self, trade: Dict) -> bool:
        """Move stop loss to breakeven (entry price)"""
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE trades 
                SET stop_loss = ?,
                    notes = COALESCE(notes, '') || ' | SL moved to breakeven'
                WHERE id = ?
            """, (trade['entry_price'], trade['id']))
            
            conn.commit()
            logger.info(f"✅ Stop loss moved to breakeven for trade #{trade['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error moving stop loss: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def execute_full_close(self, trade: Dict, reason: str = "full close") -> bool:
        """Execute full position close on WooX futures"""
        try:
            symbol = trade['symbol']
            
            # Get actual position from exchange
            position = self.get_position_from_exchange(symbol)
            if not position:
                logger.error(f"No position found on exchange for {symbol}")
                return False
            
            # Get current position size
            current_contracts = position['contracts']
            
            logger.info(f"📊 Executing full close for {symbol}")
            logger.info(f"   Current position: {current_contracts}")
            logger.info(f"   Reason: {reason}")
            
            # Build futures symbol
            futures_symbol = position['symbol']
            
            # Execute reduce-only market order to close entire position
            if position['side'] == 'long':
                order = self.exchange.create_market_sell_order(
                    symbol=futures_symbol,
                    amount=current_contracts,
                    params={'reduce_only': True}
                )
            else:  # short position
                order = self.exchange.create_market_buy_order(
                    symbol=futures_symbol,
                    amount=current_contracts,
                    params={'reduce_only': True}
                )
            
            logger.info(f"✅ Full close order placed: {order['id']}")
            
            # Update database to close the trade
            conn = sqlite3.connect(self.trades_db)
            cursor = conn.cursor()
            
            # Calculate P&L
            exit_price = position['mark_price']
            entry_price = trade['entry_price']
            
            if trade['side'] == 'buy':
                pnl = (exit_price - entry_price) * current_contracts
            else:
                pnl = (entry_price - exit_price) * current_contracts
                
            # Apply leverage if exists
            leverage = trade.get('leverage', 1)
            if leverage > 1:
                pnl *= leverage
            
            cursor.execute("""
                UPDATE trades 
                SET status = 'closed',
                    exit_price = ?,
                    exit_time = ?,
                    pnl = ?,
                    notes = COALESCE(notes, '') || ?
                WHERE id = ?
            """, (exit_price, datetime.now().isoformat(), pnl, 
                  f' | Closed by Gauls signal: {reason}', trade['id']))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Trade #{trade['id']} closed - P&L: ${pnl:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error executing full close: {e}")
            return False
    
    def process_gauls_signal(self, symbol: str, signal_type: str):
        """Process a Gauls signal for a specific symbol"""
        
        # Get open trade from database
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, symbol, side, entry_price, stop_loss, quantity,
                   partial_1_qty, partial_2_qty, remaining_qty, leverage
            FROM trades 
            WHERE symbol = ? AND status = 'open'
            ORDER BY entry_time DESC
            LIMIT 1
        """, (symbol,))
        
        trade_row = cursor.fetchone()
        conn.close()
        
        if not trade_row:
            logger.warning(f"No open trade found for {symbol}")
            return False
        
        trade = {
            'id': trade_row[0],
            'symbol': trade_row[1],
            'side': trade_row[2],
            'entry_price': trade_row[3],
            'stop_loss': trade_row[4],
            'quantity': trade_row[5],
            'partial_1_qty': trade_row[6],
            'partial_2_qty': trade_row[7],
            'remaining_qty': trade_row[8] or trade_row[5],
            'leverage': trade_row[9] or 1
        }
        
        logger.info(f"📋 Processing {signal_type} signal for {symbol}")
        
        # Determine action based on signal
        if 'move SL' in signal_type or 'risk free' in signal_type.lower():
            # Just move stop loss to breakeven, no partial
            if self.move_stop_to_breakeven(trade):
                logger.info(f"✅ Stop loss moved to breakeven for {symbol}")
                return True
                
        elif '1R' in signal_type or 'first partial' in signal_type.lower():
            if trade['partial_1_qty'] is None:
                # Take first partial (40%)
                if self.execute_partial_close(trade, 40):
                    self.move_stop_to_breakeven(trade)
                    logger.info(f"✅ 1R partial completed for {symbol}")
                    return True
            else:
                logger.info(f"1R partial already taken for {symbol}")
                
        elif '2R' in signal_type or 'second partial' in signal_type.lower():
            if trade['partial_2_qty'] is None:
                # Take second partial (30% of original)
                if self.execute_partial_close(trade, 30):
                    logger.info(f"✅ 2R partial completed for {symbol}")
                    return True
            else:
                logger.info(f"2R partial already taken for {symbol}")
                
        elif '3R' in signal_type:
            # +3R is typically final target - close full position
            logger.info(f"🎯 +3R reached - closing full position for {symbol}")
            if self.execute_full_close(trade, "+3R target reached"):
                logger.info(f"✅ Full position closed at +3R for {symbol}")
                return True
                
        elif 'close' in signal_type.lower() or 'exit' in signal_type.lower() or 'cut loss' in signal_type.lower():
            # Close remaining position (including early exits/stop losses)
            reason = "early exit" if 'early' in signal_type.lower() or 'cut' in signal_type.lower() else "full close"
            logger.info(f"📤 Executing {reason} for {symbol}")
            
            if self.execute_full_close(trade, reason):
                logger.info(f"✅ Full position closed for {symbol} - {reason}")
                return True
                
        return False

def test_executor():
    """Test the executor with AI/USDT"""
    executor = GaulsPartialExecutor(mode='production')
    
    # Check current position
    position = executor.get_position_from_exchange('AI/USDT')
    if position:
        print(f"\n📊 Current AI/USDT position on WooX:")
        print(f"   Size: {position['contracts']} contracts")
        print(f"   Side: {position['side']}")
        print(f"   Mark Price: ${position['mark_price']}")
        print(f"   Unrealized PNL: ${position['unrealized_pnl']:.2f}")
    else:
        print("No AI/USDT position found on exchange")

if __name__ == "__main__":
    test_executor()