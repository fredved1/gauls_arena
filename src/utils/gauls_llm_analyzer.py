#!/usr/bin/env python3
"""
🤖 Gauls LLM Analyzer - AI Enhancement for Signal Analysis
Analyzes Gauls messages for context, sentiment, and signal quality
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import logging
import json
from datetime import datetime
from typing import Dict, List, Optional

try:
    import openai
except ImportError:
    openai = None
import sqlite3
import os

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file"""
    env_path = '/opt/sage-trading-system/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value

load_env_file()

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger("GAULS_LLM")

class GaulsLLMAnalyzer:
    """LLM-powered analysis of Gauls trading signals"""
    
    def __init__(self, openai_key: Optional[str] = None):
        self.openai_key = openai_key or os.getenv('OPENAI_API_KEY')
        self.client = None
        
        if self.openai_key and OPENAI_AVAILABLE:
            try:
                self.client = openai.OpenAI(api_key=self.openai_key)
                logger.info("🤖 LLM Analyzer initialized")
            except Exception as e:
                logger.error(f"OpenAI initialization failed: {e}")
        else:
            logger.warning("⚠️ LLM Analyzer running without OpenAI (pattern-based fallback)")
    
    def analyze_signal_quality(self, signal: Dict, original_message: str) -> Dict:
        """Analyze the quality and context of a Gauls signal"""
        
        analysis = {
            'signal_confidence': 'medium',
            'risk_assessment': 'moderate',
            'market_context': 'neutral',
            'execution_recommendation': 'proceed',
            'reasoning': [],
            'warnings': [],
            'enhancements': []
        }
        
        if self.client:
            # Use LLM for deep analysis
            analysis = self._llm_analyze_signal(signal, original_message)
        else:
            # Fallback to pattern-based analysis
            analysis = self._pattern_analyze_signal(signal, original_message)
        
        return analysis
    
    def _llm_analyze_signal(self, signal: Dict, message: str) -> Dict:
        """Use LLM to analyze Gauls trading signal"""
        try:
            prompt = f"""
            Analyze this Gauls trading signal for quality and context:
            
            SIGNAL:
            Symbol: {signal['symbol']}
            Entry: {signal.get('entry_price', 'CMP')}
            Take Profit: {signal.get('take_profit')}
            Stop Loss: {signal.get('stop_loss')}
            Risk/Reward: {signal.get('risk_reward', 'N/A')}
            
            ORIGINAL MESSAGE:
            "{message}"
            
            Provide analysis as JSON:
            {{
                "signal_confidence": "low/medium/high/very_high",
                "risk_assessment": "low/moderate/high/very_high", 
                "market_context": "bearish/neutral/bullish/very_bullish",
                "execution_recommendation": "avoid/cautious/proceed/aggressive",
                "reasoning": ["key points supporting the signal"],
                "warnings": ["potential risks or concerns"],
                "enhancements": ["suggestions to improve execution"],
                "gauls_sentiment": "neutral/confident/very_confident",
                "technical_validation": "weak/moderate/strong",
                "position_sizing": "small/medium/large"
            }}
            
            Focus on:
            1. Signal quality indicators in Gauls' language
            2. Risk/reward ratio analysis  
            3. Market timing context
            4. Execution recommendations
            5. Any red flags or concerns
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800
            )
            
            analysis_text = response.choices[0].message.content
            
            # Parse JSON response
            try:
                analysis = json.loads(analysis_text)
                logger.info(f"🤖 LLM analyzed {signal['symbol']} signal: {analysis['signal_confidence']} confidence")
                return analysis
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM response as JSON")
                return self._pattern_analyze_signal(signal, message)
                
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._pattern_analyze_signal(signal, message)
    
    def _pattern_analyze_signal(self, signal: Dict, message: str) -> Dict:
        """Pattern-based fallback analysis"""
        
        analysis = {
            'signal_confidence': 'medium',
            'risk_assessment': 'moderate', 
            'market_context': 'neutral',
            'execution_recommendation': 'proceed',
            'reasoning': [],
            'warnings': [],
            'enhancements': [],
            'gauls_sentiment': 'neutral',
            'technical_validation': 'moderate',
            'position_sizing': 'medium'
        }
        
        message_lower = message.lower()
        
        # Confidence indicators
        if any(word in message_lower for word in ['guarantee', 'certain', 'perfect', 'textbook']):
            analysis['signal_confidence'] = 'very_high'
            analysis['gauls_sentiment'] = 'very_confident'
            analysis['reasoning'].append("Strong conviction language detected")
        elif any(word in message_lower for word in ['good', 'solid', 'clean']):
            analysis['signal_confidence'] = 'high'
            analysis['gauls_sentiment'] = 'confident'
        
        # Risk assessment based on R/R ratio
        rr_ratio = signal.get('risk_reward', 0)
        if rr_ratio and rr_ratio > 3:
            analysis['risk_assessment'] = 'low'
            analysis['reasoning'].append(f"Excellent R/R ratio: {rr_ratio:.1f}")
        elif rr_ratio and rr_ratio > 2:
            analysis['risk_assessment'] = 'moderate'
            analysis['reasoning'].append(f"Good R/R ratio: {rr_ratio:.1f}")
        elif rr_ratio and rr_ratio < 1.5:
            analysis['risk_assessment'] = 'high'
            analysis['warnings'].append(f"Low R/R ratio: {rr_ratio:.1f}")
        
        # Entry type analysis
        if signal.get('entry_type') == 'market':
            analysis['reasoning'].append("Immediate market entry (CMP)")
        else:
            analysis['warnings'].append("Limit order - price may not be reached")
        
        # Position sizing recommendation
        if analysis['signal_confidence'] == 'very_high' and analysis['risk_assessment'] == 'low':
            analysis['position_sizing'] = 'large'
        elif analysis['signal_confidence'] == 'high':
            analysis['position_sizing'] = 'medium'
        else:
            analysis['position_sizing'] = 'small'
        
        return analysis
    
    def validate_against_market_conditions(self, signal: Dict, analysis: Dict) -> Dict:
        """Validate signal against current market conditions"""
        
        enhanced_analysis = analysis.copy()
        
        try:
            # Get current price for comparison
            from mock_exchange import MockExchange
            exchange = MockExchange(1000)
            ticker = exchange.fetch_ticker(signal['symbol'])
            current_price = ticker['last']
            
            # Compare with signal prices
            entry_price = signal.get('entry_price')
            if entry_price:
                price_diff_pct = ((current_price - entry_price) / entry_price) * 100
                
                if abs(price_diff_pct) > 5:
                    enhanced_analysis['warnings'].append(
                        f"Price moved {price_diff_pct:+.1f}% since signal (Entry: {entry_price}, Current: {current_price:.2f})"
                    )
                    if price_diff_pct > 5:  # Price went up significantly
                        enhanced_analysis['execution_recommendation'] = 'cautious'
                        enhanced_analysis['enhancements'].append("Consider waiting for pullback")
                    elif price_diff_pct < -5:  # Price dropped significantly  
                        enhanced_analysis['enhancements'].append("Opportunity to enter at better price")
            
        except Exception as e:
            logger.error(f"Market validation failed: {e}")
        
        return enhanced_analysis
    
    def generate_execution_plan(self, signal: Dict, analysis: Dict) -> Dict:
        """Generate detailed execution plan based on analysis"""
        
        plan = {
            'should_execute': True,
            'position_size_modifier': 1.0,
            'entry_strategy': 'immediate',
            'risk_adjustments': [],
            'monitoring_points': [],
            'exit_modifications': []
        }
        
        # Adjust based on analysis
        if analysis['execution_recommendation'] == 'avoid':
            plan['should_execute'] = False
            plan['reason'] = "Analysis recommends avoiding this signal"
            
        elif analysis['execution_recommendation'] == 'cautious':
            plan['position_size_modifier'] = 0.5
            plan['entry_strategy'] = 'staged'
            plan['risk_adjustments'].append("Reduce position size by 50%")
            
        elif analysis['execution_recommendation'] == 'aggressive':
            plan['position_size_modifier'] = 1.5
            plan['risk_adjustments'].append("Increase position size by 50%")
        
        # Position sizing based on confidence
        if analysis.get('position_sizing') == 'small':
            plan['position_size_modifier'] *= 0.5
        elif analysis.get('position_sizing') == 'large':
            plan['position_size_modifier'] *= 1.5
        
        # Add monitoring points
        if signal.get('stop_loss'):
            plan['monitoring_points'].append(f"Watch for SL breach at {signal['stop_loss']}")
        if signal.get('take_profit'):
            plan['monitoring_points'].append(f"Monitor TP approach at {signal['take_profit']}")
        
        return plan
    
    def analyze_gauls_message_context(self, message: str) -> Dict:
        """Analyze broader context of Gauls message"""
        
        context = {
            'message_type': 'trading_signal',
            'urgency': 'normal',
            'market_phase': 'unknown',
            'strategy_context': [],
            'follow_up_expected': False
        }
        
        message_lower = message.lower()
        
        # Urgency indicators
        if any(word in message_lower for word in ['now', 'immediate', 'asap', 'quickly']):
            context['urgency'] = 'high'
        elif any(word in message_lower for word in ['wait', 'patient', 'later']):
            context['urgency'] = 'low'
        
        # Strategy context
        if 'setup' in message_lower:
            context['strategy_context'].append('technical_setup')
        if any(word in message_lower for word in ['breakout', 'break']):
            context['strategy_context'].append('breakout_play')
        if any(word in message_lower for word in ['bounce', 'support']):
            context['strategy_context'].append('support_bounce')
        
        # Follow-up expectations
        if any(phrase in message_lower for phrase in ['will update', 'more to come', 'watching']):
            context['follow_up_expected'] = True
        
        return context
    
    def adjust_entry_price_with_llm(self, signal: Dict, current_price: float) -> float:
        """Adjust entry price based on Gauls' qualitative hints using LLM"""
        base_entry = signal.get('entry_price')
        entry_hint = signal.get('entry_hint', '').lower()
        
        if not base_entry or not entry_hint:
            return base_entry
        
        # LLM-powered adjustment based on hints
        adjusted_entry = base_entry
        
        try:
            if self.openai_key:
                # Use OpenAI for intelligent adjustment
                prompt = f"""
Gauls gave this trading signal for {signal['symbol']}:
Entry: {base_entry} ({signal.get('entry_hint', '')})
Current Price: {current_price}

Gauls often uses phrases like:
- "A bit above" = slightly higher entry (0.05-0.1% above stated price)
- "A bit below" = slightly lower entry (0.05-0.1% below stated price)
- "A bit above/below" = flexible entry around stated price

Based on the hint "{signal.get('entry_hint', '')}", what should the adjusted entry price be?
Consider market context and typical Gauls adjustment patterns.

Respond with just a number (the adjusted entry price).
"""
                
                client = openai.OpenAI(api_key=self.openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.1
                )
                
                try:
                    adjusted_entry = float(response.choices[0].message.content.strip())
                    logger.info(f"🤖 LLM Entry Adjustment: {base_entry} → {adjusted_entry} (hint: '{entry_hint}')")
                except ValueError:
                    # Fall back to pattern-based adjustment
                    adjusted_entry = self._pattern_based_entry_adjustment(base_entry, entry_hint)
            else:
                # Pattern-based fallback
                adjusted_entry = self._pattern_based_entry_adjustment(base_entry, entry_hint)
                
        except Exception as e:
            logger.warning(f"LLM entry adjustment failed: {e}")
            adjusted_entry = self._pattern_based_entry_adjustment(base_entry, entry_hint)
        
        return adjusted_entry
    
    def _pattern_based_entry_adjustment(self, base_entry: float, hint: str) -> float:
        """Pattern-based entry price adjustment when LLM is not available"""
        adjustment_factor = 1.0
        
        # Smart pattern matching for common Gauls phrases
        hint = hint.lower()
        
        if 'bit above' in hint or 'above' in hint:
            adjustment_factor = 1.0007  # 0.07% higher
        elif 'bit below' in hint or 'below' in hint:
            adjustment_factor = 0.9993  # 0.07% lower
        elif 'around' in hint or 'near' in hint:
            adjustment_factor = 1.0003  # 0.03% buffer
        elif 'higher' in hint:
            adjustment_factor = 1.001   # 0.1% higher
        elif 'lower' in hint:
            adjustment_factor = 0.999   # 0.1% lower
        
        adjusted_entry = base_entry * adjustment_factor
        
        if adjustment_factor != 1.0:
            logger.info(f"📊 Pattern Entry Adjustment: {base_entry} → {adjusted_entry:.2f} (hint: '{hint}')")
        
        return adjusted_entry
    
    def detect_events_in_message(self, message: str) -> List[Dict]:
        """Detect trading events mentioned in Gauls messages"""
        events = []
        
        # Temporarily disable LLM to prevent JSON parsing errors
        # Always use pattern-based detection until LLM issue is resolved
        events = self._pattern_detect_events(message)
        
        # if self.client:
        #     # Use LLM for sophisticated event detection
        #     events = self._llm_detect_events(message)
        # else:
        #     # Fallback to pattern-based detection
        #     events = self._pattern_detect_events(message)
        
        return events
    
    def _llm_detect_events(self, message: str) -> List[Dict]:
        """Use LLM to detect events in Gauls message"""
        try:
            prompt = f"""
            Analyze this Gauls trading message for mentions of upcoming market events, news, or time-sensitive triggers.
            
            MESSAGE:
            "{message}"
            
            Extract any mentioned events as JSON array. For each event found, include:
            {{
                "event_type": "FED_MEETING|EARNINGS|CPI|NFP|GDP|FOMC|ECONOMIC_DATA|TECHNICAL_EVENT|MACRO_EVENT|OTHER",
                "event_title": "Brief descriptive title",
                "event_date": "YYYY-MM-DD or null if not specified",
                "event_time": "HH:MM:SS or null if not specified", 
                "time_context": "today|tomorrow|this week|next week|specific date|relative time",
                "symbols_affected": ["BTC/USDT", "ETH/USDT"],
                "expected_impact": "BULLISH|BEARISH|NEUTRAL|VOLATILE",
                "impact_strength": 1-5,
                "confidence": 0.0-1.0,
                "description": "What Gauls said about this event",
                "trading_relevance": 0.0-1.0,
                "urgency": "LOW|MEDIUM|HIGH|CRITICAL"
            }}
            
            Common event patterns to look for:
            - "Today we've got 3 key macro events"
            - "Fed meeting tomorrow" 
            - "CPI data this week"
            - "Earnings season"
            - "post mid-week" (Thursday/Friday patterns)
            - "current week is bearish"
            - "next week setup"
            - "If price comes to X before Y"
            - Technical level events ("breakout above", "bounce from support")
            
            Return empty array [] if no events detected.
            """
            
            # Check if client is properly initialized
            if not self.client:
                logger.warning("🚨 OpenAI client not initialized, falling back to pattern detection")
                return self._pattern_detect_events(message)
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=1000
                )
            except Exception as api_error:
                logger.error(f"🚨 OpenAI API call failed: {api_error}")
                return self._pattern_detect_events(message)
            
            events_text = response.choices[0].message.content
            
            # Debug logging for empty responses
            if not events_text or events_text.strip() == "":
                logger.warning(f"🚨 OpenAI returned empty response for message: {message[:100]}...")
                logger.warning(f"🔍 Response object: {response}")
                return self._pattern_detect_events(message)
            
            events_text = events_text.strip()
            logger.debug(f"📋 LLM raw response: {events_text[:200]}...")
            
            # Parse JSON response
            try:
                events = json.loads(events_text)
                if isinstance(events, list):
                    logger.info(f"🔍 LLM detected {len(events)} events in message")
                    return events
                else:
                    logger.warning("LLM response was not a list, falling back to pattern detection")
                    return self._pattern_detect_events(message)
                    
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse LLM event response as JSON: {e}, falling back to pattern detection")
                return self._pattern_detect_events(message)
                
        except Exception as e:
            logger.error(f"LLM event detection failed: {e}")
            return self._pattern_detect_events(message)
    
    def _pattern_detect_events(self, message: str) -> List[Dict]:
        """Pattern-based fallback event detection"""
        events = []
        message_lower = message.lower()
        
        # Common event patterns
        event_patterns = {
            'fed': {'type': 'FED_MEETING', 'title': 'Federal Reserve Meeting', 'impact': 'VOLATILE', 'strength': 4},
            'fomc': {'type': 'FOMC', 'title': 'FOMC Meeting', 'impact': 'VOLATILE', 'strength': 4},
            'cpi': {'type': 'CPI', 'title': 'CPI Data Release', 'impact': 'VOLATILE', 'strength': 3},
            'nfp': {'type': 'NFP', 'title': 'Non-Farm Payrolls', 'impact': 'VOLATILE', 'strength': 3},
            'gdp': {'type': 'GDP', 'title': 'GDP Data', 'impact': 'VOLATILE', 'strength': 3},
            'earnings': {'type': 'EARNINGS', 'title': 'Earnings Release', 'impact': 'VOLATILE', 'strength': 2},
            'rate cut': {'type': 'FED_MEETING', 'title': 'Rate Decision', 'impact': 'VOLATILE', 'strength': 4},
            'macro events': {'type': 'MACRO_EVENT', 'title': 'Macro Economic Events', 'impact': 'VOLATILE', 'strength': 3}
        }
        
        # Time context patterns
        time_patterns = {
            'today': 'today',
            'tomorrow': 'tomorrow', 
            'this week': 'this week',
            'next week': 'next week',
            'thursday': 'thursday',
            'friday': 'friday',
            'mid-week': 'mid-week',
            'post mid-week': 'post mid-week'
        }
        
        # Search for event mentions
        for pattern, event_info in event_patterns.items():
            if pattern in message_lower:
                # Find time context
                time_context = 'unknown'
                for time_pattern, time_value in time_patterns.items():
                    if time_pattern in message_lower:
                        time_context = time_value
                        break
                
                event = {
                    'event_type': event_info['type'],
                    'event_title': event_info['title'],
                    'event_date': None,
                    'event_time': None,
                    'time_context': time_context,
                    'symbols_affected': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],  # Default major symbols
                    'expected_impact': event_info['impact'],
                    'impact_strength': event_info['strength'],
                    'confidence': 0.7,  # Pattern detection confidence
                    'description': f"Gauls mentioned {pattern}",
                    'trading_relevance': 0.8,
                    'urgency': 'MEDIUM',
                    'source': 'gauls_pattern'
                }
                
                events.append(event)
        
        # Special patterns for conditional events
        if 'if price comes to' in message_lower and 'before' in message_lower:
            event = {
                'event_type': 'TECHNICAL_EVENT',
                'event_title': 'Conditional Price Level Event',
                'event_date': None,
                'event_time': None,
                'time_context': 'conditional',
                'symbols_affected': ['BTC/USDT'],  # Usually BTC context
                'expected_impact': 'VOLATILE',
                'impact_strength': 3,
                'confidence': 0.8,
                'description': 'Gauls set conditional price level triggers',
                'trading_relevance': 0.9,
                'urgency': 'HIGH',
                'source': 'gauls_pattern'
            }
            events.append(event)
        
        # Weekly bias events
        if any(phrase in message_lower for phrase in ['current week', 'this week', 'week bias']):
            bias = 'NEUTRAL'
            if 'bearish' in message_lower:
                bias = 'BEARISH'
            elif 'bullish' in message_lower:
                bias = 'BULLISH'
                
            event = {
                'event_type': 'TECHNICAL_EVENT',
                'event_title': f'Weekly Market Bias - {bias}',
                'event_date': None,
                'event_time': None,
                'time_context': 'this week',
                'symbols_affected': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
                'expected_impact': bias,
                'impact_strength': 2,
                'confidence': 0.9,
                'description': f'Gauls indicated {bias.lower()} bias for the week',
                'trading_relevance': 0.7,
                'urgency': 'MEDIUM',
                'source': 'gauls_pattern'
            }
            events.append(event)
        
        if events:
            logger.info(f"📊 Pattern detection found {len(events)} events")
        
        return events
    
    def extract_event_timing(self, message: str, detected_events: List[Dict]) -> List[Dict]:
        """Extract and enhance timing information for detected events"""
        enhanced_events = []
        
        for event in detected_events:
            enhanced_event = event.copy()
            
            # Try to extract specific dates/times
            import re
            
            # Look for date patterns (simplified)
            date_patterns = [
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY or MM-DD-YYYY
                r'(\d{4}-\d{1,2}-\d{1,2})',          # YYYY-MM-DD
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, message)
                if match:
                    enhanced_event['event_date'] = match.group(1)
                    break
            
            # Look for time patterns
            time_pattern = r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)'
            time_match = re.search(time_pattern, message, re.IGNORECASE)
            if time_match:
                enhanced_event['event_time'] = time_match.group(1)
            
            # Enhance urgency based on time context
            time_context = enhanced_event.get('time_context', '').lower()
            if time_context in ['today', 'now', 'immediate']:
                enhanced_event['urgency'] = 'CRITICAL'
            elif time_context in ['tomorrow', 'tonight']:
                enhanced_event['urgency'] = 'HIGH'
            elif time_context in ['this week']:
                enhanced_event['urgency'] = 'MEDIUM'
            
            enhanced_events.append(enhanced_event)
        
        return enhanced_events

