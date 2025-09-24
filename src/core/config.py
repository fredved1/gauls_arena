
import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TelegramConfig:
    api_id: int
    api_hash: str
    phone: str
    channel_id: str
    notification_chat_id: Optional[int]
    session_name: str = "trading_session"

@dataclass
class WooXConfig:
    api_key: str
    api_secret: str
    testnet: bool = False

@dataclass
class TradingConfig:
    auto_trade: bool
    max_position_size: float
    max_loss_euro: float = 50.0
    default_leverage: int = 10
    confirmation_timeout: int = 60
    phoenix_risk_per_trade: float = 0.02  # Phoenix: 2% risk per trade
    phoenix_capital: float = 1000.0  # Phoenix: Starting capital
    use_mental_stops: bool = True  # Phoenix: Use mental stops

@dataclass
class MultiStrategyConfig:
    """Phoenix multi-strategy configuration"""
    enabled: bool = True  # Phoenix always multi-strategy
    phoenix_ma_weight: float = 0.4      # 40% MA crossover strategy
    phoenix_rsi_weight: float = 0.3     # 30% RSI extreme strategy
    phoenix_breakout_weight: float = 0.3  # 30% Volume breakout strategy
    max_strategies_concurrent: int = 3  # Phoenix runs 3 strategies
    conflict_detection: bool = True     # Detect conflicting signals

@dataclass
class Config:
    telegram: TelegramConfig
    woox: WooXConfig
    trading: TradingConfig
    multi_strategy: MultiStrategyConfig
    openai_api_key: Optional[str]
    twelve_data_api_key: str = "c29b522533ab4a41b313483b349246d1"
    
    @classmethod
    def from_env(cls) -> 'Config':
        telegram = TelegramConfig(
            api_id=int(os.getenv('TELEGRAM_API_ID', '0')),
            api_hash=os.getenv('TELEGRAM_API_HASH', ''),
            phone=os.getenv('TELEGRAM_PHONE', ''),
            channel_id=os.getenv('TELEGRAM_CHANNEL_ID', ''),
            notification_chat_id=int(os.getenv('TELEGRAM_NOTIFICATION_CHAT_ID', '0')) if os.getenv('TELEGRAM_NOTIFICATION_CHAT_ID') else None
        )
        
        woox = WooXConfig(
            api_key=os.getenv('WOOX_API_KEY', ''),
            api_secret=os.getenv('WOOX_API_SECRET', ''),
            testnet=os.getenv('WOOX_TESTNET', 'false').lower() == 'true'
        )
        
        trading = TradingConfig(
            auto_trade=os.getenv('AUTO_TRADE', 'false').lower() == 'true',
            max_position_size=float(os.getenv('MAX_POSITION_SIZE', '1000')),
            max_loss_euro=float(os.getenv('MAX_LOSS_EURO', '50.0')),
            default_leverage=int(os.getenv('DEFAULT_LEVERAGE', '10')),
            phoenix_risk_per_trade=float(os.getenv('PHOENIX_RISK_PER_TRADE', '0.02')),
            phoenix_capital=float(os.getenv('PHOENIX_CAPITAL', '1000.0')),
            use_mental_stops=os.getenv('USE_MENTAL_STOPS', 'true').lower() == 'true'
        )
        
        multi_strategy = MultiStrategyConfig(
            enabled=os.getenv('ENABLE_PHOENIX_STRATEGIES', 'true').lower() == 'true',
            phoenix_ma_weight=float(os.getenv('PHOENIX_MA_WEIGHT', '0.4')),
            phoenix_rsi_weight=float(os.getenv('PHOENIX_RSI_WEIGHT', '0.3')),
            phoenix_breakout_weight=float(os.getenv('PHOENIX_BREAKOUT_WEIGHT', '0.3')),
            max_strategies_concurrent=int(os.getenv('MAX_STRATEGIES_CONCURRENT', '3')),
            conflict_detection=os.getenv('CONFLICT_DETECTION', 'true').lower() == 'true'
        )

        return cls(
            telegram=telegram,
            woox=woox,
            trading=trading,
            multi_strategy=multi_strategy,
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            twelve_data_api_key=os.getenv('TWELVE_DATA_API_KEY', 'c29b522533ab4a41b313483b349246d1')
        )
    
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.telegram.api_id or not self.telegram.api_hash:
            raise ValueError("Telegram API credentials missing")
        if not self.telegram.channel_id:
            raise ValueError("Telegram channel ID missing")
        if not self.woox.api_key or not self.woox.api_secret:
            raise ValueError("WooX API credentials missing")
        return True