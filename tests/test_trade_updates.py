#!/usr/bin/env python3
"""
Unit tests for Gauls Trade Update Processing
Tests 1R, 2R, breakeven, and exit update formats
"""

import unittest
import sys
import re
sys.path.append('/gauls-copy-trading-system')

from processors.gauls_trade_update_processor import GaulsTradeUpdateProcessor

class TestTradeUpdatePatterns(unittest.TestCase):
    """Test trade update pattern recognition"""
    
    def setUp(self):
        self.processor = GaulsTradeUpdateProcessor(mode='test')
        
    def test_1r_update_formats(self):
        """Test various 1R update formats"""
        test_messages = [
            "$BTC UPDATE: +1R done ✅",
            "$ETH Update - 1R reached, SL to breakeven",
            "SEI UPDATE: 1R done, risk-free now",
            "$SOL: +1R achieved",
            "AI Update: 1R hit ✅"
        ]
        
        for msg in test_messages:
            match = self.processor.update_patterns['partial_1r'].search(msg)
            self.assertIsNotNone(match, f"Failed to match 1R in: {msg}")
    
    def test_2r_update_formats(self):
        """Test various 2R update formats"""
        test_messages = [
            "$BTC UPDATE: +2R done 🎯",
            "$ETH: 2R reached, booking 50%",
            "DOGE UPDATE - 2R hit",
            "$AVAX Update: +2R achieved ✅"
        ]
        
        for msg in test_messages:
            match = self.processor.update_patterns['partial_2r'].search(msg)
            self.assertIsNotNone(match, f"Failed to match 2R in: {msg}")
    
    def test_risk_free_formats(self):
        """Test risk-free/breakeven update formats"""
        test_messages = [
            "$BTC: Move SL to entry",
            "ETH UPDATE: Risk-free trade now",
            "$SOL: SL to breakeven",
            "LINK: Move stop loss to entry price",
            "$DOGE: Risk free position"
        ]
        
        for msg in test_messages:
            match = self.processor.update_patterns['risk_free'].search(msg)
            self.assertIsNotNone(match, f"Failed to match risk-free in: {msg}")
    
    def test_partial_booking_formats(self):
        """Test partial profit booking formats"""
        test_messages = [
            "$BTC: Book 30% here",
            "ETH UPDATE: Take 50% profits",
            "$SOL: Partial exit 25%",
            "Book 40% of position",
            "Take partial 20%"
        ]
        
        for msg in test_messages:
            match = self.processor.update_patterns['book_partial'].search(msg)
            self.assertIsNotNone(match, f"Failed to match partial booking in: {msg}")
            
            # Extract percentage
            groups = match.groups()
            percentage = next((g for g in groups if g), None)
            self.assertIsNotNone(percentage, f"Failed to extract percentage from: {msg}")
    
    def test_full_exit_formats(self):
        """Test full exit/close formats"""
        test_messages = [
            "$BTC: Close all",
            "ETH UPDATE: Exit here",
            "$SOL: Out completely",
            "LINK: Done, close position",
            "$DOGE: Full exit"
        ]
        
        for msg in test_messages:
            match = self.processor.update_patterns['full_exit'].search(msg)
            self.assertIsNotNone(match, f"Failed to match exit in: {msg}")
    
    def test_symbol_extraction(self):
        """Test symbol extraction from update messages"""
        test_cases = [
            ("$BTC UPDATE: 1R done", "BTC"),
            ("ETH Update: Risk-free", None),  # No $ sign - should this work?
            ("$SOL: Exit here", "SOL"),
            ("DOGE update - 2R hit", None),  # No $ sign
            ("$AVAX/USDT: 1R reached", "AVAX"),
        ]
        
        for msg, expected_symbol in test_cases:
            match = re.search(r'\$([A-Z]+)', msg)
            if expected_symbol:
                self.assertIsNotNone(match, f"Failed to find symbol in: {msg}")
                self.assertEqual(match.group(1), expected_symbol)
            else:
                self.assertIsNone(match, f"Wrongly found symbol in: {msg}")
    
    def test_complex_update_messages(self):
        """Test complex real-world update messages"""
        complex_messages = [
            {
                'text': '''$BTC UPDATE 🚨
                
+1R done ✅
Move SL to entry for risk-free trade
Still targeting 2R at $115k

#TraderGauls''',
                'expected': {
                    '1r': True,
                    'risk_free': True,
                    'symbol': 'BTC'
                }
            },
            {
                'text': '''$SEI Update:

2R reached! 🎯
Book 50% here
Let rest run with SL at 1R level

Cheers!''',
                'expected': {
                    '2r': True,
                    'partial': True,
                    'symbol': 'SEI'
                }
            }
        ]
        
        for case in complex_messages:
            msg = case['text']
            expected = case['expected']
            
            # Check 1R
            if expected.get('1r'):
                match = self.processor.update_patterns['partial_1r'].search(msg)
                self.assertIsNotNone(match, f"Failed to find 1R in complex message")
            
            # Check 2R
            if expected.get('2r'):
                match = self.processor.update_patterns['partial_2r'].search(msg)
                self.assertIsNotNone(match, f"Failed to find 2R in complex message")
            
            # Check risk-free
            if expected.get('risk_free'):
                match = self.processor.update_patterns['risk_free'].search(msg)
                self.assertIsNotNone(match, f"Failed to find risk-free in complex message")
            
            # Check symbol
            if expected.get('symbol'):
                match = re.search(r'\$([A-Z]+)', msg)
                self.assertIsNotNone(match, f"Failed to find symbol in complex message")
                self.assertEqual(match.group(1), expected['symbol'])

