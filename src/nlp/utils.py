"""
NLP Utilities - Entity extraction and sentiment analysis
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import sys
sys.path.insert(0, str(__file__).replace('nlp/utils.py', ''))
from utils.config import config
from utils.logger import logger

@dataclass
class MedicalEntity:
    """Extracted medical entity"""
    text: str
    entity_type: str  # drug, company, condition, trial
    ticker: Optional[str] = None
    confidence: float = 0.0

class EntityExtractor:
    """Extract medical and financial entities from text"""
    
    # Clinical trial phase patterns
    PHASE_PATTERN = re.compile(
        r'phase\s*[IVX]+(?:\s*[\-\/]?\s*\d+)?',
        re.IGNORECASE
    )
    
    # FDA decision patterns
    FDA_PATTERN = re.compile(
        r'(FDA|approve[ds]?|rejection?|reject[ds]?|clear[eds]?|denied?|warning|orphan)',
        re.IGNORECASE
    )
    
    # Efficacy patterns
    EFFICACY_PATTERN = re.compile(
        r'(\d+(?:\.\d+)?%?)\s*(improvement|reduction|increase|decrease|efficacy|response)',
        re.IGNORECASE
    )
    
    # Company patterns
    COMPANY_PATTERNS = [
        (r'(Pfizer|Merck|Johnson[\s&]+Johnson|J&J)', 'PFE'),
        (r'(Novartis|Roche|AbbVie|AstraZeneca)', None),
        (r'(Moderna|BioNTech|Gilead)', None),
        (r'(Medtronic|Abbott|Boston Scientific)', None),
        (r'(Illumina|Danaher|Thermo Fisher)', None),
    ]
    
    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract entities from text"""
        entities = []
        
        # Extract clinical phases
        phases = self.PHASE_PATTERN.findall(text)
        for phase in phases:
            entities.append(MedicalEntity(
                text=phase.strip(),
                entity_type="trial_phase",
                confidence=0.9
            ))
        
        # Extract FDA decisions
        fda = self.FDA_PATTERN.findall(text)
        for decision in fda:
            entities.append(MedicalEntity(
                text=decision[0] if isinstance(decision, tuple) else decision,
                entity_type="fda_decision",
                confidence=0.95
            ))
        
        # Extract efficacy numbers
        efficacy = self.EFFICACY_PATTERN.findall(text)
        for match in efficacy:
            entities.append(MedicalEntity(
                text=f"{match[0]} {match[1]}",
                entity_type="efficacy",
                confidence=0.8
            ))
        
        # Map companies to tickers
        text_lower = text.lower()
        for pattern, ticker in self.COMPANY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE)
                entities.append(MedicalEntity(
                    text=match.group(0),
                    entity_type="company",
                    ticker=ticker,
                    confidence=0.9
                ))
                break
        
        return entities
    
    def extract_drugs(self, text: str) -> List[str]:
        """Extract drug names from text"""
        # Common drug name patterns
        patterns = [
            r'(?:drug|therapy|treatment|medication)[\s:]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'(?:new|investigational|experimental)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]
        
        drugs = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            drugs.extend(matches)
        
        return list(set(drugs))
    
    def extract_ticker(self, text: str) -> Optional[str]:
        """Extract ticker symbol from text"""
        ticker_match = re.search(r'\$([A-Z]{1,5})\b', text)
        if ticker_match:
            return ticker_match.group(1)
        
        # Check against known mappings
        for company, ticker in config.TICKER_MAP.items():
            if company.lower() in text.lower():
                return ticker
        
        return None


class SentimentAnalyzer:
    """Analyze sentiment of medical/financial text"""
    
    POSITIVE_KEYWORDS = [
        "improved", "effective", "successful", "positive", "benefit",
        "breakthrough", "promising", "superior", "efficacy", "response rate",
        "survival", "tolerable", "safe", "approves", "approved"
    ]
    
    NEGATIVE_KEYWORDS = [
        "failed", "failure", "adverse", "toxicity", "rejected",
        "declined", "safety concern", "worse", "inferior", "withdrawn",
        "side effect", "death", "hospitalization"
    ]
    
    NEUTRAL_KEYWORDS = [
        "ongoing", "preliminary", "mixed results", "further study"
    ]
    
    def analyze(self, text: str) -> Tuple[str, float]:
        """
        Analyze sentiment of medical text
        
        Returns: (sentiment, confidence)
        sentiment: positive, negative, or neutral
        confidence: 0.0 to 1.0
        """
        text_lower = text.lower()
        
        pos_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text_lower)
        neg_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text_lower)
        neu_count = sum(1 for kw in self.NEUTRAL_KEYWORDS if kw in text_lower)
        
        total = pos_count + neg_count + neu_count
        
        if total == 0:
            return "neutral", 0.5
        
        pos_score = pos_count / total
        neg_score = neg_count / total
        neu_score = neu_count / total
        
        if pos_score > neg_score and pos_score > 0.3:
            return "positive", min(0.5 + pos_score, 0.95)
        elif neg_score > pos_score and neg_score > 0.3:
            return "negative", min(0.5 + neg_score, 0.95)
        else:
            return "neutral", 0.6
    
    def get_clinical_sentiment(self, text: str) -> Dict:
        """Get detailed clinical sentiment"""
        sentiment, confidence = self.analyze(text)
        
        # Check for specific clinical indicators
        text_lower = text.lower()
        
        # Trial outcomes
        if "primary endpoint met" in text_lower:
            trial_sentiment = "success"
            trial_confidence = 0.95
        elif "primary endpoint not met" in text_lower:
            trial_sentiment = "failure"
            trial_confidence = 0.95
        elif any(kw in text_lower for kw in ["phase 3", "phase iii", "pivotal trial"]):
            trial_sentiment = "registration"
            trial_confidence = 0.8
        elif any(kw in text_lower for kw in ["phase 2", "phase ii"]):
            trial_sentiment = "mid-stage"
            trial_confidence = 0.7
        else:
            trial_sentiment = "unknown"
            trial_confidence = 0.5
        
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "trial_sentiment": trial_sentiment,
            "trial_confidence": trial_confidence,
            "positive_signals": self.POSITIVE_KEYWORDS[:5],
            "negative_signals": self.NEGATIVE_KEYWORDS[:5]
        }


if __name__ == "__main__":
    extractor = EntityExtractor()
    analyzer = SentimentAnalyzer()
    
    sample = """
    Pfizer's Phase 3 trial for breast cancer showed 45% improvement 
    in progression-free survival. FDA approved the drug.
    """
    
    print("Entities:", extractor.extract_entities(sample))
    print("\nSentiment:", analyzer.analyze(sample))
    print("\nClinical:", analyzer.get_clinical_sentiment(sample))
