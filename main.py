#!/usr/bin/env python3
"""
Gauls Copy Trading System - Main Entry Point
Provides centralized control for all system components
"""

import sys
import os
import argparse
import asyncio
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def start_component(component: str):
    """Start a specific component"""
    components = {
        'trader': 'src/core/gauls_copy_trader.py',
        'listener': 'src/monitors/live_telegram_listener.py',
        'exit-monitor': 'src/monitors/exit_monitor_v2.py',
        'update-processor': 'src/processors/gauls_trade_update_processor.py',
        'dashboard': 'src/interfaces/gauls_dashboard_enhanced.py',
        'health-monitor': 'src/monitors/check_system_health.py',
    }
    
    if component not in components:
        print(f"❌ Unknown component: {component}")
        print(f"Available components: {', '.join(components.keys())}")
        return
    
    script_path = Path(__file__).parent / components[component]
    print(f"🚀 Starting {component}...")
    
    # Set environment variable for production
    os.environ['TRADING_MODE'] = 'production'
    
    # Import and run the component
    if component == 'trader':
        from core.gauls_copy_trader import GaulsCopyTrader, main
        asyncio.run(main())
    elif component == 'listener':
        from monitors.live_telegram_listener import main
        asyncio.run(main())
    elif component == 'exit-monitor':
        from monitors.exit_monitor_v2 import main
        asyncio.run(main())
    elif component == 'update-processor':
        from processors.gauls_trade_update_processor import main
        asyncio.run(main())
    elif component == 'dashboard':
        from interfaces.gauls_dashboard_enhanced import main
        main()
    elif component == 'health-monitor':
        from monitors.check_system_health import main
        main()

def run_tests():
    """Run all tests"""
    print("🧪 Running tests...")
    test_dir = Path(__file__).parent / 'tests'
    subprocess.run([sys.executable, str(test_dir / 'run_all_tests.py')])

def check_status():
    """Check system status"""
    print("📊 System Status")
    print("=" * 50)
    
    # Check services
    services = [
        'gauls-telegram-listener',
        'gauls-copy-trader',
        'gauls-exit-monitor',
        'gauls-update-processor',
        'gauls-dashboard',
        'gauls-health-monitor'
    ]
    
    for service in services:
        result = subprocess.run(
            ['systemctl', 'is-active', service],
            capture_output=True,
            text=True
        )
        status = result.stdout.strip()
        icon = "✅" if status == "active" else "❌"
        print(f"{icon} {service}: {status}")
    
    print("\n📁 Directory Structure")
    print("=" * 50)
    src_dir = Path(__file__).parent / 'src'
    for subdir in ['core', 'parsers', 'processors', 'monitors', 'executors', 'interfaces', 'utils']:
        path = src_dir / subdir
        if path.exists():
            file_count = len(list(path.glob('*.py')))
            print(f"  {subdir}/: {file_count} Python files")

def main():
    parser = argparse.ArgumentParser(description='Gauls Copy Trading System')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start a component')
    start_parser.add_argument('component', help='Component to start')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run tests')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Check system status')
    
    args = parser.parse_args()
    
    if args.command == 'start':
        start_component(args.component)
    elif args.command == 'test':
        run_tests()
    elif args.command == 'status':
        check_status()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()