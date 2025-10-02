#!/usr/bin/env python3
"""
Gauls Copy Trading Dashboard - Enhanced with Exchange Integration
Real P&L data directly from WooX Exchange
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
import hashlib
import hmac
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/gauls-copy-trading-system/.env')

import os
# Set template folder path
template_dir = os.path.abspath('/gauls-copy-trading-system/templates')
app = Flask(__name__, template_folder=template_dir)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/gauls-copy-trading-system/logs/dashboard_enhanced.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize WooX exchange for all data (positions and prices)
from core.unified_exchange import UnifiedExchange

# Initialize WooX for position data
try:
    woox = ccxt.woo({
        'apiKey': os.getenv('WOOX_API_KEY'),
        'secret': os.getenv('WOOX_API_SECRET'),
        'options': {
            'defaultType': 'swap',  # Use perpetuals
            'adjustForTimeDifference': True
        },
        'enableRateLimit': True
    })
    woox.load_markets()
    logger.info("✅ WooX exchange initialized")
except Exception as e:
    logger.error(f"Failed to initialize WooX: {e}")
    woox = None

def get_woox_positions():
    """Get actual positions from WooX exchange"""
    try:
        if not woox:
            return {}
        
        # Fetch all open positions from WooX
        positions = woox.fetch_positions()
        
        position_data = {}
        for pos in positions:
            if pos['contracts'] > 0:  # Only include open positions
                symbol = pos['symbol']
                position_data[symbol] = {
                    'symbol': symbol,
                    'side': pos['side'],
                    'contracts': pos['contracts'],
                    'entry_price': pos.get('entryPrice') or pos.get('markPrice', 0),
                    'current_price': pos.get('markPrice', 0),
                    'unrealized_pnl': pos.get('unrealizedPnl', 0) or 0,
                    'realized_pnl': pos.get('realizedPnl', 0) or 0,
                    'percentage': pos.get('percentage', 0) or 0,
                    'margin': pos.get('initialMargin', 0) or 0,
                    'leverage': pos.get('leverage', 1) or 1
                }
                logger.info(f"WooX Position: {symbol} - Unrealized P&L: ${position_data[symbol]['unrealized_pnl']:.2f}")
        
        return position_data
    except Exception as e:
        logger.error(f"Error fetching WooX positions: {e}")
        return {}

def get_time_ago(timestamp):
    """Convert timestamp to human-readable time ago"""
    try:
        now = datetime.now()
        msg_time = datetime.fromtimestamp(timestamp)
        diff = now - msg_time
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"
    except:
        return ""

def get_woox_balance():
    """Get account balance from WooX"""
    try:
        if not woox:
            return None
        
        balance = woox.fetch_balance()
        
        # Get USDT balance
        usdt_balance = {
            'free': balance.get('USDT', {}).get('free', 0),
            'used': balance.get('USDT', {}).get('used', 0),
            'total': balance.get('USDT', {}).get('total', 0)
        }
        
        # Calculate account metrics
        account_info = {
            'balance': usdt_balance,
            'total_equity': usdt_balance['total'],
            'free_balance': usdt_balance['free'],
            'margin_used': usdt_balance['used']
        }
        
        return account_info
    except Exception as e:
        logger.error(f"Error fetching WooX balance: {e}")
        return None

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
    return render_template('gauls_dashboard_enhanced.html')

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
        status['trading_mode'] = os.environ.get('TRADING_MODE', 'production')
        
        # Get WooX connection status
        try:
            balance = get_woox_balance()
            status['woox_connected'] = balance is not None
            if balance:
                status['account_balance'] = balance['total_equity']
        except:
            status['woox_connected'] = False
        
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
def get_trades():
    """Get all trades with real P&L from exchange"""
    try:
        # Get exchange positions for real P&L
        woox_positions = get_woox_positions()
        
        conn = get_db_connection('trades')
        cursor = conn.cursor()
        
        # Get open trades from database with partial exit totals
        cursor.execute("""
            SELECT t.id, t.symbol, t.side, t.entry_price, t.stop_loss, t.take_profit_1, t.take_profit_2,
                   t.quantity, t.original_quantity, t.remaining_quantity, t.partial_exits_done, t.partial_pnl,
                   t.entry_time, t.notes, t.leverage, t.status,
                   COALESCE(pe.total_exited_quantity, 0) as total_exited_quantity
            FROM trades t
            LEFT JOIN (
                SELECT trade_id, SUM(quantity_exited) as total_exited_quantity
                FROM partial_exits
                GROUP BY trade_id
            ) pe ON t.id = pe.trade_id
            WHERE t.status = 'open'
            ORDER BY t.entry_time DESC
        """)
        
        trades = []
        for row in cursor.fetchall():
            trade = dict(row)
            
            # Match symbol format (database has SEI/USDT, exchange has SEI/USDT:USDT)
            symbol = trade['symbol']
            exchange_symbol = f"{symbol}:USDT" if ':' not in symbol else symbol
            
            # Check both formats
            exchange_pos = woox_positions.get(exchange_symbol) or woox_positions.get(symbol)
            
            if exchange_pos:
                # Use exchange data for accurate P&L and position size
                trade['current_price'] = exchange_pos['current_price']
                trade['unrealized_pnl'] = exchange_pos['unrealized_pnl']
                trade['total_pnl'] = exchange_pos['unrealized_pnl'] + (trade['partial_pnl'] or 0)
                
                # Use live exchange position size instead of database remaining_quantity
                trade['remaining_quantity'] = exchange_pos['contracts']
                trade['live_position_size'] = exchange_pos['contracts']  # Add explicit field
                
                # Calculate percentage P&L based on entry price and current price
                leverage = trade['leverage'] or 1.0
                if trade['entry_price'] and trade['entry_price'] > 0:
                    if trade['side'] == 'buy':
                        pnl_pct = ((exchange_pos['current_price'] - trade['entry_price']) / trade['entry_price']) * 100 * leverage
                    else:
                        pnl_pct = ((trade['entry_price'] - exchange_pos['current_price']) / trade['entry_price']) * 100 * leverage
                    trade['pnl_pct'] = round(pnl_pct, 2)
                else:
                    # Fallback to exchange percentage if available
                    trade['pnl_pct'] = exchange_pos['percentage'] * 100 if exchange_pos['percentage'] else 0
                
                logger.info(f"Trade {symbol}: Using Exchange P&L = ${trade['unrealized_pnl']:.2f} ({trade['pnl_pct']:.2f}%)")
            else:
                # Fallback to price-based calculation if not on exchange
                try:
                    unified_exchange = UnifiedExchange()
                    ticker = unified_exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    trade['current_price'] = current_price
                    
                    # Calculate P&L locally
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
                    
                except Exception as e:
                    logger.error(f"Error calculating P&L for {trade['symbol']}: {e}")
                    trade['current_price'] = None
            
            # Check if trade is risk-free
            if trade['stop_loss']:
                if trade['side'] == 'buy' and trade['stop_loss'] >= trade['entry_price']:
                    trade['risk_free'] = True
                elif trade['side'] == 'sell' and trade['stop_loss'] <= trade['entry_price']:
                    trade['risk_free'] = True
                else:
                    trade['risk_free'] = False
            
            # Calculate distances and potential profits for TP levels
            if trade.get('current_price'):
                remaining_qty = trade['remaining_quantity'] or trade['quantity'] or 0
                
                if trade['take_profit_1']:
                    trade['tp1_distance'] = round(abs(trade['current_price'] - trade['take_profit_1']), 4)
                    trade['tp1_pct'] = round(abs((trade['current_price'] - trade['take_profit_1']) / trade['current_price'] * 100), 2)
                    
                    # Calculate potential profit at TP1 (leverage already included in position size)
                    if trade['side'] == 'buy':
                        tp1_profit = (trade['take_profit_1'] - trade['entry_price']) * remaining_qty
                    else:
                        tp1_profit = (trade['entry_price'] - trade['take_profit_1']) * remaining_qty
                    trade['tp1_profit'] = round(tp1_profit, 2)
                
                if trade['take_profit_2']:
                    trade['tp2_distance'] = round(abs(trade['current_price'] - trade['take_profit_2']), 4)
                    trade['tp2_pct'] = round(abs((trade['current_price'] - trade['take_profit_2']) / trade['current_price'] * 100), 2)
                    
                    # Calculate potential profit at TP2 (leverage already included in position size)
                    if trade['side'] == 'buy':
                        tp2_profit = (trade['take_profit_2'] - trade['entry_price']) * remaining_qty
                    else:
                        tp2_profit = (trade['entry_price'] - trade['take_profit_2']) * remaining_qty
                    trade['tp2_profit'] = round(tp2_profit, 2)
            
            trades.append(trade)
        
        # Get closed trades from last 7 days
        cursor.execute("""
            SELECT id, symbol, side, entry_price, exit_price, pnl, 
                   entry_time, exit_time, notes, status
            FROM trades
            WHERE status = 'closed' 
            AND exit_time > datetime('now', '-7 days')
            ORDER BY exit_time DESC
            LIMIT 20
        """)
        
        closed_trades = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        # Add account balance info
        account_info = get_woox_balance()
        
        return jsonify({
            'open': trades,
            'closed': closed_trades,
            'account': account_info,
            'exchange_positions': list(woox_positions.values()),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exchange/positions')
def get_exchange_positions():
    """Get raw position data from exchange"""
    try:
        positions = get_woox_positions()
        return jsonify({
            'positions': list(positions.values()),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting exchange positions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exchange/balance')
def get_exchange_balance():
    """Get account balance from exchange"""
    try:
        balance = get_woox_balance()
        return jsonify({
            'balance': balance,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting exchange balance: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders')
def get_open_orders():
    """Get open orders from exchange"""
    try:
        if woox:
            orders = woox.fetch_open_orders()
            formatted_orders = []
            for order in orders:
                formatted_orders.append({
                    'id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'amount': order['amount'],
                    'price': order['price'],
                    'status': order['status'],
                    'timestamp': order['datetime'] if order.get('datetime') else None
                })
            return jsonify({
                'orders': formatted_orders,
                'count': len(formatted_orders),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'orders': [], 'count': 0})
    except Exception as e:
        logger.error(f"Error getting open orders: {e}")
        return jsonify({'error': str(e), 'orders': []}), 500

@app.route('/api/messages')
def get_gauls_messages():
    """Get recent Gauls messages"""
    try:
        conn = get_db_connection('gauls')
        cursor = conn.cursor()
        
        # Get ALL recent messages from the comprehensive table
        cursor.execute("""
            SELECT message_id, timestamp, message_text, message_type, is_trade_signal, processed
            FROM all_gauls_messages
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        
        all_messages = []
        for row in cursor.fetchall():
            msg = {
                'message_id': row[0],
                'timestamp': row[1],
                'message_text': row[2][:200] + '...' if len(row[2]) > 200 else row[2],
                'message_type': row[3],
                'is_trade_signal': row[4],
                'processed': row[5],
                'time_ago': get_time_ago(row[1])
            }
            all_messages.append(msg)
        
        # Also get trade signals separately
        cursor.execute("""
            SELECT message_id, timestamp, message_text
            FROM gauls_messages
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        
        trade_signals = []
        for row in cursor.fetchall():
            trade_signals.append({
                'message_id': row[0],
                'timestamp': row[1],
                'message_text': row[2],
                'time_ago': get_time_ago(row[1])
            })
        
        conn.close()
        return jsonify({
            'all_messages': all_messages,
            'trade_signals': trade_signals
        })
        
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
    """Get trading statistics with exchange verification"""
    try:
        # Get exchange data
        woox_positions = get_woox_positions()
        account_info = get_woox_balance()
        
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
        
        # Calculate proper realized P&L: closed trades + partial exits  
        cursor.execute("""
            SELECT 
                (SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE status = 'closed') as closed_pnl,
                (SELECT COALESCE(SUM(partial_pnl), 0) FROM trades WHERE status = 'open' AND partial_pnl > 0) as partial_pnl
        """)
        
        pnl_data = dict(cursor.fetchone())
        total_realized_pnl = (pnl_data['closed_pnl'] or 0) + (pnl_data['partial_pnl'] or 0)
        
        # Get exchange-verified unrealized P&L (current positions only)
        exchange_unrealized_pnl = sum(pos['unrealized_pnl'] for pos in woox_positions.values())
        exchange_realized_pnl = sum(pos['realized_pnl'] for pos in woox_positions.values())
        
        stats['realized_pnl'] = round(total_realized_pnl, 2)
        stats['unrealized_pnl'] = round(exchange_unrealized_pnl, 2) 
        stats['total_pnl'] = round(total_realized_pnl + exchange_unrealized_pnl, 2)
        
        # Keep exchange data for reference
        stats['exchange_unrealized_pnl'] = round(exchange_unrealized_pnl, 2)
        stats['exchange_realized_pnl'] = round(exchange_realized_pnl, 2)
        
        # Add account balance
        if account_info:
            stats['account_balance'] = account_info['total_equity']
            stats['free_balance'] = account_info['free_balance']
            stats['margin_used'] = account_info['margin_used']
        
        # Get today's stats - use local date
        from datetime import datetime
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # Calculate today's P&L: closed trades + partial exits done today
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM trades WHERE date(entry_time) = ?) as today_trades,
                (SELECT COALESCE(SUM(pnl), 0) FROM trades 
                 WHERE status = 'closed' AND date(exit_time) = ?) as closed_today_pnl,
                (SELECT COALESCE(SUM(pnl), 0) FROM partial_exits 
                 WHERE date(exit_time) = ?) as partial_today_pnl
        """, (today_date, today_date, today_date))
        
        today_stats = dict(cursor.fetchone())
        today_total_pnl = (today_stats.get('closed_today_pnl', 0) or 0) + (today_stats.get('partial_today_pnl', 0) or 0)
        
        # Update today's stats
        stats['today_pnl'] = round(today_total_pnl, 2)
        stats['today_realized_pnl'] = round(today_total_pnl, 2)
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
    logger.info("🚀 Starting Enhanced Gauls Trading Dashboard with Exchange Integration on port 7777")
    logger.info("📊 Fetching real P&L data from WooX Exchange")
    
    # Test exchange connection
    balance = get_woox_balance()
    if balance:
        logger.info(f"✅ WooX Connected - Balance: ${balance['total_equity']:.2f}")
    else:
        logger.warning("⚠️ Could not connect to WooX - will use calculated P&L")
    
    app.run(host='0.0.0.0', port=7777, debug=False)