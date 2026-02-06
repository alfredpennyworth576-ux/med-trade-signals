"""
Confidence Scoring System
Builds confidence scores for trading signals based on multiple factors.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import math
import sys
sys.path.insert(0, str(__file__).replace('signals/confidence.py', ''))


@dataclass
class ConfidenceFactors:
    """Breakdown of confidence factors"""
    source_reliability: float = 0.0  # 0-1
    entity_quality: float = 0.0  # 0-1
    sentiment_strength: float = 0.0  # 0-1
    recency_score: float = 0.0  # 0-1
    market_impact: float = 0.0  # 0-1
    confirmation_count: float = 0.0  # 0-1 (multiple sources)
    historical_accuracy: float = 0.5  # 0-1


class ConfidenceScorer:
    """
    Calculate confidence scores for trading signals.
    
    Input: entity extraction + sentiment + source quality + recency
    Output: confidence score 0-100
    
    Factors:
    - source_reliability: How trustworthy is the source
    - entity_quality: Quality of extracted entities (ticker, company)
    - sentiment_strength: How strong is the sentiment signal
    - recency_score: How recent is the information
    - market_impact: Expected market impact of the event
    - confirmation_count: Multiple independent sources confirm
    - historical_accuracy: Track record of similar signals
    """
    
    # Source reliability weights
    SOURCE_RELIABILITY = {
        # Government/Regulatory (highest)
        "fda.gov": 1.0,
        "sec.gov": 1.0,
        "nih.gov": 0.95,
        "cdc.gov": 0.95,
        
        # Academic/Medical (very high)
        "pubmed.ncbi.nlm.nih.gov": 0.95,
        "nejm.org": 0.95,
        "lancet.com": 0.95,
        "nature.com": 0.9,
        "jama.org": 0.9,
        "biomedcentral.com": 0.85,
        
        # Financial News (high)
        "reuters.com": 0.9,
        "bloomberg.com": 0.85,
        "wsj.com": 0.85,
        "financialtimes.com": 0.85,
        "marketwatch.com": 0.75,
        
        # General News (medium)
        "cnn.com": 0.7,
        "bbc.com": 0.7,
        "nytimes.com": 0.7,
        "washingtonpost.com": 0.7,
        
        # Social/Community (lower)
        "reddit.com": 0.4,
        "twitter.com": 0.3,
        "stocktwits.com": 0.25,
        "investorhub": 0.25,
        
        # Unknown/default
        "default": 0.5
    }
    
    # Signal type impact weights
    SIGNAL_IMPACT_WEIGHTS = {
        "FDA_APPROVAL": 0.9,
        "FDA_REJECTION": 0.95,
        "FDA_WARNING": 0.7,
        "TRIAL_SUCCESS": 0.85,
        "TRIAL_FAILURE": 0.9,
        "TRIAL_PHASE_ADVANCE": 0.6,
        "SEC_FILING": 0.4,
        "PRICE_TARGET_CHANGE": 0.5,
        "UPGRADE_DOWNGRADE": 0.55,
        "INSIDER_BUYING": 0.5
    }
    
    # Recency decay parameters
    RECENCY_HALF_LIFE_HOURS = 24  # Half-life in hours
    MAX_AGE_HOURS = 168  # 1 week max
    
    def __init__(self, historical_tracker: Optional[Dict] = None):
        self.historical_tracker = historical_tracker or {}
    
    def get_source_reliability(self, source: str) -> float:
        """Get reliability score for a source"""
        source_lower = source.lower()
        
        for known_source, score in self.SOURCE_RELIABILITY.items():
            if known_source in source_lower:
                return score
        
        return self.SOURCE_RELIABILITY["default"]
    
    def get_source_reliability_multiple(self, sources: List[str]) -> float:
        """Calculate average reliability across multiple sources"""
        if not sources:
            return 0.3  # Default for no sources
        
        scores = [self.get_source_reliability(s) for s in sources]
        avg_score = sum(scores) / len(scores)
        
        # Bonus for multiple sources
        if len(sources) > 1:
            # Max bonus of 0.1 for 3+ sources
            bonus = min(0.1, (len(sources) - 1) * 0.05)
            avg_score += bonus
        
        return min(1.0, avg_score)
    
    def get_recency_score(self, timestamp: str) -> float:
        """Calculate recency score based on age"""
        try:
            # Parse timestamp
            if timestamp:
                collected_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                now = datetime.now()
                age_hours = (now - collected_date).total_seconds / 3600
            else:
                age_hours = 0
        except (ValueError, AttributeError):
            age_hours = 24  # Default to 24 hours old
        
        # Exponential decay
        if age_hours < 0:
            return 1.0  # Future dates
        
        if age_hours > self.MAX_AGE_HOURS:
            return 0.1  # Very old
        
        # Decay formula: e^(-ln(2) * age / half_life)
        decay = math.exp(-math.log(2) * age_hours / self.RECENCY_HALF_LIFE_HOURS)
        return max(0.1, decay)
    
    def get_entity_quality(self, ticker: str, company_name: str) -> float:
        """Score quality of extracted entities"""
        score = 0.5  # Base score
        
        # Valid ticker format (basic check)
        if ticker and len(ticker) >= 1 and len(ticker) <= 5:
            score += 0.2
        
        # Company name present and reasonable length
        if company_name and len(company_name) > 2 and len(company_name) < 100:
            score += 0.2
        
        # Ticker matches company pattern (all caps)
        if ticker and ticker.isupper():
            score += 0.1
        
        return min(1.0, score)
    
    def get_sentiment_strength(self, sentiment: str, confidence: float) -> float:
        """
        Calculate sentiment strength score.
        
        Args:
            sentiment: 'positive', 'negative', 'neutral'
            confidence: 0-1 confidence in sentiment
        """
        base = confidence
        
        if sentiment in ["positive", "negative"]:
            base += 0.1  # Strong sentiment bonus
        else:
            base -= 0.1  # Neutral penalty
        
        return max(0.0, min(1.0, base))
    
    def get_market_impact(self, signal_type: str) -> float:
        """Get expected market impact for signal type"""
        return self.SIGNAL_IMPACT_WEIGHTS.get(signal_type, 0.5)
    
    def get_confirmation_score(self, source_count: int, 
                               source_diversity: float) -> float:
        """
        Score based on multiple confirmations.
        
        Args:
            source_count: Number of independent sources
            source_diversity: How different are the sources (0-1)
        """
        if source_count == 0:
            return 0.2
        elif source_count == 1:
            return 0.5
        elif source_count == 2:
            return 0.7 + (source_diversity * 0.1)
        else:  # 3+
            return 0.9 + (source_diversity * 0.1)
    
    def calculate_confidence(
        self,
        sources: List[str],
        sentiment: str,
        sentiment_confidence: float,
        timestamp: str,
        ticker: str,
        company_name: str,
        signal_type: str,
        historical_accuracy: Optional[float] = None,
        source_count: int = None,
        source_diversity: float = 0.5
    ) -> Tuple[int, ConfidenceFactors]:
        """
        Calculate overall confidence score (0-100).
        
        Args:
            sources: List of source URLs/identifiers
            sentiment: Detected sentiment
            sentiment_confidence: Confidence in sentiment (0-1)
            timestamp: When the information was collected
            ticker: Extracted ticker symbol
            company_name: Extracted company name
            signal_type: Type of signal
            historical_accuracy: Historical accuracy for this signal type (optional)
            source_count: Number of sources (defaults to len(sources))
            source_diversity: Diversity of sources 0-1
        
        Returns:
            Tuple of (confidence_score, ConfidenceFactors breakdown)
        """
        factors = ConfidenceFactors()
        
        # Calculate individual factors
        factors.source_reliability = self.get_source_reliability_multiple(sources)
        factors.recency_score = self.get_recency_score(timestamp)
        factors.entity_quality = self.get_entity_quality(ticker, company_name)
        factors.sentiment_strength = self.get_sentiment_strength(
            sentiment, sentiment_confidence
        )
        factors.market_impact = self.get_market_impact(signal_type)
        
        count = source_count if source_count is not None else len(sources)
        factors.confirmation_count = self.get_confirmation_score(count, source_diversity)
        
        if historical_accuracy is not None:
            factors.historical_accuracy = historical_accuracy
        else:
            # Default based on signal type
            factors.historical_accuracy = 0.6
        
        # Weighted combination
        weights = {
            "source_reliability": 0.25,
            "recency_score": 0.20,
            "entity_quality": 0.15,
            "sentiment_strength": 0.15,
            "market_impact": 0.10,
            "confirmation_count": 0.10,
            "historical_accuracy": 0.05
        }
        
        raw_score = sum(
            getattr(factors, key) * weight
            for key, weight in weights.items()
        )
        
        # Scale to 0-100
        confidence = int(raw_score * 100)
        confidence = min(95, max(5, confidence))  # Clamp to reasonable bounds
        
        return confidence, factors
    
    def calculate_from_signal(self, signal: Dict) -> Tuple[int, ConfidenceFactors]:
        """Calculate confidence from a signal dictionary"""
        return self.calculate_confidence(
            sources=signal.get("sources", []),
            sentiment=signal.get("sentiment", "neutral"),
            sentiment_confidence=signal.get("confidence", 50) / 100,
            timestamp=signal.get("collected_at", ""),
            ticker=signal.get("ticker", ""),
            company_name=signal.get("company_name", ""),
            signal_type=signal.get("signal_type", ""),
            source_count=len(signal.get("sources", []))
        )
    
    def get_confidence_breakdown(self, factors: ConfidenceFactors) -> Dict:
        """Get human-readable breakdown of confidence factors"""
        return {
            "source_reliability": {
                "score": factors.source_reliability,
                "rating": self._get_rating(factors.source_reliability),
                "weight": 0.25
            },
            "recency_score": {
                "score": factors.recency_score,
                "rating": self._get_rating(factors.recency_score),
                "weight": 0.20
            },
            "entity_quality": {
                "score": factors.entity_quality,
                "rating": self._get_rating(factors.entity_quality),
                "weight": 0.15
            },
            "sentiment_strength": {
                "score": factors.sentiment_strength,
                "rating": self._get_rating(factors.sentiment_strength),
                "weight": 0.15
            },
            "market_impact": {
                "score": factors.market_impact,
                "rating": self._get_rating(factors.market_impact),
                "weight": 0.10
            },
            "confirmation_count": {
                "score": factors.confirmation_count,
                "rating": self._get_rating(factors.confirmation_count),
                "weight": 0.10
            },
            "historical_accuracy": {
                "score": factors.historical_accuracy,
                "rating": self._get_rating(factors.historical_accuracy),
                "weight": 0.05
            }
        }
    
    def _get_rating(self, score: float) -> str:
        """Convert score to rating"""
        if score >= 0.9:
            return "Excellent"
        elif score >= 0.75:
            return "Very Good"
        elif score >= 0.6:
            return "Good"
        elif score >= 0.4:
            return "Fair"
        elif score >= 0.25:
            return "Poor"
        else:
            return "Very Poor"
    
    def get_recommendation(self, confidence: int, sentiment: str) -> str:
        """Get trading recommendation based on confidence and sentiment"""
        if confidence >= 80:
            strength = "Strong"
        elif confidence >= 60:
            strength = "Moderate"
        elif confidence >= 40:
            strength = "Weak"
        else:
            return "LOW CONFIDENCE - Monitor only"
        
        direction = "Bullish" if sentiment == "positive" else "Bearish" if sentiment == "negative" else "Neutral"
        
        return f"{strength} {direction} Signal"


# Convenience function
def calculate_signal_confidence(**kwargs) -> Tuple[int, ConfidenceFactors]:
    """Quick function to calculate confidence"""
    scorer = ConfidenceScorer()
    return scorer.calculate_confidence(**kwargs)


if __name__ == "__main__":
    # Demo
    scorer = ConfidenceScorer()
    
    # Test signal
    confidence, factors = scorer.calculate_confidence(
        sources=["fda.gov", "reuters.com"],
        sentiment="positive",
        sentiment_confidence=0.85,
        timestamp="2026-02-06T08:00:00",
        ticker="MRNA",
        company_name="Moderna Inc",
        signal_type="FDA_APPROVAL",
        source_count=2,
        source_diversity=0.8
    )
    
    print(f"Confidence Score: {confidence}/100")
    print(f"\nFactors:")
    print(f"  Source Reliability: {factors.source_reliability:.2f}")
    print(f"  Recency Score: {factors.recency_score:.2f}")
    print(f"  Entity Quality: {factors.entity_quality:.2f}")
    print(f"  Sentiment Strength: {factors.sentiment_strength:.2f}")
    print(f"  Market Impact: {factors.market_impact:.2f}")
    print(f"  Confirmation Count: {factors.confirmation_count:.2f}")
    print(f"  Historical Accuracy: {factors.historical_accuracy:.2f}")
    
    print(f"\nRecommendation: {scorer.get_recommendation(confidence, 'positive')}")
