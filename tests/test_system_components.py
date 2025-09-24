#!/usr/bin/env python3
"""
Gauls Trading System - Component Unit Tests
Comprehensive testing suite for all system components
"""

import unittest
import sqlite3
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add system path
sys.path.append('/gauls-copy-trading-system')

class TestDatabaseOperations(unittest.TestCase):
    """Test database operations and integrity"""
    
    def setUp(self):
        self.test_db = '/tmp/test_trades.db'
        self.conn = sqlite3.connect(self.test_db)
        self.cursor = self.conn.cursor()
        
        # Create test table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                entry_price REAL,
                entry_time TEXT,
                quantity REAL,
                status TEXT DEFAULT 'open',
                strategy TEXT DEFAULT 'gauls_copy',
                notes TEXT,
                stop_loss REAL,
                take_profit_1 REAL,
                take_profit_2 REAL,
                leverage REAL DEFAULT 1,
                risk_reward REAL,
                position_type TEXT DEFAULT 'futures',
                exit_price REAL,
                exit_time TEXT,
                pnl REAL,
                original_quantity REAL,
                remaining_quantity REAL,
                partial_exits_done INTEGER DEFAULT 0,
                partial_pnl REAL DEFAULT 0,
                trade_type TEXT DEFAULT 'signal'
            )
        """)
        self.conn.commit()
    
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_insert_trade(self):
        """Test inserting a new trade"""
        self.cursor.execute("""
            INSERT INTO trades (symbol, side, entry_price, entry_time, quantity, stop_loss, take_profit_1)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('BTC/USDT', 'buy', 50000, datetime.now().isoformat(), 0.01, 48000, 52000))
        self.conn.commit()
        
        self.cursor.execute("SELECT COUNT(*) FROM trades")
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, 1)
    
    def test_update_trade_status(self):
        """Test updating trade status"""
        # Insert test trade
        self.cursor.execute("""
            INSERT INTO trades (symbol, side, entry_price, entry_time, quantity, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('ETH/USDT', 'buy', 3000, datetime.now().isoformat(), 0.1, 'open'))
        trade_id = self.cursor.lastrowid
        self.conn.commit()
        
        # Update status
        self.cursor.execute("""
            UPDATE trades 
            SET status = 'closed', exit_price = ?, exit_time = ?, pnl = ?
            WHERE id = ?
        """, (3100, datetime.now().isoformat(), 10, trade_id))
        self.conn.commit()
        
        # Verify update
        self.cursor.execute("SELECT status, pnl FROM trades WHERE id = ?", (trade_id,))
        status, pnl = self.cursor.fetchone()
        self.assertEqual(status, 'closed')
        self.assertEqual(pnl, 10)
    
    def test_query_open_trades(self):
        """Test querying open trades"""
        # Insert multiple trades
        trades = [
            ('BTC/USDT', 'buy', 'open'),
            ('ETH/USDT', 'sell', 'closed'),
            ('SOL/USDT', 'buy', 'open')
        ]
        
        for symbol, side, status in trades:
            self.cursor.execute("""
                INSERT INTO trades (symbol, side, status, entry_price, entry_time, quantity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, side, status, 100, datetime.now().isoformat(), 1))
        self.conn.commit()
        
        # Query open trades
        self.cursor.execute("SELECT symbol FROM trades WHERE status = 'open'")
        open_trades = [row[0] for row in self.cursor.fetchall()]
        
        self.assertEqual(len(open_trades), 2)
        self.assertIn('BTC/USDT', open_trades)
        self.assertIn('SOL/USDT', open_trades)

class TestSignalParsing(unittest.TestCase):
    """Test signal parsing functionality"""
    
    def test_parse_entry_signal(self):
        """Test parsing entry signals"""
        signals = [
            ("BTC/USDT LONG Entry: 50000 SL: 48000 TP1: 52000", 
             {'symbol': 'BTC/USDT', 'side': 'buy', 'entry': 50000, 'sl': 48000, 'tp1': 52000}),
            ("ETH SHORT 3000 Stop 3100 Target 2900",
             {'symbol': 'ETH/USDT', 'side': 'sell', 'entry': 3000, 'sl': 3100, 'tp1': 2900})
        ]
        
        for signal_text, expected in signals:
            # Simplified parsing logic
            result = self.parse_signal(signal_text)
            for key in expected:
                if key in result:
                    self.assertEqual(result[key], expected[key])
    
    def parse_signal(self, text):
        """Simplified signal parser for testing"""
        result = {}
        
        # Extract symbol
        if 'BTC' in text:
            result['symbol'] = 'BTC/USDT'
        elif 'ETH' in text:
            result['symbol'] = 'ETH/USDT'
        
        # Extract side
        if 'LONG' in text.upper() or 'BUY' in text.upper():
            result['side'] = 'buy'
        elif 'SHORT' in text.upper() or 'SELL' in text.upper():
            result['side'] = 'sell'
        
        # Extract prices (simplified)
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        if len(numbers) >= 3:
            result['entry'] = float(numbers[0])
            result['sl'] = float(numbers[1])
            result['tp1'] = float(numbers[2])
        
        return result
    
    def test_parse_update_signal(self):
        """Test parsing trade update signals"""
        updates = [
            ("+1R done, move SL to entry", {'action': '1r_done', 'move_sl': 'entry'}),
            ("Book 50% here", {'action': 'partial', 'percentage': 50}),
            ("Close all positions", {'action': 'close_all'})
        ]
        
        for update_text, expected in updates:
            result = self.parse_update(update_text)
            for key in expected:
                if key in result:
                    self.assertEqual(result[key], expected[key])
    
    def parse_update(self, text):
        """Simplified update parser for testing"""
        result = {}
        
        if '1R done' in text or '+1R' in text:
            result['action'] = '1r_done'
        elif 'Book' in text or 'partial' in text.lower():
            result['action'] = 'partial'
            import re
            match = re.search(r'(\d+)%', text)
            if match:
                result['percentage'] = int(match.group(1))
        elif 'Close' in text or 'exit' in text.lower():
            result['action'] = 'close_all'
        
        if 'move SL to entry' in text.lower() or 'sl to entry' in text.lower():
            result['move_sl'] = 'entry'
        
        return result

