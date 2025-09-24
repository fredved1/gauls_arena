#!/usr/bin/env python3
"""
Execute the SEI trade on WooX with correct position sizing
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import ccxt
import os
from dotenv import load_dotenv

load_dotenv('/gauls-copy-trading-system/.env')

print("🚨 PLACING SEI TRADE ON WOOX - REAL MONEY")
print("="*50)

# Trade parameters from Gauls signal
SYMBOL = 'SEI/USDT:USDT'  # Perpetual format for WooX
ENTRY_PRICE = 0.29255
STOP_LOSS = 0.26
TAKE_PROFIT = 0.43
MAX_LOSS_EUR = 25.0
LEVERAGE = 10

# Calculate position size
risk_per_unit = abs(ENTRY_PRICE - STOP_LOSS)
quantity = MAX_LOSS_EUR / risk_per_unit
position_value = quantity * ENTRY_PRICE
margin_required = position_value / LEVERAGE

print(f"Symbol: {SYMBOL}")
print(f"Entry: ${ENTRY_PRICE}")
print(f"Stop Loss: ${STOP_LOSS}")
print(f"Take Profit: ${TAKE_PROFIT}")
print(f"Risk per unit: ${risk_per_unit:.5f}")
print(f"Quantity: {quantity:.2f} SEI")
print(f"Position Value: ${position_value:.2f}")
print(f"Leverage: {LEVERAGE}x")
print(f"Margin Required: ${margin_required:.2f}")
print("")

# Initialize WooX
woox = ccxt.woo({
    'apiKey': os.getenv('WOOX_API_KEY'),
    'secret': os.getenv('WOOX_API_SECRET'),
    'options': {
        'defaultType': 'swap',
        'adjustForTimeDifference': True
    },
    'enableRateLimit': True
})

woox.load_markets()

# Check balance
balance = woox.fetch_balance()
usdt_balance = balance.get('USDT', {}).get('free', 0)
print(f"Available Balance: ${usdt_balance:.2f}")

if usdt_balance < margin_required:
    print(f"❌ Insufficient balance! Need ${margin_required:.2f}, have ${usdt_balance:.2f}")
else:
    # Set leverage
    try:
        woox.set_leverage(LEVERAGE, SYMBOL)
        print(f"✅ Set leverage to {LEVERAGE}x")
    except Exception as e:
        print(f"⚠️ Could not set leverage: {e}")
    
    # Place the order
    print(f"\n🚀 PLACING MARKET BUY ORDER...")
    try:
        order = woox.create_order(
            symbol=SYMBOL,
            type='market',
            side='buy',
            amount=round(quantity, 2)  # Round to 2 decimals for SEI
        )
        print(f"✅ Order placed successfully!")
        print(f"Order ID: {order['id']}")
        print(f"Status: {order['status']}")
        print(f"Filled: {order.get('filled', 0)} SEI")
        print(f"Average Price: ${order.get('average', ENTRY_PRICE)}")
    except Exception as e:
        print(f"❌ Order failed: {e}")
