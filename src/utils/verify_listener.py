#!/usr/bin/env python3
"""
Verify Telegram Listener is working and catching messages
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import sqlite3
import time
import subprocess
from datetime import datetime, timedelta

def check_latest_message():
    """Check the latest message in database"""
    conn = sqlite3.connect('/gauls-copy-trading-system/databases/gauls_trading.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timestamp, substr(message_text, 1, 50) 
        FROM raw_telegram_messages 
        ORDER BY id DESC LIMIT 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        msg_time = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
        time_diff = datetime.now() - msg_time
        
        print(f"✅ Latest message: {result[0]}")
        print(f"   Content: {result[1]}...")
        print(f"   Age: {time_diff}")
        
        # Alert if no message in last 2 hours
        if time_diff > timedelta(hours=2):
            print(f"⚠️  WARNING: No messages in {time_diff}!")
            return False
    else:
        print("❌ No messages found in database")
        return False
    
    return True

def check_service_status():
    """Check if the listener service is running"""
    result = subprocess.run(['systemctl', 'is-active', 'gauls-telegram-listener'], 
                          capture_output=True, text=True)
    
    if result.stdout.strip() == 'active':
        print("✅ Telegram listener service is active")
        
        # Check CPU and memory usage
        result = subprocess.run(['systemctl', 'status', 'gauls-telegram-listener'], 
                              capture_output=True, text=True)
        
        for line in result.stdout.split('\n'):
            if 'Memory:' in line or 'CPU:' in line:
                print(f"   {line.strip()}")
        
        return True
    else:
        print(f"❌ Telegram listener service is {result.stdout.strip()}")
        return False

def check_connection():
    """Check if actively connected to Telegram"""
    # Check recent logs for connection status
    result = subprocess.run(['tail', '-20', '/gauls-copy-trading-system/logs/telegram_listener.log'], 
                          capture_output=True, text=True)
    
    if 'Connected to Telegram successfully' in result.stdout:
        print("✅ Connected to Telegram")
        return True
    elif 'disconnected' in result.stdout.lower() or 'error' in result.stdout.lower():
        print("❌ Connection issues detected in logs")
        return False
    
    return True

def main():
    print("=" * 60)
    print("🔍 TELEGRAM LISTENER VERIFICATION")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_good = True
    
    # Check service
    if not check_service_status():
        all_good = False
        print("   → Restarting service...")
        subprocess.run(['sudo', 'systemctl', 'restart', 'gauls-telegram-listener'])
    
    print()
    
    # Check messages
    if not check_latest_message():
        all_good = False
    
    print()
    
    # Check connection
    if not check_connection():
        all_good = False
    
    print("=" * 60)
    if all_good:
        print("✅ ALL SYSTEMS OPERATIONAL")
    else:
        print("⚠️  ISSUES DETECTED - Check logs for details")
    print("=" * 60)

if __name__ == "__main__":
    main()