def test_llm_analyzer():
    """Test the LLM analyzer with real Gauls data"""
    
    # Sample real Gauls signal
    signal = {
        'symbol': 'BTC/USDT',
        'entry_price': 111216.0,
        'take_profit': 114914.6,
        'stop_loss': 109896.1,
        'risk_reward': 2.8,
        'side': 'buy'
    }
    
    message = """**$BTC**** Buying Setup:**

👉 Entry: 111216 (A bit above)
👉 TP: 114914.6
👉 SL: 109896.1
👉 RR: 2.8

Good night 🌃

**#TraderGauls****🎭**"""
    
    analyzer = GaulsLLMAnalyzer()
    
    print("=== GAULS LLM ANALYZER TEST ===")
    
    # Basic signal analysis
    analysis = analyzer.analyze_signal_quality(signal, message)
    print(f"Signal Confidence: {analysis['signal_confidence']}")
    print(f"Risk Assessment: {analysis['risk_assessment']}")
    print(f"Recommendation: {analysis['execution_recommendation']}")
    print(f"Reasoning: {analysis.get('reasoning', [])}")
    
    # Market validation
    enhanced_analysis = analyzer.validate_against_market_conditions(signal, analysis)
    print(f"Warnings: {enhanced_analysis.get('warnings', [])}")
    
    # Execution plan
    plan = analyzer.generate_execution_plan(signal, enhanced_analysis)
    print(f"Should Execute: {plan['should_execute']}")
    print(f"Position Size Modifier: {plan['position_size_modifier']:.1f}x")
    print(f"Entry Strategy: {plan['entry_strategy']}")

if __name__ == "__main__":
    test_llm_analyzer()