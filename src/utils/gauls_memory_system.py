#!/usr/bin/env python3
"""
🧠 Gauls Memory System - Strategic Intelligence Storage & Retrieval

Stores and analyzes Gauls' strategic market insights beyond individual trades.
Provides memory-based context for SAGE trading decisions.
"""

import sys
sys.path.insert(0, '/gauls-copy-trading-system/src')


import sqlite3
import json
import re
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)

class MessageType(Enum):
    SIGNAL = "signal"           # Individual trade signals  
    ANALYSIS = "analysis"       # Market structure analysis
    STRATEGY = "strategy"       # Strategic guidance
    CONVICTION = "conviction"   # High-confidence predictions
    RISK = "risk"              # Risk management guidance
    TIMING = "timing"          # Time-based expectations

class ConvictionLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"  
    HIGH = "high"
    GUARANTEE = "guarantee"

@dataclass
class MarketInsight:
    """Strategic market insight from Gauls"""
    message_type: MessageType
    raw_text: str
    timestamp: int = 0
    
    # Market Structure
    resistance_levels: List[float] = field(default_factory=list)
    support_levels: List[float] = field(default_factory=list)
    key_zones: Dict[str, float] = field(default_factory=dict)
    
    # Strategic Triggers  
    bullish_triggers: List[str] = field(default_factory=list)
    bearish_triggers: List[str] = field(default_factory=list)
    wait_conditions: List[str] = field(default_factory=list)
    
    # Context & Timing
    time_context: Dict[str, str] = field(default_factory=dict)  # {"month": "September", "type": "news-driven"}
    validity_period_hours: int = 168  # 1 week default
    
    # Conviction & Risk
    conviction_level: ConvictionLevel = ConvictionLevel.MEDIUM
    risk_guidance: Dict[str, str] = field(default_factory=dict)
    position_sizing: Dict[str, str] = field(default_factory=dict)
    
    # Targets & Expectations
    price_targets: Dict[str, List[float]] = field(default_factory=dict)  # {"BTC": [95000, 100000]}
    expected_moves: Dict[str, str] = field(default_factory=dict)  # {"alts": "2x+"}
    
    # References
    symbols_mentioned: List[str] = field(default_factory=list)
    related_insights: List[int] = field(default_factory=list)