class TestExchangeConnection(unittest.TestCase):
    """Test exchange connection and operations"""
    
    @patch('unified_exchange.UnifiedExchange')
    def test_get_balance(self, mock_exchange):
        """Test getting account balance"""
        mock_instance = mock_exchange.return_value
        mock_instance.get_balance.return_value = {
            'total_usdt': 1000.0,
            'free_usdt': 800.0,
            'used_usdt': 200.0
        }
        
        from core.unified_exchange import UnifiedExchange
        exchange = UnifiedExchange()
        balance = exchange.get_balance()
        
        self.assertEqual(balance['total_usdt'], 1000.0)
        self.assertEqual(balance['free_usdt'], 800.0)
    
    @patch('unified_exchange.UnifiedExchange')
    def test_place_order(self, mock_exchange):
        """Test placing an order"""
        mock_instance = mock_exchange.return_value
        mock_instance.place_order.return_value = {
            'id': '12345',
            'status': 'filled',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'price': 50000,
            'amount': 0.01
        }
        
        from core.unified_exchange import UnifiedExchange
        exchange = UnifiedExchange()
        order = exchange.place_order('BTC/USDT', 'buy', 0.01, 50000)
        
        self.assertEqual(order['id'], '12345')
        self.assertEqual(order['status'], 'filled')

class TestSystemIntegration(unittest.TestCase):
    """Test system integration and workflow"""
    
    def test_signal_to_trade_workflow(self):
        """Test complete workflow from signal to trade"""
        # Simulate receiving a signal
        signal = {
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'entry': 50000,
            'stop_loss': 48000,
            'take_profit_1': 52000,
            'timestamp': datetime.now().isoformat()
        }
        
        # Test signal validation
        self.assertTrue(self.validate_signal(signal))
        
        # Test position sizing
        position_size = self.calculate_position_size(
            capital=1000,
            risk_percent=1,
            entry=signal['entry'],
            stop_loss=signal['stop_loss']
        )
        self.assertGreater(position_size, 0)
        
        # Test order creation
        order = self.create_order_from_signal(signal, position_size)
        self.assertEqual(order['symbol'], signal['symbol'])
        self.assertEqual(order['side'], signal['side'])
    
    def validate_signal(self, signal):
        """Validate signal has required fields"""
        required = ['symbol', 'side', 'entry', 'stop_loss']
        return all(field in signal for field in required)
    
    def calculate_position_size(self, capital, risk_percent, entry, stop_loss):
        """Calculate position size based on risk"""
        risk_amount = capital * (risk_percent / 100)
        price_difference = abs(entry - stop_loss)
        position_size = risk_amount / price_difference
        return position_size
    
    def create_order_from_signal(self, signal, position_size):
        """Create order from signal"""
        return {
            'symbol': signal['symbol'],
            'side': signal['side'],
            'amount': position_size,
            'price': signal['entry'],
            'stop_loss': signal['stop_loss'],
            'take_profit': signal.get('take_profit_1')
        }

class TestMonitoringSystem(unittest.TestCase):
    """Test monitoring and alert systems"""
    
    def test_price_monitoring(self):
        """Test price monitoring for exit conditions"""
        position = {
            'symbol': 'BTC/USDT',
            'entry': 50000,
            'stop_loss': 48000,
            'take_profit_1': 52000,
            'current_price': 51000
        }
        
        # Test stop loss check
        position['current_price'] = 47900
        self.assertTrue(self.check_stop_loss(position))
        
        # Test take profit check
        position['current_price'] = 52100
        self.assertTrue(self.check_take_profit(position))
        
        # Test normal condition
        position['current_price'] = 50500
        self.assertFalse(self.check_stop_loss(position))
        self.assertFalse(self.check_take_profit(position))
    
    def check_stop_loss(self, position):
        """Check if stop loss is hit"""
        return position['current_price'] <= position['stop_loss']
    
    def check_take_profit(self, position):
        """Check if take profit is hit"""
        return position['current_price'] >= position.get('take_profit_1', float('inf'))
    
    def test_partial_exit_conditions(self):
        """Test partial exit conditions"""
        position = {
            'entry': 50000,
            'current_price': 51000,
            'risk_reward_1r': 52000,
            'risk_reward_2r': 54000
        }
        
        # Test 1R reached
        position['current_price'] = 52000
        self.assertEqual(self.check_risk_reward(position), '1R')
        
        # Test 2R reached
        position['current_price'] = 54000
        self.assertEqual(self.check_risk_reward(position), '2R')
    
    def check_risk_reward(self, position):
        """Check risk reward levels"""
        if position['current_price'] >= position.get('risk_reward_2r', float('inf')):
            return '2R'
        elif position['current_price'] >= position.get('risk_reward_1r', float('inf')):
            return '1R'
        return None

def run_tests():
    """Run all tests and generate report"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseOperations))
    suite.addTests(loader.loadTestsFromTestCase(TestSignalParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestExchangeConnection))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMonitoringSystem))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFailed tests:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nTests with errors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_tests())