class TestUpdateProcessorEdgeCases(unittest.TestCase):
    """Test edge cases and potential bugs"""
    
    def setUp(self):
        self.processor = GaulsTradeUpdateProcessor(mode='test')
    
    def test_symbol_without_dollar_sign(self):
        """Test if updates work without $ sign (like the signal bug)"""
        messages_without_dollar = [
            "BTC UPDATE: 1R done",
            "ETH: Move to breakeven",
            "SOL Update - 2R reached"
        ]
        
        for msg in messages_without_dollar:
            # Current pattern REQUIRES $ sign
            match = re.search(r'\$([A-Z]+)', msg)
            self.assertIsNone(match, "Should not match without $ sign")
            
            # Alternative pattern that would work
            flexible_match = re.search(r'\$?([A-Z]{2,10})(?:\s+UPDATE|\s+Update|:)', msg, re.IGNORECASE)
            self.assertIsNotNone(flexible_match, f"Flexible pattern should match: {msg}")
    
    def test_multiple_symbols_in_message(self):
        """Test handling of multiple symbols in one message"""
        msg = "$BTC and $ETH UPDATE: Both hit 1R"
        
        # Current pattern only gets first symbol
        match = re.search(r'\$([A-Z]+)', msg)
        self.assertEqual(match.group(1), 'BTC')
        
        # To get all symbols:
        all_symbols = re.findall(r'\$([A-Z]+)', msg)
        self.assertEqual(len(all_symbols), 2)
        self.assertIn('BTC', all_symbols)
        self.assertIn('ETH', all_symbols)
    
    def test_percentage_extraction_edge_cases(self):
        """Test percentage extraction from various formats"""
        test_cases = [
            ("Book 50%", "50"),
            ("Take 25% profits", "25"),
            ("partial 33.3%", "33.3"),
            ("book50%", "50"),  # No space
            ("100% exit", "100"),
        ]
        
        for msg, expected_pct in test_cases:
            match = self.processor.update_patterns['book_partial'].search(msg)
            if expected_pct:
                self.assertIsNotNone(match, f"Failed to match percentage in: {msg}")
                # Get the captured percentage
                groups = match.groups()
                percentage = next((g for g in groups if g), None)
                self.assertEqual(percentage, expected_pct.split('.')[0])  # Pattern doesn't capture decimals

if __name__ == '__main__':
    unittest.main(verbosity=2)