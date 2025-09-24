#!/usr/bin/env python3
"""
Gauls Update Monitor - Monitors for Gauls signals and executes partials automatically
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import asyncio
import sqlite3
import logging
import re
from datetime import datetime, timedelta
from processors.gauls_partial_executor import GaulsPartialExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('GaulsUpdateMonitor')

class GaulsUpdateMonitor:
    def __init__(self, mode='production'):
        self.mode = mode
        self.executor = GaulsPartialExecutor(mode)
        self.sage_db = f'/opt/sage-trading-system/sage_trading{"_production" if mode == "production" else ""}.db'
        self.processed_messages = set()
        
        # Patterns to detect updates
        self.patterns = {
            '+1R': re.compile(r'\+1R\s+(done|reached|hit)', re.IGNORECASE),
            '+2R': re.compile(r'\+2R\s+(done|reached|hit)', re.IGNORECASE),
            '+3R': re.compile(r'\+3R\s+(done|reached|hit)', re.IGNORECASE),
            'partial': re.compile(r'(book|take)\s+(\d+)%\s+partial', re.IGNORECASE),
            'risk_free': re.compile(r'(risk.?free|move.?sl.?to.?(entry|breakeven))', re.IGNORECASE),
            'close': re.compile(r'(close|exit|out)\s+(full|all|position)', re.IGNORECASE),
            'early_close': re.compile(r'(closing\s+it\s+in|cutting\s+loss|stop\s+out|-[\d.]+R\s+loss)', re.IGNORECASE),
            'weekend_close': re.compile(r'(weekend\s+closing|friday\s+close)', re.IGNORECASE)
        }
        
    def extract_symbol_from_message(self, message: str) -> str:
        """Extract trading symbol from Gauls message"""
        # Look for patterns like AI/USDT, BTC/USDT, $PYTH, etc.
        
        # First try standard format: SYMBOL/USDT
        symbol_pattern = re.compile(r'([A-Z]{2,10})[/\s]+USDT', re.IGNORECASE)
        match = symbol_pattern.search(message)
        if match:
            return f"{match.group(1).upper()}/USDT"
        
        # Then try $ format: $PYTH, $BTC, etc.
        dollar_pattern = re.compile(r'\$([A-Z]{2,10})\b', re.IGNORECASE)
        match = dollar_pattern.search(message)
        if match:
            return f"{match.group(1).upper()}/USDT"
            
        return None
    
    async def check_for_updates(self):
        """Check for new Gauls messages with trade updates"""
        conn = sqlite3.connect(self.sage_db)
        cursor = conn.cursor()
        
        # Get recent messages (last hour)
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        cursor.execute("""
            SELECT id, message_text, timestamp
            FROM raw_telegram_messages
            WHERE timestamp > ?
                AND (message_text LIKE '%TRADE UPDATE%'
                    OR message_text LIKE '%+1R%'
                    OR message_text LIKE '%+2R%'
                    OR message_text LIKE '%partial%'
                    OR message_text LIKE '%risk free%')
            ORDER BY timestamp DESC
            LIMIT 20
        """, (one_hour_ago,))
        
        messages = cursor.fetchall()
        conn.close()
        
        for msg_id, message_text, timestamp in messages:
            if msg_id in self.processed_messages:
                continue
                
            # Extract symbol
            symbol = self.extract_symbol_from_message(message_text)
            if not symbol:
                continue
                
            logger.info(f"📨 Found Gauls update for {symbol}")
            logger.info(f"   Message: {message_text[:100]}...")
            
            # Determine signal type
            signal_type = None
            
            if self.patterns['+1R'].search(message_text):
                signal_type = '+1R done'
            elif self.patterns['+2R'].search(message_text):
                signal_type = '+2R done'
            elif self.patterns['+3R'].search(message_text):
                signal_type = '+3R done (full close)'
            elif self.patterns['risk_free'].search(message_text):
                signal_type = 'move SL to BE'
            elif self.patterns['early_close'].search(message_text):
                signal_type = 'early close (cut loss)'
            elif self.patterns['weekend_close'].search(message_text):
                signal_type = 'weekend close'
            elif self.patterns['close'].search(message_text):
                signal_type = 'close position'
            elif self.patterns['partial'].search(message_text):
                match = self.patterns['partial'].search(message_text)
                if match:
                    percent = match.group(2)
                    signal_type = f'take {percent}% partial'
            
            if signal_type:
                logger.info(f"🎯 Signal detected: {signal_type} for {symbol}")
                
                # Execute the signal
                success = self.executor.process_gauls_signal(symbol, signal_type)
                
                if success:
                    logger.info(f"✅ Successfully processed {signal_type} for {symbol}")
                else:
                    logger.warning(f"⚠️ Could not process {signal_type} for {symbol}")
                
                # Mark as processed
                self.processed_messages.add(msg_id)
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info(f"🚀 Starting Gauls Update Monitor in {self.mode} mode")
        logger.info("📡 Monitoring for partial profit signals...")
        
        while True:
            try:
                await self.check_for_updates()
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in monitor loop: {e}")
                await asyncio.sleep(30)

async def main():
    """Main function"""
    import os
    mode = os.getenv('TRADING_MODE', 'production')
    monitor = GaulsUpdateMonitor(mode=mode)
    await monitor.monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())