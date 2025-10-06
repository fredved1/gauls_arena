#!/usr/bin/env python3
"""
Gauls Trade Update Processor - Handles Gauls' partial profit and SL movement instructions
Integrates with existing exit_monitor_v2.py for seamless operation
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import asyncio
import sqlite3
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from core.unified_exchange import UnifiedExchange

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('GaulsUpdateProcessor')

class GaulsTradeUpdateProcessor:
    def __init__(self, mode='production'):
        """Initialize the Gauls trade update processor"""
        self.mode = mode
        self.exchange = UnifiedExchange()
        
        # Database paths - USE GAULS DATABASES!
        self.trades_db = '/gauls-copy-trading-system/databases/trades.db'
        self.sage_db = '/gauls-copy-trading-system/databases/gauls_trading.db'
        
        # Track processed updates to avoid duplicates
        self.processed_updates = set()
        self.load_processed_updates()
        
        # Update patterns to detect - Enhanced for multi-symbol updates
        self.update_patterns = {
            # Split into action words (trigger partial) vs info words (no partial)
            'r_action': re.compile(r'(\d+\.?\d*)R\s+(locked|done|reached|secured|taken)', re.IGNORECASE),
            'r_info': re.compile(r'(\d+\.?\d*)R\s+(?:profit\s+)?running', re.IGNORECASE),
            'risk_free': re.compile(r'risk.?free|move.*?(?:sl|stop.*?loss).*?(?:to|at).*?(?:entry|breakeven)|sl.?to.?breakeven|trade.*risk.free|moving.*?stop.*?to.*?entry', re.IGNORECASE),
            'book_partial': re.compile(r'book\s+(\d+)%|take\s+(\d+)%|partial.*(\d+)%', re.IGNORECASE),
            'full_exit': re.compile(r'clos(?:e|ing)\s+(?:it\s+)?here|exit|out|done', re.IGNORECASE),
            # New patterns for multi-symbol updates
            'symbol_line': re.compile(r'(?:👉🏻|•|-)\s*\$([A-Z]{2,10})\s*[—–-]\s*(.+?)(?=\n|👉|$)', re.MULTILINE | re.DOTALL),
            'both_all': re.compile(r'\b(?:both|all)\s+(?:trades?|positions?)\b', re.IGNORECASE),
            'let_cook': re.compile(r'let(?:ting)?\s+(?:the\s+)?(?:final\s+)?targets?\s+cook|patience|hold', re.IGNORECASE),
            'entries_filled': re.compile(r'(?:both\s+)?entries?\s+filled', re.IGNORECASE)
        }
        
    def load_processed_updates(self):
        """Load previously processed update IDs from database"""
        conn = sqlite3.connect(self.sage_db)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_gauls_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_hash TEXT UNIQUE,
                symbol TEXT,
                action_taken TEXT,
                processed_at TIMESTAMP
            )
        ''')
        
        # Load existing processed updates
        cursor.execute('SELECT message_hash FROM processed_gauls_updates')
        self.processed_updates = {row[0] for row in cursor.fetchall()}
        conn.close()
        
    async def scan_for_updates(self):
        """Scan for new Gauls trade update messages"""
        conn = sqlite3.connect(self.sage_db)
        cursor = conn.cursor()
        
        # Get recent messages (last 6 hours to catch missed updates) 
        # Convert to Unix timestamp to match database format
        cutoff_time = int((datetime.now() - timedelta(hours=6)).timestamp())
        cursor.execute('''
            SELECT message_text, timestamp 
            FROM all_gauls_messages 
            WHERE timestamp > ? 
            AND (message_text LIKE '%UPDATE%' OR message_text LIKE '%R locked%' OR message_text LIKE '%R done%' OR message_text LIKE '%R reached%')
            ORDER BY timestamp DESC
        ''', (cutoff_time,))
        
        messages = cursor.fetchall()
        conn.close()
        
        for message_text, timestamp in messages:
            # Create hash for duplicate detection
            message_hash = hash(f"{message_text}_{timestamp}")
            
            if message_hash not in self.processed_updates:
                await self.process_update_message(message_text, timestamp, message_hash)
                
    async def process_update_message(self, message_text: str, timestamp: str, message_hash: int):
        """Process a Gauls trade update message (handles multi-symbol)"""
        # Check if this is a multi-symbol update
        symbol_updates = self.extract_symbol_updates(message_text)
        
        if not symbol_updates:
            # Fallback to single symbol extraction
            symbol_match = re.search(r'\$([A-Z]{2,10})', message_text, re.IGNORECASE)
            if not symbol_match:
                symbol_match = re.search(r'([A-Z]{2,10})(?=\s*(UPDATE|TRADE|:))', message_text, re.IGNORECASE)
            if not symbol_match:
                return
            
            symbol_updates = {symbol_match.group(1): {'r_value': None, 'r_action': None}}
        
        # Check for generic instructions that apply to all symbols
        generic_instructions = self.extract_generic_instructions(message_text)
        
        # Process each symbol
        for symbol, symbol_data in symbol_updates.items():
            symbol_usdt = f"{symbol}/USDT"
            
            # Find matching open trades
            trades = await self.get_matching_trades(symbol_usdt)
            if not trades:
                logger.info(f"📭 No open trades found for {symbol_usdt} update")
                continue
            
            # Determine action based on message content and generic instructions
            action = self.determine_action_enhanced(message_text, symbol_data, generic_instructions)
            
            if action:
                logger.info(f"🎯 Processing Gauls update for {symbol_usdt}: {action['type']}")
                
                for trade in trades:
                    success = await self.execute_action(trade, action)
                    
                    if success:
                        # Mark as processed
                        self.mark_as_processed(message_hash, symbol_usdt, action['type'])
                        logger.info(f"✅ Successfully processed {action['type']} for {symbol_usdt} trade #{trade['id']}")
                    
    def extract_symbol_updates(self, message_text: str) -> Dict:
        """Extract all symbols and their individual updates"""
        updates = {}
        
        # Look for symbol-specific lines (e.g., "👉🏻 $SOL — ...")
        for match in self.update_patterns['symbol_line'].finditer(message_text):
            symbol = match.group(1)
            content = match.group(2)
            
            # Extract R value for this symbol - check both action and info patterns
            r_match = self.update_patterns['r_action'].search(content)
            is_action_word = True
            if not r_match:
                r_match = self.update_patterns['r_info'].search(content)
                is_action_word = False
            
            r_value = float(r_match.group(1)) if r_match else None
            # Group 2 only exists for r_action pattern
            if r_match and is_action_word and len(r_match.groups()) > 1:
                r_action = r_match.group(2).lower()
            elif r_match and not is_action_word:
                r_action = 'running'  # Info pattern means "running"
            else:
                r_action = None
            
            updates[symbol] = {
                'r_value': r_value,
                'r_action': r_action,
                'content': content
            }
        
        return updates
    
    def extract_generic_instructions(self, message_text: str) -> Dict:
        """Extract instructions that apply to all symbols"""
        instructions = {}
        
        # Check for "both/all trades should be risk-free"
        has_risk_free = bool(self.update_patterns['risk_free'].search(message_text))
        has_both_all = bool(self.update_patterns['both_all'].search(message_text))
        
        if has_risk_free and has_both_all:
            instructions['all_risk_free'] = True
        
        # Check for "let targets cook" / hold instructions
        if self.update_patterns['let_cook'].search(message_text):
            instructions['let_cook'] = True
            instructions['no_partial_exit'] = True
        
        return instructions
    
    def determine_action_enhanced(self, message_text: str, symbol_data: Dict, generic_instructions: Dict) -> Optional[Dict]:
        """Enhanced action determination with generic instruction support"""
        
        # Priority 1: Check for generic risk-free instruction
        if generic_instructions.get('all_risk_free'):
            action = {
                'type': 'risk_free_generic',
                'move_sl_to': 'breakeven'
            }
            
            # IMPORTANT: Only add partial exit if explicitly NOT "let cook"
            # "Risk-free" alone doesn't mean take profit!
            if generic_instructions.get('let_cook') or generic_instructions.get('no_partial_exit'):
                # Explicitly told to let targets cook - NO partial exit
                pass  # No partial_percent added
            else:
                # Only if there's NO "let cook" instruction, check for standard R-based partial
                # But this should be rare - usually risk-free just means move SL
                pass  # Don't automatically add 40% - let explicit instructions handle it
            
            return action
        
        # Priority 2: Use standard determination for specific R values
        return self.determine_action(message_text)
    
    def determine_action(self, message_text: str) -> Optional[Dict]:
        """Determine what action to take based on message"""
        # Check for R ACTION pattern (e.g., "1.25R locked") - these trigger partial exits
        r_match = self.update_patterns['r_action'].search(message_text)
        if r_match:
            r_value = float(r_match.group(1))
            
            if r_value >= 1.0 and r_value < 2.0:
                # First R level reached (1R to 1.99R) - Take 40% profit and move SL to breakeven
                return {
                    'type': f'{r_value}R_partial',
                    'partial_percent': 40,
                    'move_sl_to': 'breakeven',
                    'r_value': r_value
                }
            elif r_value >= 2.0:
                # Second R level reached (2R+) - Take another 30% profit
                return {
                    'type': f'{r_value}R_partial', 
                    'partial_percent': 30,
                    'r_value': r_value
                }
            
        # Check for specific percentage booking
        book_match = self.update_patterns['book_partial'].search(message_text)
        if book_match:
            percent = None
            for group in book_match.groups():
                if group and group.isdigit():
                    percent = int(group)
                    break
                    
            if percent:
                return {
                    'type': 'book_partial',
                    'partial_percent': percent
                }
                
        # Check for risk-free instruction
        if self.update_patterns['risk_free'].search(message_text):
            action = {
                'type': 'make_risk_free',
                'move_sl_to': 'breakeven'
            }
            # Don't automatically add partial exit!
            # Risk-free means move SL to breakeven, not necessarily take profit
            # Only add partial if explicitly mentioned elsewhere in the message
            if self.update_patterns['book_partial'].search(message_text):
                book_match = self.update_patterns['book_partial'].search(message_text)
                if book_match:
                    for group in book_match.groups():
                        if group and group.isdigit():
                            action['partial_percent'] = int(group)
                            break
            return action
            
        # Check for full exit - allow closing instructions in trade updates
        if self.update_patterns['full_exit'].search(message_text):
            return {
                'type': 'full_exit',
                'partial_percent': 100
            }
            
        return None
        
    async def get_matching_trades(self, symbol: str) -> List[Dict]:
        """Get open trades matching the symbol"""
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, symbol, side, entry_price, quantity, stop_loss, take_profit_1,
                   original_quantity, partial_exits_done, remaining_quantity, leverage, strategy
            FROM trades 
            WHERE symbol = ? AND status = 'open' AND strategy = 'gauls_copy'
        ''', (symbol,))
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'id': row[0],
                'symbol': row[1],
                'side': row[2],
                'entry_price': row[3],
                'quantity': row[4],
                'stop_loss': row[5],
                'take_profit_1': row[6],
                'original_quantity': row[7] or row[4],
                'partial_exits_done': row[8] or 0,
                'remaining_quantity': row[9] or row[4],
                'leverage': row[10] or 1,
                'strategy': row[11]
            })
            
        conn.close()
        return trades
        
    async def execute_action(self, trade: Dict, action: Dict) -> bool:
        """Execute the determined action on the trade"""
        try:
            symbol = trade['symbol']
            remaining_qty = trade['remaining_quantity']

            # Calculate partial quantity (default to 0 if not specified)
            partial_percent = action.get('partial_percent', 0)
            partial_qty = remaining_qty * (partial_percent / 100)
            
            if partial_qty > 0:
                # Get current price
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                # Execute partial close
                if partial_percent < 100:
                    logger.info(f"📊 Taking {partial_percent}% partial on {symbol}")
                    
                    # Place market sell order for partial
                    order = self.exchange.create_order(
                        symbol=symbol,
                        order_type='market',
                        side='sell' if trade['side'] == 'buy' else 'buy',
                        amount=partial_qty
                    )
                    
                    # Update database with partial exit
                    await self.update_trade_partial(trade['id'], partial_qty, current_price, action['type'])
                    
                else:
                    # Full exit
                    logger.info(f"🏁 Closing full position on {symbol}")
                    order = self.exchange.create_order(
                        symbol=symbol,
                        order_type='market',
                        side='sell' if trade['side'] == 'buy' else 'buy',
                        amount=remaining_qty
                    )
                    
                    # Update database with full exit
                    await self.close_trade(trade['id'], current_price)
                    
            # Move stop loss if requested
            if action.get('move_sl_to') == 'breakeven':
                logger.info(f"🛡️ Moving SL to breakeven for {symbol}")
                await self.move_stop_to_breakeven(trade)
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error executing action: {e}")
            return False
            
    async def update_trade_partial(self, trade_id: int, partial_qty: float, exit_price: float, action_type: str):
        """Update trade with partial exit information using correct table structure"""
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        # Calculate PnL for this partial exit
        cursor.execute('SELECT side, entry_price, leverage FROM trades WHERE id = ?', (trade_id,))
        side, entry_price, leverage = cursor.fetchone()
        leverage = leverage or 1
        
        if side == 'buy':
            pnl = (exit_price - entry_price) * partial_qty
        else:
            pnl = (entry_price - exit_price) * partial_qty
        
        # Insert into partial_exits table
        cursor.execute('''
            INSERT INTO partial_exits (trade_id, exit_price, quantity_exited, pnl, tp_level, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (trade_id, exit_price, partial_qty, pnl, 1 if '1' in action_type else 2, f'Gauls {action_type}'))
        
        # Update main trade
        cursor.execute('''
            UPDATE trades 
            SET remaining_quantity = remaining_quantity - ?,
                partial_exits_done = partial_exits_done + 1,
                partial_pnl = partial_pnl + ?,
                notes = notes || ?
            WHERE id = ?
        ''', (partial_qty, pnl, f' | Gauls {action_type}', trade_id))
            
        conn.commit()
        conn.close()
        
    async def move_stop_to_breakeven(self, trade: Dict):
        """Move stop loss to breakeven (entry price)"""
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        # Calculate breakeven including fees (add 0.1% for fees)
        breakeven = trade['entry_price'] * (1.001 if trade['side'] == 'buy' else 0.999)
        
        cursor.execute('''
            UPDATE trades 
            SET stop_loss = ?,
                notes = notes || ' | SL moved to breakeven'
            WHERE id = ?
        ''', (breakeven, trade['id']))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Moved SL to breakeven ({breakeven:.4f}) for trade #{trade['id']}")
        
    async def close_trade(self, trade_id: int, exit_price: float):
        """Close the trade completely"""
        conn = sqlite3.connect(self.trades_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trades 
            SET status = 'closed',
                exit_price = ?,
                exit_time = ?,
                notes = notes || ' | Closed by Gauls update'
            WHERE id = ?
        ''', (exit_price, datetime.now().isoformat(), trade_id))
        
        conn.commit()
        conn.close()
        
    def mark_as_processed(self, message_hash: int, symbol: str, action: str):
        """Mark update message as processed"""
        conn = sqlite3.connect(self.sage_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO processed_gauls_updates (message_hash, symbol, action_taken, processed_at)
            VALUES (?, ?, ?, ?)
        ''', (str(message_hash), symbol, action, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        self.processed_updates.add(message_hash)
        
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info(f"🚀 Starting Gauls Trade Update Processor in {self.mode} mode")
        
        while True:
            try:
                await self.scan_for_updates()
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"❌ Error in monitor loop: {e}")
                await asyncio.sleep(60)

async def main():
    """Main function"""
    mode = os.getenv('TRADING_MODE', 'production')
    processor = GaulsTradeUpdateProcessor(mode=mode)
    await processor.monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())