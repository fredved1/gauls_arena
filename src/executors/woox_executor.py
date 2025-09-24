
import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')

import logging
import ccxt
import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from decimal import Decimal
from core.config import WooXConfig, TradingConfig
from signal_parser import TradingSignal, OrderSide, OrderType

logger = logging.getLogger(__name__)

@dataclass
class TradeResult:
    success: bool
    order_id: Optional[str] = None
    message: str = ""
    order_data: Optional[Dict[str, Any]] = None
    
@dataclass
class PositionInfo:
    symbol: str
    side: str
    size: float
    entry_price: float
    unrealized_pnl: float
    margin: float

class WooXExecutor:
    def __init__(self, config: WooXConfig, trading_config: TradingConfig):
        self.config = config
        self.trading_config = trading_config
        
        exchange_config = {
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True
            }
        }
        
        if config.testnet:
            exchange_config['hostname'] = 'api.woo.network'
            exchange_config['urls'] = {
                'api': {
                    'public': 'https://api.staging.woo.network/v1',
                    'private': 'https://api.staging.woo.network/v1'
                }
            }
            
        self.exchange = ccxt.woo(exchange_config)
        
    async def initialize(self):
        """Initialize exchange and load markets"""
        try:
            self.exchange.load_markets()
            logger.info(f"WooX initialized with {len(self.exchange.markets)} markets")
            
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            logger.info(f"Account USDT balance: {usdt_balance}")
            
        except Exception as e:
            logger.error(f"Failed to initialize WooX: {e}")
            raise
            
    async def execute_signal(self, signal: TradingSignal) -> TradeResult:
        """Execute a trading signal"""
        try:
            if signal.symbol not in self.exchange.markets:
                return TradeResult(
                    success=False,
                    message=f"Symbol {signal.symbol} not found on WooX"
                )
                
            market = self.exchange.markets[signal.symbol]
            
            quantity = await self._calculate_position_size(signal, market)
            if quantity <= 0:
                return TradeResult(
                    success=False,
                    message="Invalid position size calculated"
                )
                
            if signal.leverage and market['type'] == 'swap':
                await self._set_leverage(signal.symbol, signal.leverage)
                
            order_params = self._prepare_order_params(signal, market)
            
            side = 'buy' if signal.side in [OrderSide.BUY, OrderSide.LONG] else 'sell'
            
            # CONSERVATIVE LIMIT ORDER LOGIC for "CMP down to $X" signals
            if hasattr(signal, 'original_target') and signal.original_target:
                return await self._execute_conservative_limit_order(signal, side, quantity, order_params)
            elif signal.order_type == OrderType.MARKET:
                # Try maker order first to save fees (0.03% vs 0.05%)
                try:
                    # Use order book instead of ticker (WooX doesn't support fetch_ticker)
                    order_book = self.exchange.fetch_order_book(signal.symbol)
                    if side == 'buy':
                        # Place limit buy slightly below current bid price
                        maker_price = order_book['bids'][0][0] * 0.9999
                    else:
                        # Place limit sell slightly above current ask price
                        maker_price = order_book['asks'][0][0] * 1.0001
                    
                    order = self.exchange.create_limit_order(
                        signal.symbol,
                        side,
                        quantity,
                        maker_price,
                        params={**order_params, 'postOnly': True}
                    )
                    logger.info(f"Maker order placed at {maker_price:.2f} to save fees")
                except:
                    # Fall back to market order if maker fails
                    order = self.exchange.create_market_order(
                        signal.symbol,
                        side,
                        quantity,
                        params=order_params
                    )
            else:
                order = self.exchange.create_limit_order(
                    signal.symbol,
                    side,
                    quantity,
                    signal.entry_price,
                    params=order_params
                )
                
            logger.info(f"Order placed: {order['id']} - {side} {quantity} {signal.symbol}")
            
            # NO EXCHANGE STOP LOSS - Using mental stops to prevent hunting
            # Stop losses are handled by mental stop system (invisible to market makers)
                
            if signal.take_profits:
                await self._place_take_profits(signal, quantity, market)
                
            return TradeResult(
                success=True,
                order_id=order['id'],
                message=f"Order executed: {side} {quantity} {signal.symbol}",
                order_data=order
            )
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            return TradeResult(
                success=False,
                message=f"Trade execution failed: {str(e)}"
            )
            
    async def _calculate_position_size(self, signal: TradingSignal, market: Dict) -> float:
        """Calculate position size based on fixed €50 max loss and stop loss distance"""
        try:
            # Get real-time account balance
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            total_balance = balance.get('USDT', {}).get('total', 0)
            
            logger.info(f"Real-time account balance: Free=${usdt_balance:.2f}, Total=${total_balance:.2f}")
            
            if usdt_balance <= 0:
                logger.error("Insufficient USDT balance for trading")
                return 0
            
            # If signal specifies exact quantity, use it
            if signal.quantity:
                logger.info(f"Using signal-specified quantity: {signal.quantity}")
                return signal.quantity
            
            # FIXED LOSS CALCULATION: Position size based on €50 max loss and stop loss distance
            if not signal.stop_loss:
                logger.error("No stop loss specified - cannot calculate fixed loss position size")
                return 0
                
            # Get current price
            if signal.entry_price:
                current_price = signal.entry_price
                logger.info(f"Using signal entry price: ${current_price}")
            else:
                # Use order book instead of ticker (WooX doesn't support fetch_ticker)
                order_book = self.exchange.fetch_order_book(signal.symbol)
                current_price = (order_book['bids'][0][0] + order_book['asks'][0][0]) / 2
                logger.info(f"Using current market price: ${current_price}")
            
            # Calculate stop loss distance
            sl_distance = abs(current_price - signal.stop_loss)
            sl_percent = (sl_distance / current_price) * 100
            
            logger.info(f"Stop loss distance: ${sl_distance:.4f} ({sl_percent:.2f}%)")
            
            # Calculate position value for fixed €50 max loss
            # Formula: Position Value = Max Loss / (SL Distance % / 100)
            max_loss = self.trading_config.max_loss_euro
            position_value = max_loss / (sl_percent / 100)
            
            logger.info(f"Fixed loss calculation: €{max_loss} max loss = €{position_value:.2f} position value")
            
            # Apply safety cap
            if position_value > self.trading_config.max_position_size:
                logger.warning(f"Position value €{position_value:.2f} exceeds safety cap €{self.trading_config.max_position_size}, capping")
                position_value = self.trading_config.max_position_size
            
            # Calculate account impact with leverage
            account_impact = position_value / self.trading_config.default_leverage
            account_impact_percent = (account_impact / usdt_balance) * 100
            
            logger.info(f"Account impact: €{account_impact:.2f} ({account_impact_percent:.1f}% of balance with {self.trading_config.default_leverage}x leverage)")
            
            # Check if we have enough balance
            if account_impact > usdt_balance:
                logger.error(f"Required margin €{account_impact:.2f} exceeds available balance €{usdt_balance:.2f}")
                return 0
            
            # Calculate quantity
            quantity = position_value / current_price
            
            # Apply market constraints
            min_qty = market.get('limits', {}).get('amount', {}).get('min', 0)
            max_qty = market.get('limits', {}).get('amount', {}).get('max', float('inf'))
            precision = market.get('precision', {}).get('amount', 8)
            
            quantity = round(quantity, precision)
            
            # Validate quantity
            if quantity < min_qty:
                logger.error(f"Calculated quantity {quantity} below minimum {min_qty}")
                return 0
                
            if quantity > max_qty:
                logger.warning(f"Calculated quantity {quantity} above maximum {max_qty}, capping")
                quantity = max_qty
            
            # Final verification - calculate actual max loss
            actual_max_loss = quantity * sl_distance
            
            logger.info(f"Final position:")
            logger.info(f"  Quantity: {quantity} {signal.symbol.split('/')[0]}")
            logger.info(f"  Position Value: €{position_value:.2f}")
            logger.info(f"  Account Impact: €{account_impact:.2f} ({account_impact_percent:.1f}%)")
            logger.info(f"  Max Loss at SL: €{actual_max_loss:.2f}")
                
            return quantity
            
        except Exception as e:
            logger.error(f"Failed to calculate position size: {e}")
            return 0
            
    async def _set_leverage(self, symbol: str, leverage: int):
        """Set leverage for futures trading"""
        try:
            self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            logger.warning(f"Failed to set leverage: {e}")
            
    def _prepare_order_params(self, signal: TradingSignal, market: Dict) -> Dict:
        """Prepare additional order parameters"""
        params = {}
        
        if market['type'] == 'swap':
            params['positionSide'] = 'LONG' if signal.side in [OrderSide.BUY, OrderSide.LONG] else 'SHORT'
            
        if signal.side in [OrderSide.LONG, OrderSide.SHORT]:
            params['reduceOnly'] = False
            
        return params
        
    # REMOVED: Exchange stop loss function - using mental stops instead
    # This prevents stop hunting by market makers
            
    async def _place_take_profits(self, signal: TradingSignal, quantity: float, market: Dict):
        """Place take profit orders"""
        try:
            side = 'sell' if signal.side in [OrderSide.BUY, OrderSide.LONG] else 'buy'
            
            tp_quantity = quantity / len(signal.take_profits)
            
            for i, tp_price in enumerate(signal.take_profits):
                qty = tp_quantity if i < len(signal.take_profits) - 1 else quantity - (tp_quantity * i)
                
                order = self.exchange.create_limit_order(
                    signal.symbol,
                    side,
                    qty,
                    tp_price,
                    params={'reduceOnly': True}
                )
                
                logger.info(f"Take profit {i+1} placed at {tp_price} for {signal.symbol}")
                
        except Exception as e:
            logger.error(f"Failed to place take profits: {e}")
            
    async def get_positions(self) -> List[PositionInfo]:
        """Get current open positions"""
        try:
            positions = self.exchange.fetch_positions()
            
            position_list = []
            for pos in positions:
                if pos['contracts'] > 0:
                    position_list.append(PositionInfo(
                        symbol=pos['symbol'],
                        side=pos['side'],
                        size=pos['contracts'],
                        entry_price=pos['markPrice'],
                        unrealized_pnl=pos['unrealizedPnl'] or 0,
                        margin=pos['initialMargin'] or 0
                    ))
                    
            return position_list
            
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []
            
    async def cancel_all_orders(self, symbol: Optional[str] = None):
        """Cancel all open orders"""
        try:
            if symbol:
                self.exchange.cancel_all_orders(symbol)
                logger.info(f"All orders cancelled for {symbol}")
            else:
                for market_symbol in self.exchange.markets:
                    try:
                        self.exchange.cancel_all_orders(market_symbol)
                    except:
                        pass
                logger.info("All orders cancelled")
                
        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")
    
    async def _execute_conservative_limit_order(self, signal, side: str, quantity: float, order_params: dict) -> TradeResult:
        """Execute conservative limit order with timeout and price monitoring"""
        try:
            # Configuration
            CONSERVATIVE_TIMEOUT = 30 * 60  # 30 minutes
            MAX_PRICE_DRIFT_PCT = 2.0  # 2% max drift from original target
            
            # Get current market price
            order_book = self.exchange.fetch_order_book(signal.symbol)
            current_price = (order_book['bids'][0][0] + order_book['asks'][0][0]) / 2
            
            # Calculate max acceptable drift
            max_price_drift = signal.original_target * (MAX_PRICE_DRIFT_PCT / 100)
            
            logger.info(f"🎯 Conservative limit order setup:")
            logger.info(f"   Original target: ${signal.original_target:.3f}")
            logger.info(f"   Conservative limit: ${signal.entry_price:.3f} (+0.63% buffer)")
            logger.info(f"   Current price: ${current_price:.3f}")
            logger.info(f"   Max drift allowed: ±${max_price_drift:.3f}")
            
            # Check if price has drifted too far from original target
            price_drift = abs(current_price - signal.original_target)
            if price_drift > max_price_drift:
                logger.warning(f"❌ Price drift too large: ${price_drift:.3f} > ${max_price_drift:.3f}")
                return TradeResult(
                    success=False,
                    message=f"Price drift: ${price_drift:.3f} exceeds max ${max_price_drift:.3f}"
                )
            
            # Check if current price is suitable for conservative limit order
            if side == 'buy':
                if current_price <= signal.entry_price:
                    logger.warning(f"❌ Current price ${current_price:.3f} too low for buy limit ${signal.entry_price:.3f}")
                    return TradeResult(
                        success=False,
                        message=f"Price too low for conservative buy limit"
                    )
            else:  # sell
                if current_price >= signal.entry_price:
                    logger.warning(f"❌ Current price ${current_price:.3f} too high for sell limit ${signal.entry_price:.3f}")
                    return TradeResult(
                        success=False,
                        message=f"Price too high for conservative sell limit"
                    )
            
            # Place conservative limit order
            logger.info(f"📍 Placing conservative {side} limit order at ${signal.entry_price:.3f}")
            order = self.exchange.create_limit_order(
                signal.symbol,
                side,
                quantity,
                signal.entry_price,
                params=order_params
            )
            
            logger.info(f"✅ Conservative limit order placed: {order['id']}")
            logger.info(f"   Will monitor for {CONSERVATIVE_TIMEOUT/60:.0f} minutes")
            
            return TradeResult(
                success=True,
                order_id=order['id'],
                message=f"Conservative limit order placed at ${signal.entry_price:.3f}",
                order_data=order
            )
            
        except Exception as e:
            logger.error(f"❌ Conservative limit order failed: {e}")
            return TradeResult(
                success=False,
                message=f"Conservative limit order failed: {str(e)}"
            )