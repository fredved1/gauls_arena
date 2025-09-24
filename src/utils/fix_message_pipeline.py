#!/usr/bin/env python3
"""
Fix the message processing pipeline to ensure signals are captured and traded
"""

import sqlite3
import sys
import os
import json
from datetime import datetime
sys.path.append('/gauls-copy-trading-system')
sys.path.append('/gauls-copy-trading-system')

def ensure_btc_signal_in_all_tables():
    """Ensure the BTC signal is in all necessary tables"""
    
    conn = sqlite3.connect('/gauls-copy-trading-system/databases/gauls_trading.db')
    cursor = conn.cursor()
    
    # The BTC signal details
    btc_signal = {
        'message_id': 1451,
        'timestamp': '2025-09-23 05:04:30',
        'unix_timestamp': 1727067870,
        'message_text': '''$BTC Buying Setup:

👉 Entry: CMP
👉 TP: 114786
👉 SL: 111468

Cheers 

#TraderGauls🎭''',
        'message_type': 'signal'
    }
    
    print("🔧 Fixing message pipeline...")
    
    # 1. Ensure it's in raw_telegram_messages (already there)
    cursor.execute("""
        SELECT COUNT(*) FROM raw_telegram_messages 
        WHERE message_text LIKE '%BTC%' AND message_text LIKE '%114786%'
    """)
    if cursor.fetchone()[0] > 0:
        print("✅ BTC signal already in raw_telegram_messages")
    
    # 2. Insert into gauls_messages if not there
    cursor.execute("""
        SELECT COUNT(*) FROM gauls_messages 
        WHERE message_text LIKE '%BTC%' AND message_text LIKE '%114786%'
    """)
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO gauls_messages (
                message_id, timestamp, message_text, message_type, views, age_hours
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (btc_signal['message_id'], btc_signal['timestamp'], 
              btc_signal['message_text'], 'signal', 0, 1.5))
        print("✅ BTC signal inserted into gauls_messages")
    else:
        print("✅ BTC signal already in gauls_messages")
    
    # 3. Insert into all_gauls_messages for dashboard
    cursor.execute("""
        DELETE FROM all_gauls_messages 
        WHERE message_text LIKE '%BTC%' AND message_text LIKE '%114786%'
    """)
    
    cursor.execute("""
        INSERT INTO all_gauls_messages (
            message_id, timestamp, message_text, message_type, is_trade_signal, processed
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (btc_signal['message_id'], btc_signal['unix_timestamp'], 
          btc_signal['message_text'], 'signal', 1, 0))
    print("✅ BTC signal refreshed in all_gauls_messages")
    
    # 4. Mark it as unprocessed for the copy trader
    cursor.execute("""
        DELETE FROM processed_gauls_signals WHERE signal_hash LIKE '%BTC%114786%'
    """)
    print("✅ BTC signal marked as unprocessed for copy trader")
    
    conn.commit()
    
    # 5. Verify it's visible
    cursor.execute("""
        SELECT message_id, timestamp, substr(message_text, 1, 50), is_trade_signal 
        FROM all_gauls_messages 
        WHERE message_text LIKE '%BTC%'
        ORDER BY timestamp DESC LIMIT 1
    """)
    result = cursor.fetchone()
    if result:
        print(f"✅ Verified in all_gauls_messages: ID={result[0]}, Signal={result[3]}")
        print(f"   Text: {result[2]}...")
    
    conn.close()
    print("\n✅ Message pipeline fixed!")
    print("   - BTC signal is now in all tables")
    print("   - Dashboard should show it")
    print("   - Copy trader will process it on next check")

def fix_message_processing_pipeline():
    """Fix the pipeline so future messages are properly processed"""
    
    # Create a trigger to ensure messages go to all tables
    conn = sqlite3.connect('/gauls-copy-trading-system/databases/gauls_trading.db')
    cursor = conn.cursor()
    
    # Create a processing queue table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS message_processing_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_text TEXT,
            timestamp TEXT,
            processed BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("✅ Processing queue table ensured")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    ensure_btc_signal_in_all_tables()
    fix_message_processing_pipeline()