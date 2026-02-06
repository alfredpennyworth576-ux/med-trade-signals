"""
Signal Generator - Create trading signals from medical news
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
import hashlib
import re
import sys
sys.path.insert(0, str(__file__).replace('signals/generator.py', ''))
from collectors.pubmed import PubMedCollector
from collectors.fda import FDACollector
from collectors.reddit import RedditCollector
from nlp.utils import EntityExtractor, SentimentAnalyzer
from utils.config import config
from utils.logger import logger


@dataclass
class TradingSignal:
    """Trading signal output"""
    signal_id: str
    signal_type: str  # FDA_APPROVAL, TRIAL_SUCCESS, etc.
    ticker: str
    company_name: str
    headline: str
    summary: str
    confidence: int  # 0-100
    sentiment: str  # positive, negative, neutral
    target_upside: Optional[float]
    target_downside: Optional[float]
    sources: List[str]
    collected_at: str
    created_at: str
    # Enhanced fields
    source_quality: float = 0.0  # 0-1
    recency_weight: float = 1.0  # 0-1
    market_impact_score: float = 0.0  # 0-1
    duplicate_hash: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)
    
    def calculate_deduplication_hash(self) -> str:
        """Generate hash for deduplication"""
        content = f"{self.ticker}:{self.signal_type}:{self.headline[:50]}:{self.collected_at}"
        return hashlib.md5(content.encode()).hexdigest()


class SignalGenerator:
    """Generate trading signals from medical data"""
    
    # Comprehensive signal types with metadata
    SIGNAL_TYPES = {
        "FDA_APPROVAL": {
            "keywords": ["fda approves", "fda approved", "approval granted", "cleared by fda"],
            "sentiment": "positive",
            "target_upside": 15.0,
            "target_downside": -5.0,
            "base_confidence": 85,
            "source_weight": {"fda.gov": 1.0, "pubmed": 0.7, "reuters": 0.9, "reddit": 0.3},
            "market_impact": "high"
        },
        "FDA_REJECTION": {
            "keywords": ["fda rejects", "fda rejected", "not approved", "complete response letter"],
            "sentiment": "negative",
            "target_upside": -20.0,
            "target_downside": -30.0,
            "base_confidence": 90,
            "source_weight": {"fda.gov": 1.0, "pubmed": 0.7, "reuters": 0.9, "reddit": 0.3},
            "market_impact": "high"
        },
        "FDA_WARNING": {
            "keywords": ["fda warning", "warning letter", "safety concern", "advisory committee"],
            "sentiment": "negative",
            "target_upside": -10.0,
            "target_downside": -20.0,
            "base_confidence": 75,
            "source_weight": {"fda.gov": 1.0, "reuters": 0.9, "pubmed": 0.5, "reddit": 0.3},
            "market_impact": "medium"
        },
        "TRIAL_SUCCESS": {
            "keywords": ["primary endpoint met", "met primary endpoint", "successful trial", 
                        "statistically significant", "phase 3 success", "positive results"],
            "sentiment": "positive",
            "target_upside": 12.0,
            "target_downside": -3.0,
            "base_confidence": 75,
            "source_weight": {"pubmed": 0.9, "reuters": 0.9, "fda.gov": 0.8, "reddit": 0.3},
            "market_impact": "high"
        },
        "TRIAL_FAILURE": {
            "keywords": ["primary endpoint not met", "failed trial", "study failed", 
                        "negative results", "did not meet endpoint"],
            "sentiment": "negative",
            "target_upside": -15.0,
            "target_downside": -25.0,
            "base_confidence": 80,
            "source_weight": {"pubmed": 0.9, "reuters": 0.9, "fda.gov": 0.8, "reddit": 0.3},
            "market_impact": "high"
        },
        "TRIAL_PHASE_ADVANCE": {
            "keywords": ["phase 3 initiated", "phase 2 completed", "advances to next phase",
                        "enrolling phase", "initiates pivotal trial"],
            "sentiment": "positive",
            "target_upside": 8.0,
            "target_downside": -2.0,
            "base_confidence": 70,
            "source_weight": {"fda.gov": 0.9, "reuters": 0.8, "pubmed": 0.6, "reddit": 0.3},
            "market_impact": "medium"
        },
        "SEC_FILING": {
            "keywords": ["10-k", "10q", "8-k", "sec filing", "annual report", "quarterly results"],
            "sentiment": "neutral",
            "target_upside": 3.0,
            "target_downside": -3.0,
            "base_confidence": 60,
            "source_weight": {"sec.gov": 1.0, "reuters": 0.8, "reddit": 0.3},
            "market_impact": "low"
        },
        "PRICE_TARGET_CHANGE": {
            "keywords": ["price target raised", "price target cut", "target price", 
                        "upside potential", "pt raised", "pt cut"],
            "sentiment": "positive" if "raised" in str() else "negative",
            "target_upside": 10.0,
            "target_downside": -10.0,
            "base_confidence": 65,
            "source_weight": {"reuters": 0.9, "fda.gov": 0.5, "reddit": 0.3},
            "market_impact": "medium"
        },
        "UPGRADE_DOWNGRADE": {
            "keywords": ["upgraded", "downgraded", "rating raised", "rating cut",
                        "buy rating", "sell rating", "hold rating"],
            "sentiment": "positive" if "upgraded" in str() else "negative",
            "target_upside": 6.0,
            "target_downside": -6.0,
            "base_confidence": 65,
            "source_weight": {"reuters": 0.9, "reddit": 0.3},
            "market_impact": "medium"
        },
        "INSIDER_BUYING": {
            "keywords": ["insider buying", "insider purchase", "director buys", 
                        "ceo purchases", "officer buys", "open market purchase"],
            "sentiment": "positive",
            "target_upside": 5.0,
            "target_downside": -2.0,
            "base_confidence": 60,
            "source_weight": {"sec.gov": 0.9, "reuters": 0.8, "reddit": 0.4},
            "market_impact": "low"
        }
    }
    
    # Source reliability scores
    SOURCE_RELIABILITY = {
        "fda.gov": 1.0,
        "sec.gov": 1.0,
        "pubmed.ncbi.nlm.nih.gov": 0.95,
        "nejm.org": 0.95,
        "reuters.com": 0.9,
        "wsj.com": 0.85,
        "bloomberg.com": 0.85,
        "cnn.com": 0.7,
        "reddit.com": 0.4,
        "twitter.com": 0.3,
        "investorhub": 0.25,
        "stocktwits": 0.25
    }
    
    def __init__(self):
        self.extractor = EntityExtractor()
        self.analyzer = SentimentAnalyzer()
        self.pubmed = PubMedCollector()
        self.fda = FDACollector()
        self.reddit = RedditCollector()
        self._signal_cache = {}  # For deduplication
    
    def _get_source_quality(self, source: str) -> float:
        """Get reliability score for a source"""
        for known_source, score in self.SOURCE_RELIABILITY.items():
            if known_source in source.lower():
                return score
        return 0.5  # Default for unknown sources
    
    def _get_recency_weight(self, collected_at: str) -> float:
        """Calculate recency weight (newer = higher weight)"""
        try:
            collected_date = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
            now = datetime.now()
            hours_old = (now - collected_date).total_seconds() / 3600
            
            # Decay curve: 100% at 0h, 50% at 24h, 25% at 48h
            if hours_old < 0:
                return 1.0  # Future dates treated as now
            return max(0.1, 1.0 / (1.0 + hours_old / 24))
        except (ValueError, AttributeError):
            return 0.5  # Default if parsing fails
    
    def _calculate_confidence(self, signal_type: str, source_quality: float,
                              recency_weight: float, sentiment_match: bool,
                              entity_quality: float) -> int:
        """Calculate confidence score (0-100)"""
        rules = self.SIGNAL_TYPES.get(signal_type, {})
        base = rules.get("base_confidence", 50)
        
        # Adjustments
        confidence = base * source_quality * recency_weight
        
        if sentiment_match:
            confidence += 10
        
        confidence *= (0.8 + 0.2 * entity_quality)  # Entity quality modifier
        
        # Clamp to valid range
        return min(95, max(10, int(confidence)))
    
    def _detect_signal_type(self, text: str) -> Optional[str]:
        """Detect signal type from text"""
        text_lower = text.lower()
        
        # Priority order for detection
        priority_types = [
            "FDA_APPROVAL", "FDA_REJECTION", "FDA_WARNING",
            "TRIAL_SUCCESS", "TRIAL_FAILURE", "TRIAL_PHASE_ADVANCE",
            "SEC_FILING", "PRICE_TARGET_CHANGE", "UPGRADE_DOWNGRADE", "INSIDER_BUYING"
        ]
        
        for signal_type in priority_types:
            keywords = self.SIGNAL_TYPES.get(signal_type, {}).get("keywords", [])
            for keyword in keywords:
                if keyword in text_lower:
                    return signal_type
        return None
    
    def _is_duplicate(self, signal: TradingSignal) -> bool:
        """Check if signal is a duplicate"""
        hash_key = signal.calculate_deduplication_hash()
        
        # Check exact duplicate
        if hash_key in self._signal_cache:
            existing = self._signal_cache[hash_key]
            if existing.confidence >= signal.confidence:
                return True
            else:
                # Replace with higher confidence duplicate
                self._signal_cache[hash_key] = signal
                return False
        
        self._signal_cache[hash_key] = signal
        return False
    
    def generate_from_pubmed(self, query: str = "AI medical imaging") -> List[TradingSignal]:
        """Generate signals from PubMed papers"""
        logger.info("Generating signals from PubMed")
        signals = []
        
        try:
            papers = self.pubmed.collect(query)
        except Exception as e:
            logger.error(f"Error collecting from PubMed: {e}")
            return signals
        
        for paper in papers:
            # Analyze the paper
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            text = f"{title} {abstract}"
            
            # Detect signal type
            signal_type = self._detect_signal_type(text)
            if not signal_type:
                continue
            
            # Extract entities
            ticker = self.extractor.extract_ticker(text)
            if not ticker:
                continue
            
            entities = self.extractor.extract_entities(text)
            company_name = entities.get("company", ticker)
            
            # Analyze sentiment
            clinical = self.analyzer.get_clinical_sentiment(text)
            rules = self.SIGNAL_TYPES[signal_type]
            
            # Calculate metrics
            source_quality = self._get_source_quality("pubmed")
            recency_weight = self._get_recency_weight(paper.get("year", ""))
            sentiment_match = clinical["sentiment"] == rules["sentiment"]
            entity_quality = 1.0 if ticker else 0.5
            
            confidence = self._calculate_confidence(
                signal_type, source_quality, recency_weight,
                sentiment_match, entity_quality
            )
            
            signal = TradingSignal(
                signal_id=f"pub_{uuid.uuid4().hex[:8]}",
                signal_type=signal_type,
                ticker=ticker,
                company_name=company_name,
                headline=title[:100],
                summary=abstract[:300],
                confidence=confidence,
                sentiment=clinical["sentiment"],
                target_upside=rules["target_upside"],
                target_downside=rules["target_downside"],
                sources=["pubmed.ncbi.nlm.nih.gov"],
                collected_at=paper.get("year", ""),
                created_at=datetime.now().isoformat(),
                source_quality=source_quality,
                recency_weight=recency_weight
            )
            
            if not self._is_duplicate(signal):
                signals.append(signal)
                logger.info(f"Generated {signal_type} signal for {ticker}")
        
        return signals
    
    def generate_from_fda(self) -> List[TradingSignal]:
        """Generate signals from FDA data"""
        logger.info("Generating signals from FDA")
        signals = []
        
        try:
            data = self.fda.collect()
        except Exception as e:
            logger.error(f"Error collecting from FDA: {e}")
            return signals
        
        # Process approvals
        for approval in data.get("approvals", []):
            ticker = self.extractor.extract_ticker(approval.get("drug_name", ""))
            
            if ticker:
                rules = self.SIGNAL_TYPES["FDA_APPROVAL"]
                
                signal = TradingSignal(
                    signal_id=f"fda_{uuid.uuid4().hex[:8]}",
                    signal_type="FDA_APPROVAL",
                    ticker=ticker,
                    company_name=approval.get("company", ""),
                    headline=f"FDA approves {approval.get('drug_name', '')}",
                    summary=approval.get("indication", "")[:300],
                    confidence=90,
                    sentiment="positive",
                    target_upside=15.0,
                    target_downside=-5.0,
                    sources=["fda.gov"],
                    collected_at=approval.get("action_date", ""),
                    created_at=datetime.now().isoformat(),
                    source_quality=1.0,
                    recency_weight=self._get_recency_weight(approval.get("action_date", ""))
                )
                
                if not self._is_duplicate(signal):
                    signals.append(signal)
                    logger.info(f"Generated FDA_APPROVAL signal for {ticker}")
        
        # Process rejections if available
        for rejection in data.get("rejections", []):
            ticker = self.extractor.extract_ticker(rejection.get("drug_name", ""))
            
            if ticker:
                signal = TradingSignal(
                    signal_id=f"fda_{uuid.uuid4().hex[:8]}",
                    signal_type="FDA_REJECTION",
                    ticker=ticker,
                    company_name=rejection.get("company", ""),
                    headline=f"FDA rejects {rejection.get('drug_name', '')}",
                    summary=rejection.get("reason", "")[:300],
                    confidence=90,
                    sentiment="negative",
                    target_upside=-20.0,
                    target_downside=-30.0,
                    sources=["fda.gov"],
                    collected_at=rejection.get("action_date", ""),
                    created_at=datetime.now().isoformat(),
                    source_quality=1.0,
                    recency_weight=self._get_recency_weight(rejection.get("action_date", ""))
                )
                
                if not self._is_duplicate(signal):
                    signals.append(signal)
                    logger.info(f"Generated FDA_REJECTION signal for {ticker}")
        
        return signals
    
    def generate_from_reddit(self) -> List[TradingSignal]:
        """Generate signals from Reddit posts"""
        logger.info("Generating signals from Reddit")
        signals = []
        
        try:
            data = self.reddit.collect()
        except Exception as e:
            logger.error(f"Error collecting from Reddit: {e}")
            return signals
        
        for post in data.get("finance", []):
            text = f"{post.get('title', '')} {post.get('selftext', '')}"
            ticker = self.extractor.extract_ticker(text)
            
            if not ticker:
                continue
            
            signal_type = self._detect_signal_type(text)
            if not signal_type:
                continue
            
            clinical = self.analyzer.get_clinical_sentiment(text)
            rules = self.SIGNAL_TYPES.get(signal_type, {})
            
            # Reddit signals have lower confidence
            source_quality = self._get_source_quality("reddit")
            recency_weight = self._get_recency_weight(post.get("created_utc", ""))
            
            # Only generate if sentiment is strong and source quality decent
            if clinical["sentiment"] in ["positive", "negative"] and source_quality >= 0.3:
                signal = TradingSignal(
                    signal_id=f"rd_{uuid.uuid4().hex[:8]}",
                    signal_type=signal_type,
                    ticker=ticker,
                    company_name=ticker,
                    headline=post.get("title", "")[:100],
                    summary=post.get("selftext", "")[:200],
                    confidence=min(70, int(clinical["confidence"] * 70)),
                    sentiment=clinical["sentiment"],
                    target_upside=rules.get("target_upside", 5.0),
                    target_downside=rules.get("target_downside", -5.0),
                    sources=["reddit.com"],
                    collected_at=post.get("created_utc", ""),
                    created_at=datetime.now().isoformat(),
                    source_quality=source_quality,
                    recency_weight=recency_weight
                )
                
                if not self._is_duplicate(signal):
                    signals.append(signal)
        
        return signals
    
    def generate_all(self, clear_cache: bool = True) -> List[TradingSignal]:
        """Generate all signals from all sources"""
        logger.info("Generating all signals")
        
        if clear_cache:
            self._signal_cache.clear()
        
        all_signals = []
        
        # Collect from all sources
        all_signals.extend(self.generate_from_pubmed())
        all_signals.extend(self.generate_from_fda())
        all_signals.extend(self.generate_from_reddit())
        
        # Advanced deduplication
        seen_signals = {}
        unique_signals = []
        
        for signal in all_signals:
            # Create composite key for more sophisticated deduplication
            key = (signal.ticker, signal.signal_type)
            
            if key not in seen_signals:
                seen_signals[key] = signal
                unique_signals.append(signal)
            else:
                # Keep the higher confidence signal
                existing = seen_signals[key]
                if signal.confidence > existing.confidence:
                    seen_signals[key] = signal
                    unique_signals[unique_signals.index(existing)] = signal
        
        # Sort by confidence
        unique_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.info(f"Generated {len(unique_signals)} unique signals")
        return unique_signals
    
    def get_signal_types(self) -> Dict:
        """Get all supported signal types"""
        return {
            signal_type: {
                "keywords": info["keywords"],
                "sentiment": info["sentiment"],
                "target_upside": info["target_upside"],
                "target_downside": info["target_downside"],
                "base_confidence": info["base_confidence"]
            }
            for signal_type, info in self.SIGNAL_TYPES.items()
        }


if __name__ == "__main__":
    generator = SignalGenerator()
    signals = generator.generate_all()
    
    print(f"\n📊 Generated {len(signals)} signals:\n")
    
    for signal in signals[:10]:
        print(f"  [{signal.signal_type}] {signal.ticker} - {signal.confidence}% confidence")
        print(f"    Source quality: {signal.source_quality:.2f} | Recency: {signal.recency_weight:.2f}")
        print(f"    {signal.headline[:60]}...")
        print()
