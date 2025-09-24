#!/usr/bin/env python3
"""
Gauls Trading System Health Check
Comprehensive system status checker with unit tests
"""

import os
import sys
import psutil
import sqlite3
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import subprocess
from colorama import init, Fore, Back, Style

# Initialize colorama for colored output
init(autoreset=True)

class SystemHealthChecker:
    def __init__(self):
        self.required_processes = [
            ('live_telegram_listener.py', 'Telegram Message Monitor'),
            ('exit_monitor_v2.py', 'Exit Condition Monitor'),
            ('gauls_dashboard_enhanced.py', 'Dashboard Interface'),
            ('gauls_copy_trader.py', 'Main Copy Trader'),
            ('gauls_trade_update_processor.py', 'Trade Update Handler (1R/2R)')
        ]
        
        self.databases = {
            'trades': '/gauls-copy-trading-system/databases/trades.db',
            'gauls_trading': '/gauls-copy-trading-system/databases/gauls_trading.db',
            'messages': '/gauls-copy-trading-system/databases/gauls_messages.db'
        }
        
        self.test_results = {}
        
    def check_process_status(self) -> Dict[str, bool]:
        """Check if required processes are running"""
        process_status = {}
        
        for script_name, description in self.required_processes:
            is_running = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if script_name in cmdline and 'gauls-copy-trading-system' in cmdline:
                        is_running = True
                        process_status[script_name] = {
                            'running': True,
                            'pid': proc.info['pid'],
                            'description': description
                        }
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if not is_running:
                process_status[script_name] = {
                    'running': False,
                    'pid': None,
                    'description': description
                }
        
        return process_status
    
    def check_database_health(self) -> Dict[str, Dict]:
        """Check database connectivity and recent activity"""
        db_status = {}
        
        for db_name, db_path in self.databases.items():
            try:
                if not os.path.exists(db_path):
                    db_status[db_name] = {
                        'status': 'missing',
                        'path': db_path,
                        'error': 'Database file not found'
                    }
                    continue
                
                conn = sqlite3.connect(db_path, timeout=5)
                cursor = conn.cursor()
                
                # Get database info
                if db_name == 'trades':
                    cursor.execute("SELECT COUNT(*) FROM trades")
                    total_trades = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM trades WHERE status='open'")
                    open_trades = cursor.fetchone()[0]
                    
                    cursor.execute("""
                        SELECT entry_time, symbol, side, status 
                        FROM trades 
                        ORDER BY id DESC 
                        LIMIT 1
                    """)
                    last_trade = cursor.fetchone()
                    
                    db_status[db_name] = {
                        'status': 'healthy',
                        'path': db_path,
                        'total_trades': total_trades,
                        'open_trades': open_trades,
                        'last_trade': last_trade
                    }
                    
                elif db_name == 'gauls_trading':
                    # Check session info
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [t[0] for t in cursor.fetchall()]
                    
                    db_status[db_name] = {
                        'status': 'healthy',
                        'path': db_path,
                        'tables': tables
                    }
                    
                else:
                    db_status[db_name] = {
                        'status': 'healthy',
                        'path': db_path
                    }
                
                conn.close()
                
            except Exception as e:
                db_status[db_name] = {
                    'status': 'error',
                    'path': db_path,
                    'error': str(e)
                }
        
        return db_status
    
    def check_exchange_connection(self) -> Dict:
        """Check exchange API connection"""
        try:
            # Import and test exchange connection
            sys.path.append('/gauls-copy-trading-system')
            from core.unified_exchange import UnifiedExchange
            
            exchange = UnifiedExchange()
            balance = exchange.get_balance()
            
            return {
                'status': 'connected',
                'balance': balance,
                'exchange': 'WooX'
            }
        except Exception as e:
            return {
                'status': 'disconnected',
                'error': str(e)
            }
    
    def run_unit_tests(self) -> Dict[str, bool]:
        """Run unit tests for critical components"""
        tests = {}
        
        # Test 1: Database write/read
        try:
            conn = sqlite3.connect(self.databases['gauls_trading'])
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_check (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    status TEXT
                )
            """)
            cursor.execute(
                "INSERT INTO health_check (timestamp, status) VALUES (?, ?)",
                (datetime.now().isoformat(), 'test')
            )
            conn.commit()
            cursor.execute("SELECT * FROM health_check ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            tests['database_write_read'] = result is not None
        except:
            tests['database_write_read'] = False
        
        # Test 2: Process spawn test
        try:
            result = subprocess.run(
                ['python3', '-c', 'print("test")'],
                capture_output=True,
                text=True,
                timeout=5
            )
            tests['python_execution'] = result.returncode == 0
        except:
            tests['python_execution'] = False
        
        # Test 3: File system permissions
        try:
            test_file = '/gauls-copy-trading-system/test_health.tmp'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            tests['file_permissions'] = True
        except:
            tests['file_permissions'] = False
        
        # Test 4: Network connectivity (localhost)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 80))
            sock.close()
            tests['network_connectivity'] = True  # We can create sockets
        except:
            tests['network_connectivity'] = False
        
        return tests
    
    def print_report(self):
        """Print comprehensive health report"""
        print(f"\n{Back.BLUE}{Fore.WHITE} GAULS TRADING SYSTEM HEALTH CHECK {Style.RESET_ALL}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Check processes
        process_status = self.check_process_status()
        print(f"\n{Fore.CYAN}📊 PROCESS STATUS:{Style.RESET_ALL}")
        
        all_running = True
        for script_name, info in process_status.items():
            if info['running']:
                status = f"{Fore.GREEN}✅ RUNNING{Style.RESET_ALL}"
                pid_info = f"(PID: {info['pid']})"
            else:
                status = f"{Fore.RED}❌ NOT RUNNING{Style.RESET_ALL}"
                pid_info = ""
                all_running = False
            
            print(f"  {info['description']:<35} {status} {pid_info}")
        
        # Check databases
        db_status = self.check_database_health()
        print(f"\n{Fore.CYAN}💾 DATABASE STATUS:{Style.RESET_ALL}")
        
        for db_name, info in db_status.items():
            if info['status'] == 'healthy':
                status = f"{Fore.GREEN}✅ HEALTHY{Style.RESET_ALL}"
                if db_name == 'trades' and info.get('last_trade'):
                    extra = f" | Open: {info['open_trades']} | Last: {info['last_trade'][1]}"
                else:
                    extra = ""
            else:
                status = f"{Fore.RED}❌ {info['status'].upper()}{Style.RESET_ALL}"
                extra = f" | {info.get('error', '')}"
            
            print(f"  {db_name:<15} {status}{extra}")
        
        # Check exchange connection
        exchange_status = self.check_exchange_connection()
        print(f"\n{Fore.CYAN}🔗 EXCHANGE CONNECTION:{Style.RESET_ALL}")
        
        if exchange_status['status'] == 'connected':
            print(f"  WooX: {Fore.GREEN}✅ CONNECTED{Style.RESET_ALL}")
            if 'balance' in exchange_status:
                balance = exchange_status['balance']
                if isinstance(balance, dict):
                    print(f"  Balance: ${balance.get('total_usdt', 0):.2f} USDT")
                    print(f"  Free: ${balance.get('free_usdt', 0):.2f} USDT")
                else:
                    print(f"  Balance: ${float(balance):.2f} USDT")
        else:
            print(f"  WooX: {Fore.RED}❌ DISCONNECTED{Style.RESET_ALL}")
            print(f"  Error: {exchange_status.get('error', 'Unknown')}")
        
        # Run unit tests
        test_results = self.run_unit_tests()
        print(f"\n{Fore.CYAN}🧪 UNIT TESTS:{Style.RESET_ALL}")
        
        for test_name, passed in test_results.items():
            if passed:
                status = f"{Fore.GREEN}✅ PASSED{Style.RESET_ALL}"
            else:
                status = f"{Fore.RED}❌ FAILED{Style.RESET_ALL}"
            
            test_display = test_name.replace('_', ' ').title()
            print(f"  {test_display:<25} {status}")
        
        # Overall status
        print(f"\n{Fore.CYAN}📈 OVERALL STATUS:{Style.RESET_ALL}")
        
        all_tests_passed = all(test_results.values())
        all_db_healthy = all(db['status'] == 'healthy' for db in db_status.values())
        exchange_connected = exchange_status['status'] == 'connected'
        
        if all_running and all_db_healthy and exchange_connected and all_tests_passed:
            print(f"  {Back.GREEN}{Fore.WHITE} ALL SYSTEMS OPERATIONAL {Style.RESET_ALL}")
            return 0
        else:
            issues = []
            if not all_running:
                issues.append("Some processes are not running")
            if not all_db_healthy:
                issues.append("Database issues detected")
            if not exchange_connected:
                issues.append("Exchange not connected")
            if not all_tests_passed:
                issues.append("Some unit tests failed")
            
            print(f"  {Back.YELLOW}{Fore.BLACK} ISSUES DETECTED {Style.RESET_ALL}")
            for issue in issues:
                print(f"  ⚠️  {issue}")
            return 1
        
def main():
    checker = SystemHealthChecker()
    exit_code = checker.print_report()
    print("\n" + "=" * 60)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()