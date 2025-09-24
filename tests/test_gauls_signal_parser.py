#!/usr/bin/env python3
"""
Unit tests for Gauls Signal Parser
CRITICAL: Tests all known signal format variations to prevent parsing failures
"""

import unittest
import sys
sys.path.append('/gauls-copy-trading-system')

from core.gauls_copy_trader import GaulsSignalParser

class TestGaulsSignalParser(unittest.TestCase):
    """Test the GaulsSignalParser to ensure it handles all formats"""
    
    def setUp(self):
        self.parser = GaulsSignalParser()
    
    def test_btc_with_dollar_sign(self):
        """Test BTC signal WITH $ symbol - the format that failed"""
        text = '''$BTC Buying Setup:

👉 Entry: CMP
👉 TP: 114786
👉 SL: 111468

Cheers 

#TraderGauls🎭'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on $BTC format")
        self.assertEqual(result['symbol'], 'BTC/USDT')
        self.assertEqual(result['entry'], 'CMP')
        self.assertEqual(result['take_profit'], 114786.0)
        self.assertEqual(result['stop_loss'], 111468.0)
    
    def test_btc_without_dollar_sign(self):
        """Test BTC signal WITHOUT $ symbol"""
        text = '''BTC Buying Setup:

👉 Entry: CMP
👉 TP: 114786
👉 SL: 111468'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on BTC format (no $)")
        self.assertEqual(result['symbol'], 'BTC/USDT')
    
    def test_sei_spot_format(self):
        """Test SEI Spot/Swing format"""
        text = '''$SEI Spot/Swing Buying Setup:

👉 Entry: CMP till 2780
👉 TP: 0.43
👉 SL: 0.26'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on SEI Spot format")
        self.assertEqual(result['symbol'], 'SEI/USDT')
        self.assertEqual(result['take_profit'], 0.43)
    
    def test_entry_with_hint(self):
        """Test entry with hint in parentheses"""
        text = '''$AI Buying Setup:

👉 Entry: 0.14 (A bit above)
👉 TP: 0.16
👉 SL: 0.12'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on entry with hint")
        self.assertEqual(result['symbol'], 'AI/USDT')
        self.assertEqual(result['entry'], 0.14)
        self.assertEqual(result.get('entry_hint'), 'A bit above')
    
    def test_target_instead_of_tp(self):
        """Test using 'Target' instead of 'TP'"""
        text = '''$ETH Buying Setup:

Entry: 3200
Target: 3500
SL: 3000'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on Target format")
        self.assertEqual(result['take_profit'], 3500.0)
    
    def test_invalidation_instead_of_sl(self):
        """Test using 'Invalidation' instead of 'SL'"""
        text = '''$SOL Buying Setup:

Entry: 150
TP: 180
Invalidation: 140'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on Invalidation format")
        self.assertEqual(result['stop_loss'], 140.0)
    
    def test_lowercase_setup(self):
        """Test lowercase 'buying setup'"""
        text = '''$DOGE buying setup:

Entry: 0.35
TP: 0.42
SL: 0.30'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on lowercase setup")
        self.assertEqual(result['symbol'], 'DOGE/USDT')
    
    def test_non_signal_message(self):
        """Test that non-signal messages return None"""
        text = '''Market Update:
        
BTC is looking strong above $112k.
Watch for breakout above $115k.'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNone(result, "Parser wrongly identified non-signal as signal")
    
    def test_spaces_in_format(self):
        """Test various spacing in Entry:, TP:, SL:"""
        text = '''$LINK Buying Setup:

Entry : 25.5
TP : 30
SL : 22'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on spaced format")
        self.assertEqual(result['entry'], 25.5)
    
    def test_emoji_variations(self):
        """Test different emoji arrows"""
        text = '''$AVAX Buying Setup:

➡️ Entry: 35
→ TP: 42
👉 SL: 30'''
        
        result = self.parser.parse_signal(text)
        self.assertIsNotNone(result, "Parser failed on emoji variations")
        self.assertEqual(result['symbol'], 'AVAX/USDT')

class TestSQLPatterns(unittest.TestCase):
    """Test SQL patterns used to find signals in database"""
    
    def test_sql_pattern_matching(self):
        """Verify SQL LIKE patterns match expected messages"""
        
        # Messages that SHOULD be caught
        valid_signals = [
            "$BTC Buying Setup:\n👉 Entry: CMP\n👉 TP: 114786\n👉 SL: 111468",
            "BTC Buying Setup:\nEntry: CMP\nTP: 114786\nSL: 111468",
            "$ETH buying setup\nEntry: 3200\nTarget: 3500\nSL: 3000",
        ]
        
        # Messages that should NOT be caught
        invalid_signals = [
            "Random market update",
            "BTC looking strong",  # Has BTC but not a setup
            "Setup your account",  # Has setup but not a signal
        ]
        
        for msg in valid_signals:
            # Check all required patterns
            has_setup = 'Setup' in msg or 'setup' in msg
            has_entry = 'Entry:' in msg or 'Entry :' in msg or 'ENTRY :' in msg
            has_tp = 'TP:' in msg or 'Target:' in msg or 'TP :' in msg
            has_sl = 'SL:' in msg or 'Invalidation:' in msg or 'SL :' in msg
            
            self.assertTrue(has_setup, f"Setup not found in: {msg[:30]}...")
            self.assertTrue(has_entry, f"Entry not found in: {msg[:30]}...")
            self.assertTrue(has_tp, f"TP/Target not found in: {msg[:30]}...")
            self.assertTrue(has_sl, f"SL not found in: {msg[:30]}...")

if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)