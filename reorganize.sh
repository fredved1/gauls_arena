#!/bin/bash

# Reorganize Gauls Trading System
# This script moves files to their appropriate directories

# Core components
mv gauls_copy_trader.py src/core/
mv config.py src/core/
mv unified_exchange.py src/core/

# Parsers
mkdir -p src/parsers
# gauls_copy_trader.py contains GaulsSignalParser - will extract later

# Processors
mv gauls_trade_update_processor.py src/processors/
mv gauls_partial_executor.py src/processors/
mv gauls_update_monitor.py src/processors/

# Monitors
mv exit_monitor_v2.py src/monitors/
mv live_telegram_listener.py src/monitors/
mv system_monitor.py src/monitors/
mv check_system_health.py src/monitors/

# Executors
mv execute_sei_trade.py src/executors/
mv woox_executor.py src/executors/

# Interfaces
mv gauls_dashboard.py src/interfaces/
mv gauls_dashboard_enhanced.py src/interfaces/

# Utils
mv ensure_db_consistency.py src/utils/
mv fix_message_pipeline.py src/utils/
mv store_all_gauls_messages.py src/utils/
mv get_real_gauls_messages.py src/utils/
mv gauls_memory_system.py src/utils/
mv gauls_llm_analyzer.py src/utils/
mv verify_listener.py src/utils/

# Tests
mv test_*.py tests/
mv run_all_tests.py tests/

# Create __init__ files
touch src/__init__.py
touch src/core/__init__.py
touch src/parsers/__init__.py
touch src/processors/__init__.py
touch src/monitors/__init__.py
touch src/executors/__init__.py
touch src/interfaces/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py

echo "✅ Reorganization complete!"