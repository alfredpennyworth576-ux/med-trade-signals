"""
Data models for Med-Trade-Signals
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum
import json

class SignalType(Enum):
    """Types of trading signals"""
    FDA_APPROVAL = "FDA_APPROVAL"
    FDA_REJECTION = "FDA_REJECTION"
    FDA_WARNING = "FDA_WARNING"
    TRIAL_SUCCESS = "TRIAL_SUCCESS"
    TRIAL_FAILURE = "TRIAL_FAILURE"
    TRIAL_PHASE_ADVANCE = "TRIAL_PHASE_ADVANCE"
    SEC_FILING = "SEC_FILING"
    PRICE_TARGET_UP = "PRICE_TARGET_UP"
    PRICE_TARGET_DOWN = "PRICE_TARGET_DOWN"
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    INSIDER_BUYING = "INSIDER_BUYING"
    ANALYST_NOTE = "ANALYST_NOTE"
    REDDIT_SENTIMENT = "REDDIT_SENTIMENT"

class Sentiment(Enum):
    """Sentiment classification"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class ConfidenceLevel(Enum):
    """Confidence levels"""
    VERY_HIGH = 90
    HIGH = 75
    MEDIUM = 60
    LOW = 40
    VERY_LOW = 20

@dataclass
class Source:
    """Data source reference"""
    name: str
    url: str
    reliability_score: float  # 0-1
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "url": self.url,
            "reliability_score": self.reliability_score,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class Entity:
    """Extracted entity from text"""
    text: str
    entity_type: str  # drug, company, ticker, condition, trial
    confidence: float
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "entity_type": self.entity_type,
            "confidence": self.confidence,
            "metadata": self.metadata
        }

@dataclass
class ClinicalData:
    """Clinical trial / medical data"""
    trial_phase: Optional[str] = None
    indication: Optional[str] = None
    efficacy: Optional[float] = None
    efficacy_unit: Optional[str] = None
    p_value: Optional[float] = None
    population_size: Optional[int] = None
    control_arm: Optional[str] = None
    treatment_arm: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "trial_phase": self.trial_phase,
            "indication": self.indication,
            "efficacy": self.efficacy,
            "efficacy_unit": self.efficacy_unit,
            "p_value": self.p_value,
            "population_size": self.population_size,
            "control_arm": self.control_arm,
            "treatment_arm": self.treatment_arm
        }

@dataclass
class TradingSignal:
    """Main trading signal output"""
    signal_id: str
    signal_type: SignalType
    ticker: str
    company_name: str
    headline: str
    summary: str
    confidence: int  # 0-100
    sentiment: Sentiment
    
    # Price targets
    target_upside: Optional[float] = None
    target_downside: Optional[float] = None
    
    # Metadata
    sources: List[Source] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    clinical_data: Optional[ClinicalData] = None
    
    # Timestamps
    collected_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    
    # Additional context
    raw_text: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "headline": self.headline,
            "summary": self.summary,
            "confidence": self.confidence,
            "sentiment": self.sentiment.value,
            "target_upside": self.target_upside,
            "target_downside": self.target_downside,
            "sources": [s.to_dict() for s in self.sources],
            "entities": [e.to_dict() for e in self.entities],
            "clinical_data": self.clinical_data.to_dict() if self.clinical_data else None,
            "collected_at": self.collected_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "raw_text": self.raw_text,
            "tags": self.tags
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 90:
            return ConfidenceLevel.VERY_HIGH
        elif self.confidence >= 75:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 60:
            return ConfidenceLevel.MEDIUM
        elif self.confidence >= 40:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

@dataclass
class PaperTrade:
    """Paper trade record"""
    trade_id: str
    signal_id: str
    ticker: str
    direction: str  # long, short
    entry_price: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str = "open"  # open, closed, cancelled
    
    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "signal_id": self.signal_id,
            "ticker": self.ticker,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "status": self.status
        }

@dataclass
class Portfolio:
    """Paper trading portfolio"""
    cash: float
    positions: Dict[str, Dict] = field(default_factory=dict)  # ticker -> {shares, avg_price}
    trades: List[PaperTrade] = field(default_factory=list)
    total_pnl: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "cash": self.cash,
            "positions": self.positions,
            "trades": [t.to_dict() for t in self.trades],
            "total_pnl": self.total_pnl
        }
