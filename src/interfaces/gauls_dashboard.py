#!/usr/bin/env python3
"""
Gauls Copy Trading Dashboard
Real-time monitoring and management interface
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


from flask import Flask, render_template, jsonify
import sqlite3
import json
import os
from datetime import datetime, timedelta
import ccxt
import psutil
import logging

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/gauls-copy-trading-system/logs/dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize WooX exchange for price fetching
from core.unified_exchange import UnifiedExchange

def get_db_connection(db_name='trades'):
    """Get database connection"""
    if db_name == 'trades':
        db_path = '/gauls-copy-trading-system/databases/trades.db'
    else:
        db_path = '/gauls-copy-trading-system/databases/gauls_trading.db'
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def check_process_status(process_name):
    """Check if a process is running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if process_name in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('gauls_dashboard.html')

@app.route('/api/status')
def get_system_status():
    """Get system component status"""
    try:
        status = {
            'gauls_copy_trader': check_process_status('gauls_copy_trader.py'),
            'telegram_listener': check_process_status('live_telegram_listener.py'),
            'exit_monitor': check_process_status('exit_monitor_v2.py'),
            'timestamp': datetime.now().isoformat()
        }
        
        # Get trading mode from environment
        status['trading_mode'] = os.environ.get('TRADING_MODE', 'experimental')
        
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
def get_trades():
    """Get all trades with current prices"""
    try:
        conn = get_db_connection('trades')
        cursor = conn.cursor()
        
        # Get open trades
        cursor.execute("""
            SELECT id, symbol, side, entry_price, stop_loss, take_profit_1, take_profit_2,
                   quantity, original_quantity, remaining_quantity, partial_exits_done, partial_pnl,
                   entry_time, notes, leverage, status
            FROM trades
            WHERE status = 'open'
            ORDER BY entry_time DESC
        """)
        
        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            
            # Get current price
            try:
                unified_exchange = UnifiedExchange()
                ticker = unified_exchange.fetch_ticker(trade['symbol'])
                current_price = ticker['last']
                trade['current_price'] = current_price
                
                # Calculate P&L
                remaining_qty = trade['remaining_quantity'] or trade['quantity']
                leverage = trade['leverage'] or 1.0
                
                if trade['side'] == 'buy':
                    unrealized_pnl = (current_price - trade['entry_price']) * remaining_qty * leverage
                    pnl_pct = ((current_price - trade['entry_price']) / trade['entry_price']) * 100 * leverage
                else:
                    unrealized_pnl = (trade['entry_price'] - current_price) * remaining_qty * leverage
                    pnl_pct = ((trade['entry_price'] - current_price) / trade['entry_price']) * 100 * leverage
                
                trade['unrealized_pnl'] = round(unrealized_pnl, 2)
                trade['total_pnl'] = round((trade['partial_pnl'] or 0) + unrealized_pnl, 2)
                trade['pnl_pct'] = round(pnl_pct, 2)
                
                # Check if trade is risk-free
                if trade['stop_loss']:
                    if trade['side'] == 'buy' and trade['stop_loss'] >= trade['entry_price']:
                        trade['risk_free'] = True
                    elif trade['side'] == 'sell' and trade['stop_loss'] <= trade['entry_price']:
                        trade['risk_free'] = True
                    else:
                        trade['risk_free'] = False
                
                # Calculate distances to TP levels
                if trade['take_profit_1']:
                    trade['tp1_distance'] = round(abs(current_price - trade['take_profit_1']), 4)
                    trade['tp1_pct'] = round(abs((current_price - trade['take_profit_1']) / current_price * 100), 2)
                
                if trade['take_profit_2']:
                    trade['tp2_distance'] = round(abs(current_price - trade['take_profit_2']), 4)
                    trade['tp2_pct'] = round(abs((current_price - trade['take_profit_2']) / current_price * 100), 2)
                
            except Exception as e:
                logger.error(f"Error fetching price for {trade['symbol']}: {e}")
                trade['current_price'] = None
            
            trades.append(trade)
        
        # Get closed trades from last 24 hours
        cursor.execute("""
            SELECT id, symbol, side, entry_price, exit_price, pnl, 
                   entry_time, exit_time, notes, status
            FROM trades
            WHERE status = 'closed' 
            AND exit_time > datetime('now', '-1 day')
            ORDER BY exit_time DESC
            LIMIT 10
        """)
        
        closed_trades = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'open': trades,
            'closed': closed_trades,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/messages')
def get_gauls_messages():
    """Get recent Gauls messages"""
    try:
        conn = get_db_connection('gauls')
        cursor = conn.cursor()
        
        # Get recent messages
        cursor.execute("""
            SELECT message_id, timestamp, message_text, message_type
            FROM gauls_messages
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        messages = []
        for row in cursor.fetchall():
            msg = dict(row)
            # Check if it's a signal or update
            text = msg['message_text'].lower()
            if 'setup' in text or 'entry' in text:
                msg['msg_type'] = 'signal'
            elif 'update' in text or 'achieved' in text or 'risk free' in text:
                msg['msg_type'] = 'update'
            else:
                msg['msg_type'] = 'info'
            
            messages.append(msg)
        
        conn.close()
        return jsonify(messages)
        
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/updates')
def get_trade_updates():
    """Get recent trade updates"""
    try:
        conn = get_db_connection('gauls')
        cursor = conn.cursor()
        
        # Get trade updates
        cursor.execute("""
            SELECT symbol, action, profit_r, percentage_gain, 
                   timestamp, processed_at
            FROM trade_updates
            ORDER BY processed_at DESC
            LIMIT 20
        """)
        
        updates = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify(updates)
        
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_statistics():
    """Get trading statistics"""
    try:
        conn = get_db_connection('trades')
        cursor = conn.cursor()
        
        # Get overall stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_trades,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_trades,
                SUM(CASE WHEN status = 'closed' AND pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN status = 'closed' AND pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(CASE WHEN status = 'closed' THEN pnl ELSE 0 END) as total_pnl,
                AVG(CASE WHEN status = 'closed' THEN pnl ELSE NULL END) as avg_pnl
            FROM trades
        """)
        
        stats = dict(cursor.fetchone())
        
        # Handle None values
        for key in stats:
            if stats[key] is None:
                stats[key] = 0
        
        # Calculate win rate
        if stats['closed_trades'] and stats['closed_trades'] > 0:
            stats['win_rate'] = round((stats['winning_trades'] / stats['closed_trades']) * 100, 2)
        else:
            stats['win_rate'] = 0
        
        # Get today's stats
        cursor.execute("""
            SELECT 
                COUNT(*) as today_trades,
                SUM(CASE WHEN status = 'closed' THEN pnl ELSE 0 END) as today_pnl
            FROM trades
            WHERE date(entry_time) = date('now')
        """)
        
        today_stats = dict(cursor.fetchone())
        stats.update(today_stats)
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/partial_exits')
def get_partial_exits():
    """Get recent partial exits"""
    try:
        conn = get_db_connection('trades')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pe.*, t.symbol
            FROM partial_exits pe
            JOIN trades t ON pe.trade_id = t.id
            ORDER BY pe.exit_time DESC
            LIMIT 10
        """)
        
        partial_exits = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return jsonify(partial_exits)
        
    except Exception as e:
        logger.error(f"Error getting partial exits: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Gauls Trading Dashboard on port 7777")
    app.run(host='0.0.0.0', port=7777, debug=False)