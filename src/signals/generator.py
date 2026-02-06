"""
Signal Generator - Create trading signals from medical news
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
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
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)


class SignalGenerator:
    """Generate trading signals from medical data"""
    
    SIGNAL_TYPES = {
        "FDA_APPROVAL": {
            "keywords": ["fda approves", "fda approved", "approval"],
            "sentiment": "positive",
            "target_upside": 15.0,
            "target_downside": -5.0,
            "base_confidence": 85
        },
        "FDA_REJECTION": {
            "keywords": ["fda rejects", "fda rejected", "rejection"],
            "sentiment": "negative",
            "target_upside": -20.0,
            "target_downside": -30.0,
            "base_confidence": 90
        },
        "TRIAL_SUCCESS": {
            "keywords": ["primary endpoint met", "met primary endpoint", "successful trial"],
            "sentiment": "positive",
            "target_upside": 12.0,
            "target_downside": -3.0,
            "base_confidence": 75
        },
        "TRIAL_FAILURE": {
            "keywords": ["primary endpoint not met", "failed trial", "study failed"],
            "sentiment": "negative",
            "target_upside": -15.0,
            "target_downside": -25.0,
            "base_confidence": 80
        },
        "PRICE_TARGET_UP": {
            "keywords": ["price target raised", "upgraded", "bullish"],
            "sentiment": "positive",
            "target_upside": 8.0,
            "target_downside": -2.0,
            "base_confidence": 70
        }
    }
    
    def __init__(self):
        self.extractor = EntityExtractor()
        self.analyzer = SentimentAnalyzer()
        self.pubmed = PubMedCollector()
        self.fda = FDACollector()
        self.reddit = RedditCollector()
    
    def generate_from_pubmed(self, query: str = "AI medical imaging") -> List[TradingSignal]:
        """Generate signals from PubMed papers"""
        logger.info("Generating signals from PubMed")
        signals = []
        
        papers = self.pubmed.collect(query)
        
        for paper in papers:
            # Analyze the paper
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            text = f"{title} {abstract}"
            
            # Check for signal types
            for signal_type, rules in self.SIGNAL_TYPES.items():
                if any(kw in text.lower() for kw in rules["keywords"]):
                    # Extract entities
                    ticker = self.extractor.extract_ticker(text)
                    entities = self.extractor.extract_entities(text)
                    
                    # Analyze sentiment
                    clinical = self.analyzer.get_clinical_sentiment(text)
                    
                    # Calculate confidence
                    confidence = rules["base_confidence"]
                    if clinical["sentiment"] == rules["sentiment"]:
                        confidence += 10
                    confidence = min(95, max(50, confidence))
                    
                    if ticker:
                        signal = TradingSignal(
                            signal_id=f"pub_{uuid.uuid4().hex[:8]}",
                            signal_type=signal_type,
                            ticker=ticker,
                            company_name=ticker,  # Would need enrichment
                            headline=title[:100],
                            summary=abstract[:300],
                            confidence=confidence,
                            sentiment=clinical["sentiment"],
                            target_upside=rules["target_upside"],
                            target_downside=rules["target_downside"],
                            sources=["pubmed.ncbi.nlm.nih.gov"],
                            collected_at=paper.get("year", ""),
                            created_at=datetime.now().isoformat()
                        )
                        signals.append(signal)
                        logger.info(f"Generated {signal_type} signal for {ticker}")
        
        return signals
    
    def generate_from_fda(self) -> List[TradingSignal]:
        """Generate signals from FDA data"""
        logger.info("Generating signals from FDA")
        signals = []
        
        data = self.fda.collect()
        
        # Process approvals
        for approval in data.get("approvals", []):
            ticker = self.extractor.extract_ticker(approval.get("drug_name", ""))
            
            if ticker:
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
                    created_at=datetime.now().isoformat()
                )
                signals.append(signal)
                logger.info(f"Generated FDA_APPROVAL signal for {ticker}")
        
        return signals
    
    def generate_from_reddit(self) -> List[TradingSignal]:
        """Generate signals from Reddit posts"""
        logger.info("Generating signals from Reddit")
        signals = []
        
        data = self.reddit.collect()
        
        for post in data.get("finance", []):
            text = f"{post.get('title', '')} {post.get('selftext', '')}"
            ticker = self.extractor.extract_ticker(text)
            
            if ticker:
                clinical = self.analyzer.get_clinical_sentiment(text)
                
                # Only generate if sentiment is strong
                if clinical["sentiment"] in ["positive", "negative"]:
                    signal = TradingSignal(
                        signal_id=f"rd_{uuid.uuid4().hex[:8]}",
                        signal_type="REDDIT_SENTIMENT",
                        ticker=ticker,
                        company_name=ticker,
                        headline=post.get("title", "")[:100],
                        summary=post.get("selftext", "")[:200],
                        confidence=min(70, clinical["confidence"] * 100),
                        sentiment=clinical["sentiment"],
                        target_upside=5.0 if clinical["sentiment"] == "positive" else -5.0,
                        target_downside=-5.0 if clinical["sentiment"] == "positive" else 5.0,
                        sources=["reddit.com"],
                        collected_at=post.get("created_utc", ""),
                        created_at=datetime.now().isoformat()
                    )
                    signals.append(signal)
        
        return signals
    
    def generate_all(self) -> List[TradingSignal]:
        """Generate all signals from all sources"""
        logger.info("Generating all signals")
        
        all_signals = []
        
        # Collect from all sources
        all_signals.extend(self.generate_from_pubmed())
        all_signals.extend(self.generate_from_fda())
        all_signals.extend(self.generate_from_reddit())
        
        # Remove duplicates (same ticker, same day)
        seen = set()
        unique_signals = []
        for signal in all_signals:
            key = (signal.ticker, signal.signal_type[:10], signal.created_at[:10])
            if key not in seen:
                seen.add(key)
                unique_signals.append(signal)
        
        # Sort by confidence
        unique_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.info(f"Generated {len(unique_signals)} unique signals")
        return unique_signals


if __name__ == "__main__":
    generator = SignalGenerator()
    signals = generator.generate_all()
    
    print(f"\n📊 Generated {len(signals)} signals:\n")
    
    for signal in signals[:5]:
        print(f"  [{signal.signal_type}] {signal.ticker} - {signal.confidence}% confidence")
        print(f"    {signal.headline[:60]}...")
