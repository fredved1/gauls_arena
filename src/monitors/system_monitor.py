#!/usr/bin/env python3
"""
Gauls Trading System - Real-time System Monitor
Live monitoring dashboard with automated alerts
"""

import os
import sys
import time
import sqlite3
import psutil
from datetime import datetime, timedelta
from colorama import init, Fore, Back, Style
import subprocess
import json

# Initialize colorama
init(autoreset=True)

class SystemMonitor:
    def __init__(self):
        self.system_dir = '/gauls-copy-trading-system'
        self.databases = {
            'trades': f'{self.system_dir}/databases/trades.db',
            'gauls': f'{self.system_dir}/databases/gauls_trading.db'
        }
        
        self.critical_processes = [
            ('gauls_copy_trader.py', '🤖 Copy Trader'),
            ('live_telegram_listener.py', '📱 Telegram Monitor'),
            ('exit_monitor_v2.py', '🎯 Exit Monitor'),
            ('gauls_trade_update_processor.py', '📊 Update Processor'),
            ('gauls_dashboard_enhanced.py', '🖥️ Dashboard')
        ]
        
        self.alerts = []
        self.last_check = {}
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def get_process_status(self):
        """Get status of all critical processes"""
        status = {}
        for script, name in self.critical_processes:
            found = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if script in cmdline and 'gauls-copy-trading-system' in cmdline:
                        uptime = time.time() - proc.info['create_time']
                        status[script] = {
                            'running': True,
                            'pid': proc.info['pid'],
                            'name': name,
                            'uptime': self.format_uptime(uptime)
                        }
                        found = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if not found:
                status[script] = {
                    'running': False,
                    'name': name,
                    'pid': None,
                    'uptime': None
                }
                # Add to alerts if process stopped
                if script not in self.last_check or self.last_check[script]:
                    self.alerts.append(f"⚠️ {name} has stopped!")
            
            self.last_check[script] = found
        
        return status
    
    def format_uptime(self, seconds):
        """Format uptime in human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def get_trade_stats(self):
        """Get trading statistics"""
        stats = {
            'total_trades': 0,
            'open_positions': 0,
            'today_trades': 0,
            'total_pnl': 0,
            'last_trade': None
        }
        
        try:
            conn = sqlite3.connect(self.databases['trades'])
            cursor = conn.cursor()
            
            # Total trades
            cursor.execute("SELECT COUNT(*) FROM trades")
            stats['total_trades'] = cursor.fetchone()[0]
            
            # Open positions
            cursor.execute("SELECT COUNT(*) FROM trades WHERE status='open'")
            stats['open_positions'] = cursor.fetchone()[0]
            
            # Today's trades
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) FROM trades WHERE DATE(entry_time) = DATE(?)", (today,))
            stats['today_trades'] = cursor.fetchone()[0]
            
            # Total PnL
            cursor.execute("SELECT SUM(pnl), SUM(partial_pnl) FROM trades WHERE pnl IS NOT NULL OR partial_pnl IS NOT NULL")
            result = cursor.fetchone()
            if result:
                pnl = (result[0] or 0) + (result[1] or 0)
                stats['total_pnl'] = round(pnl, 2)
            
            # Last trade
            cursor.execute("""
                SELECT symbol, side, entry_price, status, entry_time 
                FROM trades 
                ORDER BY id DESC 
                LIMIT 1
            """)
            last = cursor.fetchone()
            if last:
                stats['last_trade'] = {
                    'symbol': last[0],
                    'side': last[1],
                    'price': last[2],
                    'status': last[3],
                    'time': last[4]
                }
            
            conn.close()
        except Exception as e:
            self.alerts.append(f"⚠️ Database error: {str(e)}")
        
        return stats
    
    def get_system_resources(self):
        """Get system resource usage"""
        return {
            'cpu': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent
        }
    
    def display_dashboard(self):
        """Display the monitoring dashboard"""
        self.clear_screen()
        
        # Header
        print(f"{Back.BLUE}{Fore.WHITE} GAULS TRADING SYSTEM MONITOR {Style.RESET_ALL}")
        print(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Process Status
        print(f"\n{Fore.CYAN}📋 PROCESS STATUS:{Style.RESET_ALL}")
        process_status = self.get_process_status()
        
        all_running = True
        for script, info in process_status.items():
            if info['running']:
                status = f"{Fore.GREEN}●{Style.RESET_ALL} Running"
                details = f"PID: {info['pid']:<8} Uptime: {info['uptime']}"
            else:
                status = f"{Fore.RED}●{Style.RESET_ALL} Stopped"
                details = "Not running"
                all_running = False
            
            print(f"  {info['name']:<25} {status:<20} {details}")
        
        # Overall system status
        if all_running:
            system_status = f"{Back.GREEN}{Fore.WHITE} ALL SYSTEMS OPERATIONAL {Style.RESET_ALL}"
        else:
            system_status = f"{Back.RED}{Fore.WHITE} SYSTEM DEGRADED {Style.RESET_ALL}"
        
        print(f"\n{system_status}")
        
        # Trading Statistics
        print(f"\n{Fore.CYAN}📈 TRADING STATISTICS:{Style.RESET_ALL}")
        stats = self.get_trade_stats()
        
        print(f"  Total Trades:    {stats['total_trades']}")
        print(f"  Open Positions:  {stats['open_positions']}")
        print(f"  Today's Trades:  {stats['today_trades']}")
        
        if stats['total_pnl'] >= 0:
            pnl_color = Fore.GREEN
        else:
            pnl_color = Fore.RED
        print(f"  Total PnL:       {pnl_color}${stats['total_pnl']}{Style.RESET_ALL}")
        
        if stats['last_trade']:
            lt = stats['last_trade']
            status_color = Fore.YELLOW if lt['status'] == 'open' else Fore.WHITE
            print(f"\n  Last Trade: {lt['symbol']} {lt['side'].upper()} @ {lt['price']}")
            print(f"              Status: {status_color}{lt['status']}{Style.RESET_ALL}")
        
        # System Resources
        print(f"\n{Fore.CYAN}💻 SYSTEM RESOURCES:{Style.RESET_ALL}")
        resources = self.get_system_resources()
        
        # CPU bar
        cpu_bar = self.create_bar(resources['cpu'], 100)
        cpu_color = Fore.GREEN if resources['cpu'] < 70 else Fore.YELLOW if resources['cpu'] < 90 else Fore.RED
        print(f"  CPU:    {cpu_color}{cpu_bar}{Style.RESET_ALL} {resources['cpu']:.1f}%")
        
        # Memory bar
        mem_bar = self.create_bar(resources['memory'], 100)
        mem_color = Fore.GREEN if resources['memory'] < 70 else Fore.YELLOW if resources['memory'] < 90 else Fore.RED
        print(f"  Memory: {mem_color}{mem_bar}{Style.RESET_ALL} {resources['memory']:.1f}%")
        
        # Disk bar
        disk_bar = self.create_bar(resources['disk'], 100)
        disk_color = Fore.GREEN if resources['disk'] < 70 else Fore.YELLOW if resources['disk'] < 90 else Fore.RED
        print(f"  Disk:   {disk_color}{disk_bar}{Style.RESET_ALL} {resources['disk']:.1f}%")
        
        # Alerts
        if self.alerts:
            print(f"\n{Fore.YELLOW}⚠️ ALERTS:{Style.RESET_ALL}")
            for alert in self.alerts[-5:]:  # Show last 5 alerts
                print(f"  {alert}")
        
        # Footer
        print("\n" + "="*70)
        print("Press Ctrl+C to exit | Auto-refresh every 5 seconds")
    
    def create_bar(self, value, max_value, width=20):
        """Create a progress bar"""
        filled = int((value / max_value) * width)
        bar = '█' * filled + '░' * (width - filled)
        return bar
    
    def run_continuous(self):
        """Run continuous monitoring"""
        try:
            while True:
                self.display_dashboard()
                time.sleep(5)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Monitor stopped by user.{Style.RESET_ALL}")
            sys.exit(0)
    
    def run_once(self):
        """Run single check and exit"""
        self.display_dashboard()
        
        # Check for critical issues
        process_status = self.get_process_status()
        stopped_processes = [info['name'] for script, info in process_status.items() if not info['running']]
        
        if stopped_processes:
            print(f"\n{Back.RED}{Fore.WHITE} CRITICAL: The following processes are not running: {Style.RESET_ALL}")
            for proc in stopped_processes:
                print(f"  - {proc}")
            return 1
        
        return 0

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Gauls Trading System Monitor')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    monitor = SystemMonitor()
    
    if args.json:
        # Output JSON for integration with other tools
        process_status = monitor.get_process_status()
        trade_stats = monitor.get_trade_stats()
        resources = monitor.get_system_resources()
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'processes': process_status,
            'trades': trade_stats,
            'resources': resources,
            'healthy': all(info['running'] for info in process_status.values())
        }
        
        print(json.dumps(output, indent=2))
        sys.exit(0 if output['healthy'] else 1)
    
    elif args.once:
        sys.exit(monitor.run_once())
    else:
        monitor.run_continuous()

if __name__ == "__main__":
    main()