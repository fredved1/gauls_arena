#!/usr/bin/env python3
"""
Live Telegram Listener for Gauls Messages
Captures messages in real-time and stores them in Sage database
"""

import asyncio
import os
import sys
import sqlite3
import json
import logging
from datetime import datetime
sys.path.insert(0, '/gauls-copy-trading-system/src')

from telethon import TelegramClient, events
from core.config import Config
from utils.gauls_memory_system import GaulsMemorySystem

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/gauls-copy-trading-system/logs/telegram_listener.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LiveTelegramListener:
    def __init__(self):
        self.config = Config.from_env()
        self.session_path = '/gauls-copy-trading-system/trading_session'
        self.client = None
        self.memory_system = GaulsMemorySystem()
        
    async def start_listening(self):
        """Start listening for Telegram messages"""
        logger.info("🚀 Starting live Telegram listener...")
        
        self.client = TelegramClient(
            self.session_path,
            self.config.telegram.api_id,
            self.config.telegram.api_hash
        )
        
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.error("❌ Telegram session not authorized")
                return
            
            logger.info("✅ Connected to Telegram successfully")
            
            # Try to get entity first
            try:
                channel_id = int(self.config.telegram.channel_id)
                entity = await self.client.get_entity(channel_id)
                logger.info(f"✅ Channel found: {entity.title}")
                
                # Register event handler for new messages with better debugging
                @self.client.on(events.NewMessage(chats=[entity]))
                async def handle_new_message(event):
                    logger.info(f"🚨 LIVE MESSAGE EVENT TRIGGERED!")
                    logger.info(f"   Channel: {event.chat.title if hasattr(event.chat, 'title') else 'Unknown'}")
                    logger.info(f"   Message ID: {event.message.id}")
                    logger.info(f"   Timestamp: {event.message.date}")
                    await self.process_message(event.message)
                
                # Also register for message edits (in case messages are edited)
                @self.client.on(events.MessageEdited(chats=[entity]))
                async def handle_edited_message(event):
                    logger.info(f"✏️ MESSAGE EDIT EVENT TRIGGERED!")
                    await self.process_message(event.message)
                
                logger.info("🎯 Listening for new messages...")
                logger.info(f"🎯 Monitoring channel: {entity.title} (ID: {entity.id})")
                
                # Keep the connection alive
                await self.client.run_until_disconnected()
                
            except Exception as e:
                logger.error(f"❌ Channel access failed: {e}")
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
        finally:
            if self.client:
                await self.client.disconnect()
    
    async def process_message(self, message):
        """Process incoming Telegram message"""
        try:
            if not message.text:
                logger.info("⚠️ Message has no text content, skipping")
                return
                
            logger.info(f"📨 NEW MESSAGE PROCESSING:")
            logger.info(f"   📅 Date: {message.date}")
            logger.info(f"   🆔 Message ID: {message.id}")
            logger.info(f"   📝 Content: {message.text[:150]}...")
            logger.info(f"   📏 Length: {len(message.text)} characters")
            
            # Store in memory system
            logger.info("🧠 Processing through GaulsMemorySystem...")
            insight_id = await self.memory_system.process_gauls_message(message.text)
            logger.info(f"✅ GaulsMemorySystem processed -> Insight ID: {insight_id}")
            
            # Store raw message in database
            logger.info("💾 Storing raw message in database...")
            self.store_raw_message(message.text, message.date)
            logger.info("✅ Raw message stored successfully")
            
            logger.info("🎉 MESSAGE PROCESSING COMPLETE!")
            
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            logger.error(f"   Message ID: {message.id if message else 'Unknown'}")
            logger.error(f"   Message date: {message.date if message else 'Unknown'}")
    
    def store_raw_message(self, text, date):
        """Store raw message in ALL necessary tables for dashboard and trading"""
        db_path = '/gauls-copy-trading-system/databases/gauls_trading.db'
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Generate a unique message ID based on timestamp
            import hashlib
            message_hash = hashlib.md5(f"{date}{text[:50]}".encode()).hexdigest()[:8]
            message_id = int(message_hash, 16) % 1000000  # Convert to integer ID
            
            # 1. Store in raw_telegram_messages (for archival)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS raw_telegram_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_text TEXT,
                    timestamp DATETIME,
                    processed INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT INTO raw_telegram_messages (message_text, timestamp, processed)
                VALUES (?, ?, 0)
            ''', (text, date.strftime('%Y-%m-%d %H:%M:%S')))
            
            # 2. Let the existing signal parser determine if it's a signal
            # The GaulsMemorySystem already does sophisticated signal detection
            is_signal = self.memory_system.is_trading_signal(text) if hasattr(self.memory_system, 'is_trading_signal') else False
            
            # If no memory system method, use basic detection as fallback
            if not hasattr(self.memory_system, 'is_trading_signal'):
                signal_keywords = ['entry:', 'tp:', 'sl:', 'buying setup', 'selling setup', 
                                 'short setup', 'long setup', 'spot buying']
                is_signal = any(keyword in text.lower() for keyword in signal_keywords)
            
            # 3. Store in gauls_messages (for copy trader)
            cursor.execute('''
                INSERT OR IGNORE INTO gauls_messages (
                    message_id, timestamp, message_text, message_type, views, age_hours
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (message_id, date.strftime('%Y-%m-%d %H:%M:%S'), text, 
                  'signal' if is_signal else 'update', 0, 0))
            
            # 4. Store in all_gauls_messages (for dashboard display)
            unix_timestamp = int(date.timestamp())
            cursor.execute('''
                INSERT OR REPLACE INTO all_gauls_messages (
                    message_id, timestamp, message_text, message_type, is_trade_signal, processed
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (message_id, unix_timestamp, text, 
                  'signal' if is_signal else 'update', 1 if is_signal else 0, 0))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Message stored in all tables (ID: {message_id}, Signal: {is_signal})")
                
        except Exception as e:
            logger.error(f"Error storing message: {e}")
    
    def add_test_message(self):
        """Add a test message to verify system is working"""
        test_message = f"""
🔥 LIVE TEST MESSAGE - {datetime.now().strftime('%H:%M:%S')}

BTC is looking strong at current levels. 
Watching for breakout above $60,000 with volume.

Key levels:
- Support: $58,500
- Resistance: $60,000  
- Target: $62,000

Conviction: HIGH for next move up.
Time: Should happen within 24-48 hours.

This is a test message from the live listener system! ✅
        """.strip()
        
        try:
            self.memory_system.process_gauls_message_sync(test_message)
            self.store_raw_message(test_message, datetime.now())
            logger.info("✅ Test message added successfully")
        except Exception as e:
            logger.error(f"Error adding test message: {e}")
    
    def add_simulated_messages(self):
        """Add simulated recent messages for testing"""
        messages = [
            {
                'text': f"""📊 Market Update - {datetime.now().strftime('%H:%M')}
                
BTC holding strong above $58,000 support.
Looking for volume breakout above $60k.

Alt season incoming if BTC dominance drops below 58%.
My picks: ETH, SOL, ADA all showing strength.

Conviction: HIGH (8/10) for the next 48 hours.""",
                'time': datetime.now()
            },
            {
                'text': f"""🎯 Trade Alert - {datetime.now().strftime('%H:%M')}

ETH/USDT setup looking clean:
- Entry: $2,400-2,420
- Stop: $2,350  
- Target: $2,600

Risk/Reward: 3:1
Confluence: Multiple timeframes aligning

This could be the breakout we've been waiting for!""",
                'time': datetime.now()
            },
            {
                'text': f"""⚡ Quick Update - {datetime.now().strftime('%H:%M')}

Volume is picking up across the board.
Major alts starting to move independently.

Watch for BTC.D breakdown - that's our signal!
When it drops, alt season officially begins.

Stay ready! 🚀""",
                'time': datetime.now()
            }
        ]
        
        for msg_data in messages:
            try:
                self.memory_system.process_gauls_message_sync(msg_data['text'])
                self.store_raw_message(msg_data['text'], msg_data['time'])
                logger.info("✅ Simulated message added")
            except Exception as e:
                logger.error(f"Error adding simulated message: {e}")

async def main():
    listener = LiveTelegramListener()
    await listener.start_listening()

if __name__ == "__main__":
    asyncio.run(main())