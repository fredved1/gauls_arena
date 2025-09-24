#!/usr/bin/env python3
"""
Comprehensive Test Suite for Gauls Trading System
Runs all unit tests to prevent regressions
"""

import unittest
import sys
import os

# Add path
sys.path.append('/gauls-copy-trading-system')

def run_all_tests():
    """Run all test suites"""
    
    print("="*60)
    print("🧪 GAULS TRADING SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    # Create test loader
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Import and add all test modules
    test_modules = [
        'test_system_components',     # Database operations
        'test_gauls_signal_parser',   # Signal parsing (NEW!)
        'test_trade_updates',          # Trade update parsing (NEW!)
    ]
    
    for module_name in test_modules:
        try:
            module = __import__(module_name)
            suite.addTests(loader.loadTestsFromModule(module))
            print(f"✅ Loaded tests from {module_name}")
        except ImportError as e:
            print(f"⚠️  Could not load {module_name}: {e}")
    
    # Run tests
    print("\n" + "="*60)
    print("Running tests...")
    print("="*60 + "\n")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED!")
        
        if result.failures:
            print("\nFailed tests:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        
        if result.errors:
            print("\nTests with errors:")
            for test, traceback in result.errors:
                print(f"  - {test}")
    
    return result.wasSuccessful()

def check_critical_patterns():
    """Check for critical patterns that caused bugs"""
    
    print("\n" + "="*60)
    print("🔍 CRITICAL PATTERN CHECKS")
    print("="*60)
    
    critical_checks = [
        {
            'name': 'Signal parser handles $ and no-$',
            'file': '/gauls-copy-trading-system/gauls_copy_trader.py',
            'pattern': r'\$?([A-Z]{2,10})',
            'expected': True
        },
        {
            'name': 'Update processor handles $ and no-$',
            'file': '/gauls-copy-trading-system/gauls_trade_update_processor.py',
            'pattern': r'\$?([A-Z]{2,10})',
            'expected': True
        }
    ]
    
    import re
    
    for check in critical_checks:
        try:
            with open(check['file'], 'r') as f:
                content = f.read()
                if check['pattern'] in content:
                    print(f"✅ {check['name']}")
                else:
                    print(f"❌ {check['name']} - Pattern not found!")
        except Exception as e:
            print(f"⚠️  Could not check {check['name']}: {e}")

if __name__ == '__main__':
    # Set test mode to avoid real trading
    os.environ['TRADING_MODE'] = 'test'
    
    # Run checks
    check_critical_patterns()
    
    # Run tests
    success = run_all_tests()
    
    # Exit code for CI/CD
    sys.exit(0 if success else 1)