#!/usr/bin/env python3
"""
Ensure database schema consistency across all tables
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_database_consistency():
    """Ensure all tables have proper schema and indexes"""
    
    db_path = '/gauls-copy-trading-system/databases/gauls_trading.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. raw_telegram_messages - Raw message archive
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raw_telegram_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                processed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_raw_timestamp ON raw_telegram_messages(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_raw_processed ON raw_telegram_messages(processed)')
        logger.info("✅ raw_telegram_messages table verified")
        
        # 2. gauls_messages - Messages for copy trader to process
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gauls_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE,
                timestamp TEXT NOT NULL,
                message_text TEXT NOT NULL,
                message_type TEXT DEFAULT 'update',
                views INTEGER DEFAULT 0,
                age_hours REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gauls_timestamp ON gauls_messages(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gauls_type ON gauls_messages(message_type)')
        logger.info("✅ gauls_messages table verified")
        
        # 3. all_gauls_messages - Messages for dashboard display
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS all_gauls_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE,
                timestamp INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                message_type TEXT DEFAULT 'update',
                is_trade_signal BOOLEAN DEFAULT 0,
                processed BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_timestamp ON all_gauls_messages(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_all_signal ON all_gauls_messages(is_trade_signal)')
        logger.info("✅ all_gauls_messages table verified")
        
        # 4. processed_gauls_signals - Track processed signals to avoid duplicates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_gauls_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_hash TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                result TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_hash ON processed_gauls_signals(signal_hash)')
        logger.info("✅ processed_gauls_signals table verified")
        
        # 5. processed_gauls_updates - Track processed trade updates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_gauls_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                update_hash TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                update_type TEXT,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_update_hash ON processed_gauls_updates(update_hash)')
        logger.info("✅ processed_gauls_updates table verified")
        
        # 6. trade_updates - Store trade update details
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT,
                profit_r REAL,
                percentage_gain REAL,
                raw_text TEXT,
                timestamp TEXT,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_symbol ON trade_updates(symbol)')
        logger.info("✅ trade_updates table verified")
        
        # 7. message_processing_queue - Queue for messages to be processed
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_processing_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                processed BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logger.info("✅ message_processing_queue table verified")
        
        conn.commit()
        
        # Verify table counts
        tables = ['raw_telegram_messages', 'gauls_messages', 'all_gauls_messages', 
                  'processed_gauls_signals', 'processed_gauls_updates', 'trade_updates']
        
        print("\n📊 Table Statistics:")
        print("-" * 40)
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table:30} {count:6} rows")
        
        conn.close()
        print("-" * 40)
        print("✅ Database schema verified and consistent")
        
    except Exception as e:
        logger.error(f"Error ensuring database consistency: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    ensure_database_consistency()