class GaulsMemorySystem:
    """Comprehensive memory system for Gauls strategic insights"""
    
    def __init__(self, db_path: str = "/opt/sage-trading-system/sage_trading.db", openai_key: Optional[str] = None):
        self.db_path = db_path
        self.openai_key = openai_key
        if openai_key and openai:
            self.client = openai.OpenAI(api_key=openai_key)
        else:
            self.client = None
            
        self._initialize_memory_db()
        
        # Insight extraction patterns
        self._init_extraction_patterns()
    
    def _initialize_memory_db(self):
        """Create memory database tables"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Market insights table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gauls_market_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_type TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    
                    -- Market Structure
                    resistance_levels TEXT,  -- JSON array
                    support_levels TEXT,     -- JSON array  
                    key_zones TEXT,         -- JSON object
                    
                    -- Strategic Triggers
                    bullish_triggers TEXT,   -- JSON array
                    bearish_triggers TEXT,   -- JSON array
                    wait_conditions TEXT,    -- JSON array
                    
                    -- Context & Timing
                    time_context TEXT,       -- JSON object
                    validity_period_hours INTEGER DEFAULT 168,
                    expires_at DATETIME,
                    
                    -- Conviction & Risk
                    conviction_level TEXT,
                    risk_guidance TEXT,      -- JSON object
                    position_sizing TEXT,    -- JSON object
                    
                    -- Targets & Expectations
                    price_targets TEXT,      -- JSON object
                    expected_moves TEXT,     -- JSON object
                    
                    -- References  
                    symbols_mentioned TEXT,  -- JSON array
                    related_insights TEXT,   -- JSON array of IDs
                    
                    -- Metadata
                    accuracy_score REAL DEFAULT 0.0,
                    usage_count INTEGER DEFAULT 0,
                    last_used DATETIME,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Enhanced signals table reference
            conn.execute("""
                ALTER TABLE gauls_signals 
                ADD COLUMN insight_reference_id INTEGER 
                REFERENCES gauls_market_insights(id)
            """)
            
            conn.commit()
            logger.info("✅ Memory database tables initialized")
            
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                logger.error(f"Database initialization error: {e}")
        finally:
            conn.close()
    
    def _init_extraction_patterns(self):
        """Initialize patterns for extracting insights"""
        self.patterns = {
            # Price levels
            'price_levels': re.compile(r'\$?([\d,]+\.?\d*[KkMmBbTt]?)', re.IGNORECASE),
            'resistance': re.compile(r'resistance.*?\$?([\d,]+\.?\d*[KkMmBbTt]?)', re.IGNORECASE),
            'support': re.compile(r'support.*?\$?([\d,]+\.?\d*[KkMmBbTt]?)', re.IGNORECASE),
            
            # Triggers
            'break_retest': re.compile(r'break.*?retest', re.IGNORECASE),
            'retrace': re.compile(r'retrace.*?to.*?\$?([\d,]+\.?\d*[KkMmBbTt]?)', re.IGNORECASE),
            
            # Conviction indicators
            'guarantee': re.compile(r'\b(guarantee|guaranteed?)\b', re.IGNORECASE),
            'high_conviction': re.compile(r'\b(high.conviction|conviction)\b', re.IGNORECASE),
            'each_alt': re.compile(r'each alt.*?(\d+)x', re.IGNORECASE),
            
            # Time context
            'month_context': re.compile(r'(january|february|march|april|may|june|july|august|september|october|november|december).*?(driven|month)', re.IGNORECASE),
            'news_driven': re.compile(r'news.driven', re.IGNORECASE),
            
            # Risk guidance
            'risk_small': re.compile(r'risk small', re.IGNORECASE),
            'accumulate': re.compile(r'accumulate.*?(major|big)', re.IGNORECASE),
            
            # Symbols
            'symbols': re.compile(r'\$([A-Z]{2,5})\b', re.IGNORECASE),
            'total2': re.compile(r'\$TOTAL2', re.IGNORECASE),
        }
    
    def analyze_message(self, message_text: str) -> Optional[MarketInsight]:
        """Analyze message and extract strategic insights"""
        try:
            # Classify message type
            message_type = self._classify_message_type(message_text)
            
            insight = MarketInsight(
                message_type=message_type,
                raw_text=message_text,
                timestamp=int(datetime.now().timestamp())
            )
            
            # Extract different types of insights
            self._extract_market_structure(message_text, insight)
            self._extract_strategic_triggers(message_text, insight)
            self._extract_time_context(message_text, insight) 
            self._extract_conviction_risk(message_text, insight)
            self._extract_targets_moves(message_text, insight)
            self._extract_symbols(message_text, insight)
            
            # Use AI for deeper analysis if available
            if self.client:
                self._enhance_with_ai(message_text, insight)
            
            logger.info(f"📊 Analyzed {message_type.value} message: {len(insight.symbols_mentioned)} symbols, conviction: {insight.conviction_level.value}")
            return insight
            
        except Exception as e:
            logger.error(f"Error analyzing message: {e}")
            return None
    
    def _classify_message_type(self, text: str) -> MessageType:
        """Classify the type of message"""
        text_lower = text.lower()
        
        # Check for specific signal indicators
        if any(word in text_lower for word in ['cmp', 'long', 'short', 'entry', 'stop']):
            return MessageType.SIGNAL
            
        # Check for conviction indicators  
        if any(word in text_lower for word in ['guarantee', 'each alt', 'will pump', 'conviction']):
            return MessageType.CONVICTION
            
        # Check for risk management
        if any(word in text_lower for word in ['risk small', 'accumulate', 'position']):
            return MessageType.RISK
            
        # Check for time context
        if any(word in text_lower for word in ['september', 'month', 'driven', 'coming days']):
            return MessageType.TIMING
            
        # Check for strategy guidance
        if any(word in text_lower for word in ['trigger', 'build positions', 'wait', 'look for']):
            return MessageType.STRATEGY
            
        # Default to analysis
        return MessageType.ANALYSIS
    
    def _extract_market_structure(self, text: str, insight: MarketInsight):
        """Extract market structure information"""
        # Find resistance levels
        resistance_match = self.patterns['resistance'].search(text)
        if resistance_match:
            level = self._parse_price(resistance_match.group(1))
            if level:
                insight.resistance_levels.append(level)
        
        # Find support levels  
        support_match = self.patterns['support'].search(text)
        if support_match:
            level = self._parse_price(support_match.group(1))
            if level:
                insight.support_levels.append(level)
                
        # Find key zones mentioned
        if '$1.6T' in text:
            insight.key_zones['TOTAL2_support'] = 1600000000000  # $1.6T in dollars
    
    def _extract_strategic_triggers(self, text: str, insight: MarketInsight):
        """Extract strategic triggers and conditions"""
        text_lower = text.lower()
        
        # Bullish triggers
        if self.patterns['break_retest'].search(text):
            insight.bullish_triggers.append("Break and retest of resistance")
            
        # Wait conditions
        retrace_match = self.patterns['retrace'].search(text)
        if retrace_match:
            level = retrace_match.group(1)
            insight.wait_conditions.append(f"Wait for retrace to {level}")
            
        if "wait" in text_lower and "dips" in text_lower:
            insight.wait_conditions.append("Wait for major dips to accumulate")
    
    def _extract_time_context(self, text: str, insight: MarketInsight):
        """Extract time-based context"""
        month_match = self.patterns['month_context'].search(text)
        if month_match:
            month = month_match.group(1)
            context_type = month_match.group(2)
            insight.time_context['month'] = month.capitalize()
            insight.time_context['type'] = f"{context_type}-driven"
            
        if "coming days" in text.lower():
            insight.time_context['timeframe'] = "coming_days"
            insight.validity_period_hours = 168  # 1 week
    
    def _extract_conviction_risk(self, text: str, insight: MarketInsight):
        """Extract conviction level and risk guidance"""
        text_lower = text.lower()
        
        # Conviction level
        if self.patterns['guarantee'].search(text):
            insight.conviction_level = ConvictionLevel.GUARANTEE
        elif self.patterns['high_conviction'].search(text):
            insight.conviction_level = ConvictionLevel.HIGH
        elif "will pump" in text_lower:
            insight.conviction_level = ConvictionLevel.HIGH
        
        # Risk guidance
        if self.patterns['risk_small'].search(text):
            insight.risk_guidance['ltf_risk'] = "small"
            
        if self.patterns['accumulate'].search(text):
            insight.position_sizing['major_dips'] = "accumulate_big"
            
        if "patience and conviction" in text_lower:
            insight.risk_guidance['mindset'] = "patience_and_conviction"
    
    def _extract_targets_moves(self, text: str, insight: MarketInsight):
        """Extract price targets and expected moves"""
        # Look for specific move expectations
        alt_move_match = self.patterns['each_alt'].search(text)
        if alt_move_match:
            multiplier = alt_move_match.group(1)
            insight.expected_moves['alts'] = f"{multiplier}x+"
            
        if "2x+" in text:
            insight.expected_moves['alts'] = "2x+"
    
    def _extract_symbols(self, text: str, insight: MarketInsight):
        """Extract mentioned symbols"""
        # Find all symbol mentions
        symbol_matches = self.patterns['symbols'].findall(text)
        for symbol in symbol_matches:
            if symbol.upper() not in ['CMP', 'LTF', 'HTF']:  # Exclude non-symbols
                insight.symbols_mentioned.append(f"{symbol.upper()}/USDT")
        
        # Special case for TOTAL2
        if self.patterns['total2'].search(text):
            insight.symbols_mentioned.append('TOTAL2')
    
    def _enhance_with_ai(self, text: str, insight: MarketInsight):
        """Enhance analysis using OpenAI"""
        try:
            prompt = f"""
            Analyze this trading message and extract strategic insights:
            
            "{text}"
            
            Extract and format as JSON:
            {{
                "market_structure": {{"resistance": [], "support": [], "key_levels": {{}}}},
                "strategic_triggers": {{"bullish": [], "bearish": [], "wait_conditions": []}},
                "conviction_indicators": {{"level": "low/medium/high/guarantee", "reasoning": ""}},
                "risk_guidance": {{"position_sizing": "", "timing": "", "mindset": ""}},
                "time_context": {{"timeframe": "", "seasonal": "", "market_phase": ""}},
                "price_expectations": {{"targets": {{}}, "moves": {{}}}},
                "key_insights": ["list of main strategic points"]
            }}
            
            Focus on strategic insights, not individual trade signals.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            ai_analysis = json.loads(response.choices[0].message.content)
            
            # Merge AI insights with extracted insights
            if ai_analysis.get('conviction_indicators', {}).get('level'):
                level_map = {
                    'low': ConvictionLevel.LOW,
                    'medium': ConvictionLevel.MEDIUM,
                    'high': ConvictionLevel.HIGH,
                    'guarantee': ConvictionLevel.GUARANTEE
                }
                ai_level = ai_analysis['conviction_indicators']['level']
                if ai_level in level_map:
                    insight.conviction_level = level_map[ai_level]
            
            logger.debug("✅ Enhanced analysis with AI insights")
            
        except Exception as e:
            logger.error(f"AI enhancement failed: {e}")
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parse price string to float (handles K, M, B, T suffixes)"""
        try:
            price_str = price_str.replace(',', '').upper()
            
            multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000, 'T': 1000000000000}
            
            for suffix, multiplier in multipliers.items():
                if suffix in price_str:
                    number = float(price_str.replace(suffix, ''))
                    return number * multiplier
            
            return float(price_str)
            
        except (ValueError, AttributeError):
            return None
    
    def store_insight(self, insight: MarketInsight) -> int:
        """Store strategic insight in memory database"""
        conn = sqlite3.connect(self.db_path)
        try:
            expires_at = datetime.now() + timedelta(hours=insight.validity_period_hours)
            
            cursor = conn.execute("""
                INSERT INTO gauls_market_insights (
                    message_type, raw_text, resistance_levels, support_levels, key_zones,
                    bullish_triggers, bearish_triggers, wait_conditions, time_context,
                    validity_period_hours, expires_at, conviction_level, risk_guidance,
                    position_sizing, price_targets, expected_moves, symbols_mentioned,
                    related_insights
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                insight.message_type.value,
                insight.raw_text,
                json.dumps(insight.resistance_levels),
                json.dumps(insight.support_levels),
                json.dumps(insight.key_zones),
                json.dumps(insight.bullish_triggers),
                json.dumps(insight.bearish_triggers), 
                json.dumps(insight.wait_conditions),
                json.dumps(insight.time_context),
                insight.validity_period_hours,
                expires_at.isoformat(),
                insight.conviction_level.value,
                json.dumps(insight.risk_guidance),
                json.dumps(insight.position_sizing),
                json.dumps(insight.price_targets),
                json.dumps(insight.expected_moves),
                json.dumps(insight.symbols_mentioned),
                json.dumps(insight.related_insights)
            ))
            
            insight_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"💾 Stored {insight.message_type.value} insight (ID: {insight_id})")
            return insight_id
            
        finally:
            conn.close()
    
    def get_strategic_memory_for_symbol(self, symbol: str, hours: int = 72) -> Dict[str, Any]:
        """Get strategic memory context for a specific symbol"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor = conn.execute("""
                SELECT * FROM gauls_market_insights 
                WHERE (symbols_mentioned LIKE ? OR symbols_mentioned LIKE ?)
                AND timestamp > ? AND is_active = 1 AND expires_at > datetime('now')
                ORDER BY timestamp DESC, conviction_level DESC
                LIMIT 10
            """, (f'%{symbol}%', '%TOTAL2%', cutoff_time))
            
            insights = []
            for row in cursor:
                insights.append(dict(row))
            
            if not insights:
                return {'has_memory': False, 'context': 'No strategic insights available'}
            
            # Analyze insights for strategic context
            context = self._build_strategic_context(symbol, insights)
            
            conn.execute("""
                UPDATE gauls_market_insights 
                SET usage_count = usage_count + 1, last_used = datetime('now')
                WHERE id IN ({})
            """.format(','.join('?' * len(insights))), [i['id'] for i in insights])
            conn.commit()
            
            return context
            
        finally:
            conn.close()
    
    def _build_strategic_context(self, symbol: str, insights: List[Dict]) -> Dict[str, Any]:
        """Build strategic trading context from memory"""
        context = {
            'has_memory': True,
            'insights_count': len(insights),
            'market_structure': {},
            'strategic_guidance': [],
            'conviction_signals': [],
            'risk_framework': {},
            'timing_context': {},
            'recent_insights': insights[:3]  # Most recent 3
        }
        
        # Aggregate market structure
        all_resistance = []
        all_support = []
        key_zones = {}
        
        for insight in insights:
            if insight['resistance_levels']:
                levels = json.loads(insight['resistance_levels'])
                all_resistance.extend(levels)
                
            if insight['support_levels']:
                levels = json.loads(insight['support_levels'])  
                all_support.extend(levels)
                
            if insight['key_zones']:
                zones = json.loads(insight['key_zones'])
                key_zones.update(zones)
        
        context['market_structure'] = {
            'resistance_levels': sorted(set(all_resistance), reverse=True)[:3],
            'support_levels': sorted(set(all_support))[:3],
            'key_zones': key_zones
        }
        
        # Aggregate strategic guidance
        all_triggers = []
        wait_conditions = []
        
        for insight in insights:
            if insight['bullish_triggers']:
                triggers = json.loads(insight['bullish_triggers'])
                all_triggers.extend(triggers)
                
            if insight['wait_conditions']:
                conditions = json.loads(insight['wait_conditions'])
                wait_conditions.extend(conditions)
        
        context['strategic_guidance'] = {
            'active_triggers': list(set(all_triggers))[:3],
            'wait_conditions': list(set(wait_conditions))[:3]
        }
        
        # Conviction analysis
        high_conviction_count = sum(1 for i in insights if i['conviction_level'] in ['high', 'guarantee'])
        context['conviction_signals'] = {
            'high_conviction_insights': high_conviction_count,
            'total_insights': len(insights),
            'conviction_ratio': high_conviction_count / len(insights) if insights else 0
        }
        
        # Risk framework
        risk_guidance = {}
        for insight in insights:
            if insight['risk_guidance']:
                guidance = json.loads(insight['risk_guidance'])
                risk_guidance.update(guidance)
        
        context['risk_framework'] = risk_guidance
        
        # Timing context
        time_contexts = []
        for insight in insights:
            if insight['time_context']:
                time_ctx = json.loads(insight['time_context'])
                time_contexts.append(time_ctx)
        
        if time_contexts:
            context['timing_context'] = time_contexts[0]  # Most recent
        
        return context
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get overview of stored strategic memory"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Count insights by type
            cursor = conn.execute("""
                SELECT message_type, COUNT(*) as count
                FROM gauls_market_insights
                WHERE is_active = 1 AND expires_at > datetime('now')
                GROUP BY message_type
            """)
            
            insights_by_type = dict(cursor.fetchall())
            
            # Recent insights
            cursor = conn.execute("""
                SELECT message_type, conviction_level, symbols_mentioned, timestamp
                FROM gauls_market_insights
                WHERE is_active = 1 AND expires_at > datetime('now')
                ORDER BY timestamp DESC
                LIMIT 5
            """)
            
            recent_insights = [dict(zip([col[0] for col in cursor.description], row)) 
                             for row in cursor.fetchall()]
            
            # Most referenced symbols
            cursor = conn.execute("""
                SELECT symbols_mentioned, COUNT(*) as mentions
                FROM gauls_market_insights
                WHERE is_active = 1 AND expires_at > datetime('now')
                AND symbols_mentioned IS NOT NULL
                GROUP BY symbols_mentioned
                ORDER BY mentions DESC
                LIMIT 5
            """)
            
            symbol_mentions = cursor.fetchall()
            
            return {
                'total_active_insights': sum(insights_by_type.values()),
                'insights_by_type': insights_by_type,
                'recent_insights': recent_insights,
                'top_symbols': symbol_mentions,
                'memory_health': 'active' if insights_by_type else 'empty'
            }
            
        finally:
            conn.close()
    
    async def process_gauls_message(self, message_text: str) -> Optional[int]:
        """Process a Gauls message asynchronously - main entry point from Telegram listener"""
        try:
            # Analyze the message to extract insights
            insight = self.analyze_message(message_text)
            
            if insight:
                # Store the insight in the database
                insight_id = self.store_insight(insight)
                logger.info(f"✅ Processed Gauls message -> Insight ID: {insight_id}")
                return insight_id
            else:
                logger.info("📋 Message processed but no strategic insights extracted")
                return None
                
        except Exception as e:
            logger.error(f"Error processing Gauls message: {e}")
            return None
    
    def process_gauls_message_sync(self, message_text: str) -> Optional[int]:
        """Process a Gauls message synchronously - for test/simulated messages"""
        try:
            # Analyze the message to extract insights
            insight = self.analyze_message(message_text)
            
            if insight:
                # Store the insight in the database
                insight_id = self.store_insight(insight)
                logger.info(f"✅ Processed Gauls message (sync) -> Insight ID: {insight_id}")
                return insight_id
            else:
                logger.info("📋 Message processed but no strategic insights extracted")
                return None
                
        except Exception as e:
            logger.error(f"Error processing Gauls message (sync): {e}")
            return None