#!/usr/bin/env python3
"""
Comprehensive tests for Gauls signal parsing
Tests all variations of signal formats to prevent future issues
"""

import sys
import re
sys.path.append('/gauls-copy-trading-system')

# Import the parser from gauls_copy_trader
from core.gauls_copy_trader import GaulsSignalParser

def test_signal_variations():
    """Test all known variations of Gauls signal formats"""
    
    parser = GaulsSignalParser()
    
    test_cases = [
        {
            'name': 'BTC with $ symbol',
            'text': '''$BTC Buying Setup:

👉 Entry: CMP
👉 TP: 114786
👉 SL: 111468

Cheers 

#TraderGauls🎭''',
            'expected': {
                'symbol': 'BTC',
                'entry': 'CMP',
                'take_profit': 114786.0,
                'stop_loss': 111468.0
            }
        },
        {
            'name': 'BTC without $ symbol',
            'text': '''BTC Buying Setup:

👉 Entry: CMP
👉 TP: 114786
👉 SL: 111468''',
            'expected': {
                'symbol': 'BTC',
                'entry': 'CMP',
                'take_profit': 114786.0,
                'stop_loss': 111468.0
            }
        },
        {
            'name': 'SEI Spot/Swing format',
            'text': '''$SEI Spot/Swing Buying Setup:

👉 Entry: CMP till 2780
👉 TP: 0.43
👉 SL: 0.26

Cheers

**#TraderGauls****🎭**''',
            'expected': {
                'symbol': 'SEI',
                'entry': 'CMP',
                'take_profit': 0.43,
                'stop_loss': 0.26
            }
        },
        {
            'name': 'AI with specific entry price',
            'text': '''$AI Buying Setup:

👉 Entry: 111216 (A bit above)
👉 TP: 114914.6
👉 SL: 108645

#TraderGauls''',
            'expected': {
                'symbol': 'AI',
                'entry': 111216.0,
                'take_profit': 114914.6,
                'stop_loss': 108645.0,
                'entry_hint': 'A bit above'
            }
        },
        {
            'name': 'ETH with Target instead of TP',
            'text': '''$ETH Buying Setup:

Entry: 3200
Target: 3500
SL: 3000''',
            'expected': {
                'symbol': 'ETH',
                'entry': 3200.0,
                'take_profit': 3500.0,
                'stop_loss': 3000.0
            }
        },
        {
            'name': 'With emoji arrows',
            'text': '''$DOGE Buying Setup:

➡️ Entry: 0.35
➡️ TP: 0.42
➡️ SL: 0.30''',
            'expected': {
                'symbol': 'DOGE',
                'entry': 0.35,
                'take_profit': 0.42,
                'stop_loss': 0.30
            }
        }
    ]
    
    print("="*60)
    print("🧪 TESTING GAULS SIGNAL PARSER")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print("-"*40)
        
        result = parser.parse_signal(test['text'])
        
        if result is None:
            print(f"❌ FAILED: Parser returned None")
            failed += 1
            continue
        
        # Check each expected field
        all_good = True
        for key, expected_value in test['expected'].items():
            actual_value = result.get(key) if key != 'symbol' else result.get('symbol', '').replace('/USDT', '')
            
            if key == 'entry' and expected_value == 'CMP':
                # CMP entries are special
                if actual_value != 'CMP':
                    print(f"  ❌ {key}: Expected 'CMP', got '{actual_value}'")
                    all_good = False
                else:
                    print(f"  ✅ {key}: {actual_value}")
            elif isinstance(expected_value, float):
                # For numeric values, check if close enough
                if actual_value and abs(float(actual_value) - expected_value) < 0.01:
                    print(f"  ✅ {key}: {actual_value}")
                else:
                    print(f"  ❌ {key}: Expected {expected_value}, got {actual_value}")
                    all_good = False
            else:
                if actual_value == expected_value:
                    print(f"  ✅ {key}: {actual_value}")
                else:
                    print(f"  ❌ {key}: Expected {expected_value}, got {actual_value}")
                    all_good = False
        
        if all_good:
            print("✅ PASSED")
            passed += 1
        else:
            print("❌ FAILED")
            failed += 1
    
    print("\n" + "="*60)
    print(f"📊 RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed > 0:
        print("\n⚠️ WARNING: Some tests failed! The parser needs fixes.")
        return False
    else:
        print("\n✅ All tests passed! Parser is working correctly.")
        return True

def test_sql_patterns():
    """Test SQL query patterns for finding signals"""
    
    import sqlite3
    
    print("\n" + "="*60)
    print("🔍 TESTING SQL QUERY PATTERNS")
    print("="*60)
    
    # Test messages
    messages = [
        "$BTC Buying Setup:\n👉 Entry: CMP\n👉 TP: 114786\n👉 SL: 111468",
        "BTC Buying Setup:\nEntry: CMP\nTP: 114786\nSL: 111468",
        "$ETH buying setup\nEntry: 3200\nTarget: 3500\nSL: 3000",
        "Random message without signals",
        "Market update: BTC looking strong"
    ]
    
    # SQL patterns from the scanner
    patterns = {
        'has_setup': "message_text LIKE '%Setup%' OR message_text LIKE '%setup%'",
        'has_entry': "message_text LIKE '%Entry:%' OR message_text LIKE '%ENTRY :%' OR message_text LIKE '%Entry :%' OR message_text LIKE '%Entry: %'",
        'has_tp': "message_text LIKE '%TP:%' OR message_text LIKE '%Target:%' OR message_text LIKE '%TARGET :%' OR message_text LIKE '%target:%' OR message_text LIKE '%TP: %'",
        'has_sl': "message_text LIKE '%SL:%' OR message_text LIKE '%Invalidation:%' OR message_text LIKE '%invalidation:%' OR message_text LIKE '%SL: %'"
    }
    
    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i}:")
        print(f"  Text: {msg[:50]}...")
        
        # Check each pattern
        results = {}
        for name, pattern in patterns.items():
            # Convert SQL LIKE to Python check
            check = pattern.replace("message_text LIKE ", "").replace(" OR ", "|")
            # This is simplified - in reality we'd need proper SQL
            has_match = any(
                term.strip("'%") in msg 
                for term in re.findall(r"'%([^%]+)%'", pattern)
            )
            results[name] = has_match
            print(f"  {name}: {'✅' if has_match else '❌'}")
        
        # Would it be caught by scanner?
        would_catch = all(results.values())
        print(f"  Would be caught: {'✅ YES' if would_catch else '❌ NO'}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    # Run tests
    test_signal_variations()
    test_sql_patterns()
    
    print("\n💡 Why the pipeline didn't catch this:")
    print("1. No unit tests existed for signal parsing")
    print("2. Integration tests didn't cover format variations")
    print("3. The $ symbol variation wasn't anticipated")
    print("4. Manual testing used different format than production")
    print("\n✅ Now we have comprehensive tests to prevent this!"