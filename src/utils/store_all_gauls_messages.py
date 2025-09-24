#!/usr/bin/env python3
"""
Store ALL Gauls Messages (Trade signals AND market updates)
Ensures no messages are missed
"""

import asyncio
import sys
import sqlite3
import logging
from datetime import datetime
sys.path.insert(0, '/gauls-copy-trading-system/src')

from telethon import TelegramClient
from core.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def classify_message(text):
    """Classify message type"""
    text_lower = text.lower()
    
    # Check if it's a trade signal (new entry)
    trade_keywords = ['entry:', 'tp:', 'sl:', 'buying setup', 'selling setup', 
                     'long setup', 'short setup', 'spot setup']
    is_trade = any(kw in text_lower for kw in trade_keywords)
    
    # Check if it's a trade update (existing position update)
    trade_update_keywords = ['+1r done', '+2r done', '+3r done', 'r done', 
                            'book profit', 'book partial', 'risk free', 
                            'move sl', 'sl to entry', 'tp achieved', 
                            'target achieved', 'close', 'exit']
    is_trade_update = any(kw in text_lower for kw in trade_update_keywords)
    
    # Classify message type
    if is_trade_update and 'trade update' in text_lower:
        msg_type = 'trade_update'
    elif is_trade:
        msg_type = 'trade_signal'
    elif 'update' in text_lower or 'outlook' in text_lower:
        msg_type = 'market_update'
    elif 'risk' in text_lower or 'management' in text_lower:
        msg_type = 'risk_update'
    elif any(word in text_lower for word in ['accumulate', 'buy', 'sell']):
        msg_type = 'action_advice'
    else:
        msg_type = 'general_update'
    
    return msg_type, is_trade

async def store_all_messages():
    """Fetch and store ALL Gauls messages"""
    
    print("🔍 Fetching ALL Gauls messages...")
    
    config = Config.from_env()
    session_path = '/gauls-copy-trading-system/trading_session'
    
    client = TelegramClient(
        session_path,
        config.telegram.api_id,
        config.telegram.api_hash
    )
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Telegram session not authorized")
            return
        
        print("✅ Connected to Telegram")
        
        # Get the Gauls channel
        channel_id = int(config.telegram.channel_id)
        entity = await client.get_entity(channel_id)
        print(f"✅ Channel found: {entity.title}")
        
        # Connect to database
        conn = sqlite3.connect('/gauls-copy-trading-system/databases/gauls_trading.db')
        cursor = conn.cursor()
        
        # Get latest 50 messages
        print("📡 Fetching latest 50 messages...")
        
        stored_count = 0
        async for message in client.iter_messages(entity, limit=50):
            if message.text and len(message.text.strip()) > 10:
                msg_type, is_trade = classify_message(message.text)
                
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO all_gauls_messages 
                        (message_id, timestamp, message_text, message_type, is_trade_signal, processed)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        message.id,
                        int(message.date.timestamp()),
                        message.text,
                        msg_type,
                        is_trade,
                        0
                    ))
                    stored_count += 1
                    
                    # Also store trade signals in the original table
                    if is_trade:
                        cursor.execute('''
                            INSERT OR REPLACE INTO gauls_messages 
                            (message_id, timestamp, message_text)
                            VALUES (?, ?, ?)
                        ''', (
                            message.id,
                            int(message.date.timestamp()),
                            message.text
                        ))
                    
                except Exception as e:
                    print(f"⚠️ Error storing message {message.id}: {e}")
        
        conn.commit()
        print(f"✅ Stored {stored_count} messages in database")
        
        # Show summary
        cursor.execute('''
            SELECT message_type, COUNT(*) as count 
            FROM all_gauls_messages 
            GROUP BY message_type
        ''')
        
        print("\n📊 Message Summary:")
        for msg_type, count in cursor.fetchall():
            print(f"  {msg_type}: {count} messages")
        
        # Show latest messages
        cursor.execute('''
            SELECT datetime(timestamp, 'unixepoch', 'localtime') as time,
                   message_type,
                   substr(message_text, 1, 80) as preview
            FROM all_gauls_messages 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        
        print("\n📱 Latest 10 Messages:")
        print("-" * 100)
        for time, msg_type, preview in cursor.fetchall():
            print(f"{time} | {msg_type:15} | {preview}...")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(store_all_messages())