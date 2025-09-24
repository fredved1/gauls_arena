#!/usr/bin/env python3
"""
Get Real Gauls Messages - Latest 10
Uses working Telegram client from gauls-bot to get actual messages
"""

import asyncio
import sys
import logging
from datetime import datetime, timedelta
sys.path.append('/gauls-copy-trading-system')

from telethon import TelegramClient
from core.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_real_gauls_messages():
    """Get the latest 10 real Gauls messages from Telegram"""
    
    print("🔍 Connecting to Telegram for real Gauls messages...")
    
    # Load config from gauls-bot
    config = Config.from_env()
    
    # Use existing session from gauls-bot
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
            return []
        
        print("✅ Connected to Telegram successfully")
        
        # Get the Gauls channel using the known ID from config
        channel_id = int(config.telegram.channel_id)  # -1002260702759
        
        try:
            entity = await client.get_entity(channel_id)
            print(f"✅ Channel found: {entity.title}")
            
            # Get latest 10 messages
            print("📡 Fetching latest 10 messages...")
            
            messages = []
            count = 0
            
            async for message in client.iter_messages(entity, limit=20):  # Get 20 to filter for meaningful ones
                if message.text and len(message.text.strip()) > 10:  # Skip very short messages
                    messages.append({
                        'id': message.id,
                        'date': message.date,
                        'text': message.text,
                        'sender': getattr(message.sender, 'username', 'Channel') if message.sender else 'Channel',
                        'views': getattr(message, 'views', 0) or 0
                    })
                    count += 1
                    if count >= 10:  # Stop after 10 meaningful messages
                        break
            
            print(f"📊 Retrieved {len(messages)} real messages")
            
            # Display the messages
            print("\n" + "="*80)
            print("📱 LATEST REAL GAULS MESSAGES")
            print("="*80)
            
            for i, msg in enumerate(messages, 1):
                age = datetime.now(msg['date'].tzinfo) - msg['date']
                age_str = f"{age.days}d {age.seconds//3600}h ago" if age.days > 0 else f"{age.seconds//3600}h {(age.seconds//60)%60}m ago"
                
                print(f"\n[{i}/10] 🕒 {msg['date'].strftime('%m-%d %H:%M')} ({age_str})")
                print(f"👁️ Views: {msg['views']} | ID: {msg['id']}")
                print("-" * 60)
                # Show first 300 characters
                display_text = msg['text'][:300]
                if len(msg['text']) > 300:
                    display_text += "..."
                print(display_text)
                print("-" * 60)
            
            return messages
            
        except Exception as e:
            print(f"❌ Channel access failed: {e}")
            print("💡 Trying to list available channels with 'gauls' in name...")
            
            # List channels that might be Gauls
            async for dialog in client.iter_dialogs():
                if 'gauls' in dialog.name.lower() or 'trader' in dialog.name.lower():
                    print(f"   📺 {dialog.name} (ID: {dialog.id})")
            
            return []
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return []
    finally:
        await client.disconnect()

async def store_real_messages_in_sage(messages):
    """Store real messages in Sage database"""
    if not messages:
        print("❌ No messages to store")
        return
    
    # Import Sage components
    sys.path.append('/opt/sage-trading-system')
    from utils.gauls_memory_system import GaulsMemorySystem
    import sqlite3
    
    memory = GaulsMemorySystem()
    
    print(f"\n🧠 Storing {len(messages)} real messages in Sage database...")
    
    # Clear old messages first
    conn = sqlite3.connect('/opt/sage-trading-system/sage_trading.db')
    cursor = conn.cursor()
    
    # Mark old messages as inactive
    cursor.execute("UPDATE gauls_market_insights SET is_active = 0")
    
    # Store new real messages
    stored_count = 0
    for msg in messages:
        try:
            # Analyze and store each message
            insight = memory.analyze_message(msg['text'])
            if insight:
                insight.timestamp = int(msg['date'].timestamp())
                insight_id = memory.store_insight(insight)
                stored_count += 1
                print(f"✅ Stored message {insight_id}: {insight.message_type.value}")
        except Exception as e:
            print(f"⚠️ Error storing message: {e}")
    
    # Also store raw messages
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS real_telegram_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            message_text TEXT,
            sender TEXT,
            views INTEGER,
            message_date DATETIME,
            retrieved_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Clear old raw messages
    cursor.execute("DELETE FROM real_telegram_messages")
    
    for msg in messages:
        cursor.execute('''
            INSERT INTO real_telegram_messages 
            (telegram_id, message_text, sender, views, message_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (msg['id'], msg['text'], msg['sender'], msg['views'], msg['date']))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Stored {stored_count}/{len(messages)} messages in Sage memory system")
    print("🔄 Dashboard will now show real Gauls messages!")

async def main():
    """Main function"""
    # Get real messages
    messages = await get_real_gauls_messages()
    
    if messages:
        # Store in Sage system
        await store_real_messages_in_sage(messages)
        
        print(f"\n🎉 SUCCESS! Retrieved and stored {len(messages)} real Gauls messages")
        print("🌐 Check dashboard at http://localhost:5000 for updated data")
    else:
        print("❌ No real messages retrieved")

if __name__ == "__main__":
    asyncio.run(main())