#!/usr/bin/env python3
"""
Gauls Signal Parser - Parses trading signals from Gauls' Telegram messages
Handles various signal formats including with/without $ prefix
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class GaulsSignalParser:
    """Parse REAL Gauls trading signals from Telegram"""
    
    def __init__(self):
        # Real Gauls signal patterns (based on actual messages)
        # IMPORTANT: $ is optional to handle both "$BTC" and "BTC" formats
        self.patterns = {
            'symbol': re.compile(r'\$?([A-Z]{2,10})\s*.*(?:Setup|buying|Buying)', re.IGNORECASE),
            'entry_price': re.compile(r'(?:Entry|ENTRY)\s*:\s*\$?([0-9]+\.?[0-9]*|CMP)(?:\s+down\s+to\s+\$?([0-9]+\.?[0-9]*))?', re.IGNORECASE),
            'entry_hint': re.compile(r'(?:Entry|ENTRY)\s*:\s*\$?[0-9]+\.?[0-9]*\s*\(([^)]+)\)', re.IGNORECASE),
            'take_profit': re.compile(r'(?:TP|Target|TARGET)\s*:\s*\$?([0-9]+\.?[0-9]*)(x?)', re.IGNORECASE),
            'stop_loss': re.compile(r'(?:SL|Invalidation)\s*:\s*\$?([0-9]+\.?[0-9]*)', re.IGNORECASE),
            'risk_reward': re.compile(r'RR\s*:\s*([0-9]+\.?[0-9]*)', re.IGNORECASE),
            'buying_setup': re.compile(r'buying\s+setup|Buying\s+Setup', re.IGNORECASE),
        }
    
    def parse_signal(self, text: str) -> Optional[Dict]:
        """Parse a REAL Gauls trading signal from Telegram"""
        try:
            # Check if this is a buying setup (Gauls' format)
            if not self.patterns['buying_setup'].search(text):
                return None
            
            # Extract symbol
            symbol_match = self.patterns['symbol'].search(text)
            if not symbol_match:
                return None
            
            symbol = symbol_match.group(1)
            
            # Parse components (all Gauls setups are LONG positions)
            signal = {
                'symbol': f"{symbol}/USDT",
                'side': 'buy',  # All Gauls "buying setups" are longs
                'entry_price': None,
                'entry_type': 'market',
                'entry_hint': None,
                'stop_loss': None,
                'take_profit': None,
                'risk_reward': None,
                'conviction': 'high',  # Gauls signals are high conviction
                'raw_text': text,
                'source': 'gauls_copy'
            }
            
            # Extract entry price
            entry_match = self.patterns['entry_price'].search(text)
            if entry_match:
                entry_str = entry_match.group(1)
                secondary_price = entry_match.group(2) if len(entry_match.groups()) > 1 else None
                
                if entry_str.upper() == 'CMP':
                    if secondary_price:  # "CMP down to $1.431" format - CONSERVATIVE LIMIT ORDER
                        target_price = float(secondary_price)
                        # Apply 0.63% conservative buffer (1.431 → 1.44 example)
                        conservative_buffer = 0.0063  # 0.63%
                        conservative_price = target_price * (1 + conservative_buffer)
                        
                        signal['entry_type'] = 'limit'
                        signal['entry_price'] = conservative_price
                        signal['entry_hint'] = f'Conservative limit @ ${conservative_price:.3f} (target: ${target_price})'
                        signal['original_target'] = target_price
                        logger.info(f"📍 Conservative limit order: ${target_price} → ${conservative_price:.3f} (+{conservative_buffer*100:.2f}% buffer)")
                    else:  # Just "CMP" - immediate market order
                        signal['entry_type'] = 'market'
                else:
                    signal['entry_price'] = float(entry_str)
                    signal['entry_type'] = 'limit'
            
            # Extract entry hint (e.g., "A bit above", "A bit below")
            hint_match = self.patterns['entry_hint'].search(text)
            if hint_match:
                signal['entry_hint'] = hint_match.group(1).strip()
            
            # Extract stop loss
            sl_match = self.patterns['stop_loss'].search(text)
            if sl_match:
                signal['stop_loss'] = float(sl_match.group(1))
            
            # Extract take profit
            tp_match = self.patterns['take_profit'].search(text)
            if tp_match:
                value = float(tp_match.group(1))
                is_multiplier = tp_match.group(2) == 'x'  # Check if second group has 'x'
                
                if is_multiplier:  # Multiplier target like "2x"
                    if signal['entry_price'] and isinstance(signal['entry_price'], (int, float)):
                        signal['take_profit'] = signal['entry_price'] * value
                    else:
                        # Use middle of entry range for calculation if available
                        entry_range_match = re.search(r'Entry:\s*([0-9]+\.?[0-9]*)-([0-9]+\.?[0-9]*)', text)
                        if entry_range_match:
                            entry_low = float(entry_range_match.group(1))
                            entry_high = float(entry_range_match.group(2))
                            entry_mid = (entry_low + entry_high) / 2
                            signal['take_profit'] = entry_mid * value
                            signal['entry_price'] = entry_mid  # Update entry to use mid-range
                        else:
                            signal['take_profit'] = value  # Store multiplier as take profit for now
                        signal['risk_reward'] = value
                else:  # Direct price target
                    signal['take_profit'] = value
            
            # Extract risk/reward ratio
            rr_match = self.patterns['risk_reward'].search(text)
            if rr_match:
                signal['risk_reward'] = float(rr_match.group(1))
            
            # Validate signal has minimum required info
            if signal['symbol'] and signal['stop_loss'] and signal['take_profit']:
                logger.info(f"📊 Parsed REAL Gauls signal: {signal['symbol']} LONG Entry:{entry_str if entry_match else 'CMP'} TP:{signal['take_profit']} SL:{signal['stop_loss']}")
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing real Gauls signal: {e}")
            return None