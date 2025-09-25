#!/usr/bin/env python3
"""
Unified Exchange Interface
Maintains the same interface for both Mock and WooX exchanges
Keeps compatibility with existing code
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import os
import logging
import ccxt
# from mock_exchange import MockExchange  # Removed - not needed
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class UnifiedExchange:
    """Wrapper that provides the same interface for both mock and real trading"""
    
    def __init__(self):
        # ALWAYS PRODUCTION FOR GAULS - NO PAPER TRADING!
        self.mode = 'production'  # Force production - Gauls is REAL money only
        
        if self.mode == 'production':
            # Initialize WooX exchange
            logger.warning("="*60)
            logger.warning("🚨 PRODUCTION MODE - REAL MONEY TRADING")
            logger.warning("="*60)
            
            api_key = os.getenv('WOOX_API_KEY')
            api_secret = os.getenv('WOOX_API_SECRET')
            
            if not api_key or not api_secret:
                logger.error("❌ WooX credentials not found in PRODUCTION mode!")
                raise ValueError("Cannot run in production mode without WooX API credentials")
            else:
                # Initialize real WooX exchange
                config = {
                    'apiKey': api_key,
                    'secret': api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'swap',  # Use perpetuals for leverage trading
                        'adjustForTimeDifference': True
                    }
                }
                
                # Check if testnet
                if os.getenv('WOOX_TESTNET', 'false').lower() == 'true':
                    config['hostname'] = 'api.staging.woo.network'
                    config['urls'] = {
                        'api': {
                            'public': 'https://api.staging.woo.network/v1',
                            'private': 'https://api.staging.woo.network/v1'
                        }
                    }
                    logger.info("🧪 Using WooX TESTNET")
                
                self.real_exchange = ccxt.woo(config)
                self.real_exchange.load_markets()
                
                # Log balance
                balance = self.real_exchange.fetch_balance()
                usdt_free = balance.get('USDT', {}).get('free', 0)
                usdt_total = balance.get('USDT', {}).get('total', 0)
                logger.info(f"💰 WooX PRODUCTION Balance: ${usdt_total:.2f} USDT (Free: ${usdt_free:.2f})")
                logger.info(f"✅ Successfully connected to WooX in PRODUCTION mode - REAL MONEY")
                
                # Production mode - no mock exchange
                self.exchange = None
                
        else:
            # NO MOCK MODE - GAULS IS PRODUCTION ONLY!
            logger.error("❌ Gauls Copy Trading is PRODUCTION ONLY!")
            raise Exception("Gauls system runs in production mode only - no paper trading!")
            self.real_exchange = None
    
    def fetch_ticker(self, symbol: str) -> Dict:
        """Fetch ticker - works for both modes"""
        if self.mode == 'production' and self.real_exchange:
            try:
                # Convert to perpetual symbol for WooX
                perp_symbol = self._convert_to_perp_symbol(symbol)
                # WooX doesn't support fetch_ticker, use order book
                order_book = self.real_exchange.fetch_order_book(perp_symbol)
                mid_price = (order_book['bids'][0][0] + order_book['asks'][0][0]) / 2 if order_book['bids'] and order_book['asks'] else 0
                return {
                    'symbol': symbol,
                    'last': mid_price,
                    'bid': order_book['bids'][0][0] if order_book['bids'] else 0,
                    'ask': order_book['asks'][0][0] if order_book['asks'] else 0,
                    'high': mid_price * 1.05,
                    'low': mid_price * 0.95,
                    'volume': 0
                }
            except Exception as e:
                logger.error(f"Error fetching ticker from WooX: {e}")
                raise Exception(f"WooX ticker fetch failed for {symbol}: {e}")
        else:
            return self.exchange.fetch_ticker(symbol)
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> list:
        """Fetch OHLCV data based on mode"""
        if self.mode == 'production' and self.real_exchange:
            try:
                perp_symbol = self._convert_to_perp_symbol(symbol)
                return self.real_exchange.fetch_ohlcv(perp_symbol, timeframe, limit=limit)
            except Exception as e:
                logger.error(f"Error fetching OHLCV from WooX: {e}")
                raise Exception(f"WooX OHLCV fetch failed for {symbol}: {e}")
        else:
            return self.exchange.fetch_ohlcv(symbol, timeframe, limit)
    
    def _convert_to_perp_symbol(self, symbol: str) -> str:
        """Convert spot symbol to perpetual format for WooX"""
        # Convert BTC/USDT -> BTC/USDT:USDT for perpetuals
        if '/' in symbol and ':' not in symbol:
            return f"{symbol}:USDT"
        return symbol
    
    def create_market_order(self, symbol: str, type: str, side: str, amount: float) -> Dict:
        """Create a market order - wrapper for compatibility with exit monitor"""
        return self.create_order(symbol, 'market', side, amount)
    
    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: Optional[float] = None, leverage: Optional[int] = None) -> Dict:
        """Create order - works for both modes with leverage support"""
        
        if self.mode == 'production' and self.real_exchange:
            try:
                logger.info(f"🔴 REAL ORDER: {side} {amount:.6f} {symbol} (Leverage: {leverage or 1}x)")
                
                # Safety check - but allow higher limits for Gauls trades
                max_position = float(os.getenv('MAX_POSITION_SIZE', 1000))
                ticker = self.fetch_ticker(symbol)
                position_value = amount * ticker['last']
                
                # Only apply limit if it's extremely high (safety net) - Allow proper Gauls sizing
                safety_limit = 1000  # Hard safety limit
                if position_value > safety_limit:
                    logger.warning(f"⚠️ Position ${position_value:.2f} exceeds safety limit ${safety_limit}, capping")
                    amount = safety_limit / ticker['last']
                else:
                    logger.info(f"✅ Position ${position_value:.2f} within limits")
                
                # Convert to perpetual symbol for WooX
                perp_symbol = self._convert_to_perp_symbol(symbol)
                logger.info(f"📊 Using perpetual contract: {perp_symbol}")
                
                # Set leverage for this position if specified
                if leverage and leverage > 1:
                    try:
                        # WooX requires leverage as integer
                        leverage_int = int(leverage)
                        self.real_exchange.set_leverage(leverage_int, perp_symbol)
                        logger.info(f"⚙️ Leverage set to {leverage_int}x for {perp_symbol}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to set leverage: {e}, using account default")
                
                # Place real order on WooX perpetuals
                if order_type == 'market':
                    order = self.real_exchange.create_market_order(perp_symbol, side, amount)
                else:
                    order = self.real_exchange.create_limit_order(perp_symbol, side, amount, price)
                
                logger.info(f"✅ Real order executed: {order['id']}")
                
                # Return the real order info
                return {
                    'id': order['id'],
                    'symbol': symbol,
                    'type': order_type,
                    'side': side,
                    'amount': amount,
                    'price': order.get('price', ticker['last']),
                    'filled': amount,
                    'remaining': 0,
                    'status': 'closed',
                    'timestamp': order.get('timestamp')
                }
                
            except Exception as e:
                logger.error(f"❌ Real order failed: {e}")
                # Don't fall back - just return failure
                return {
                    'id': None,
                    'symbol': symbol,
                    'type': order_type,
                    'side': side,
                    'amount': amount,
                    'price': 0,
                    'filled': 0,
                    'remaining': amount,
                    'status': 'failed',
                    'error': str(e)
                }
        else:
            # Mock mode
            return self.exchange.create_order(symbol, order_type, side, amount, price)
    
    def fetch_balance(self) -> Dict:
        """Fetch balance"""
        if self.mode == 'production' and self.real_exchange:
            try:
                return self.real_exchange.fetch_balance()
            except Exception as e:
                logger.error(f"Error fetching balance: {e}")
                return self.exchange.fetch_balance()
        else:
            return self.exchange.fetch_balance()
    
    def get_positions(self) -> list:
        """Get positions"""
        if self.mode == 'production' and self.real_exchange:
            try:
                positions = self.real_exchange.fetch_positions()
                formatted = []
                for pos in positions:
                    if pos.get('contracts', 0) > 0:
                        formatted.append({
                            'symbol': pos['symbol'],
                            'side': pos.get('side', 'long'),
                            'amount': pos.get('contracts', 0),
                            'entry_price': pos.get('markPrice', 0),
                            'current_price': pos.get('markPrice', 0),
                            'pnl': pos.get('unrealizedPnl', 0),
                            'id': pos.get('id', pos['symbol'])
                        })
                return formatted
            except Exception as e:
                logger.error(f"Error fetching positions: {e}")
                return []
        else:
            # Mock mode
            return self.exchange.get_positions() if self.exchange else []
    
    def close_position(self, position_id: str) -> bool:
        """Close position"""
        if self.mode == 'production' and self.real_exchange:
            # In production, we need to place a counter order
            # But for now, just track locally
            logger.info(f"📝 Position close tracked locally: {position_id}")
        
        return self.exchange.close_position(position_id)
    
    # Compatibility methods for existing code
    def get_balance(self) -> float:
        """Get USDT balance - for backward compatibility"""
        if self.mode == 'production' and self.real_exchange:
            try:
                balance = self.real_exchange.fetch_balance()
                return balance.get('USDT', {}).get('free', 0)
            except Exception as e:
                logger.error(f"Error fetching balance: {e}")
                return 0
        else:
            # Mock mode
            return self.exchange.balance['USDT']['free'] if self.exchange else 0
    
    def get_ticker(self, symbol: str) -> Dict:
        """Alias for fetch_ticker - backward compatibility"""
        return self.fetch_ticker(symbol)