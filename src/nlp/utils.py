"""
NLP Utilities - Enhanced Entity extraction and sentiment analysis
"""
import re
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import json
import hashlib
import sys
sys.path.insert(0, str(__file__).replace('nlp/utils.py', ''))
from utils.config import config
from utils.logger import logger

@dataclass
class MedicalEntity:
    """Extracted medical entity"""
    text: str
    entity_type: str  # drug, company, condition, trial, biomarker, indication
    ticker: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ClinicalTrial:
    """Parsed clinical trial information"""
    phase: Optional[str] = None
    condition: Optional[str] = None
    intervention: Optional[str] = None
    sponsor: Optional[str] = None
    enrollment: Optional[int] = None
    trial_id: Optional[str] = None
    endpoints: List[str] = field(default_factory=list)
    outcomes: Dict[str, Any] = field(default_factory=dict)


class EnhancedEntityExtractor:
    """Enhanced entity extraction with better patterns and resolution"""
    
    # ===== CLINICAL TRIAL PATTERNS =====
    CLINICAL_TRIAL_PATTERNS = {
        # NCT Number pattern
        'nct_id': re.compile(r'\bNCT[0-9]{8,}\b', re.IGNORECASE),
        
        # Phase patterns (enhanced)
        'phase': re.compile(
            r'(?:Phase|phase|Pivotal|Early[\s-]?phase|Registration)\s*([IVX]+(?:\s*[\-\/]?\s*\d+)?)'
        ),
        
        # Trial status
        'status': re.compile(
            r'\b(recruiting|completed|terminated|suspended|withdrawn|active|not yet recruiting|ongoing)\b',
            re.IGNORECASE
        ),
        
        # Enrollment patterns
        'enrollment': re.compile(
            r'(\d{1,3}(?:,\d{3})*|\d+)\s*(?:participants?|patients?|subjects?|enrolled)\b',
            re.IGNORECASE
        ),
        
        # Endpoint patterns
        'endpoint': re.compile(
            r'(primary|secondary)\s*(?:endpoint|end point)[:\s]+([^.]+(?:\([^)]+\))?)',
            re.IGNORECASE
        ),
        
        # Hazard ratio / efficacy
        'hazard_ratio': re.compile(
            r'HR\s*=?\s*(\d+\.?\d*)\s*(?:\(?(?:95%?\s*CI|confidence\s*interval)[^\)]*\)?)?'
        ),
        'relative_risk': re.compile(
            r'RR\s*=?\s*(\d+\.?\d*)'
        ),
        'odds_ratio': re.compile(
            r'OR\s*=?\s*(\d+\.?\d*)'
        ),
    }
    
    # ===== FDA REGULATORY PATTERNS =====
    FDA_PATTERNS = {
        'decision': re.compile(
            r'(FDA|(?:US)\s*FDA)\s*(?:granted|issued|approved|rejected|accepted|denied|cleared|classified)\s*(?:approval|clearance|authorization)?\s*(?:for|of)?\s*([^\.]+)',
            re.IGNORECASE
        ),
        'approval_path': re.compile(
            r'(accelerated|conditional|regular|priority|breakthrough|orphan)\s*(?:approval|review|pathway|designation)',
            re.IGNORECASE
        ),
        'advisory_committee': re.compile(
            r'(FDA\s*)?Advisory\s*Committee\s*(?:voted|recommended|endorsed)\s*(?:for|against)?\s*([^.]+)',
            re.IGNORECASE
        ),
    }
    
    # ===== DRUG/THERAPY PATTERNS =====
    DRUG_PATTERNS = {
        'generic_name': re.compile(
            r'(?:drug|therapy|treatment|medication|agent|inhibitor|antibody|vaccine)\s*(?:name)?\s*[:\-\s]+([A-Z][a-z]+(?:\s+(?:hydrochloride|sulfate|sodium|potassium))?)',
            re.IGNORECASE
        ),
        'brand_name': re.compile(
            r'\b([A-Z][a-z]{2,})\s*(?:TM|®|℠)?\b'
        ),
        'mechanism': re.compile(
            r'(?:MOA|mechanism\s*(?:of\s*action)?)[:\s]+([^.]+)',
            re.IGNORECASE
        ),
    }
    
    # ===== EFFICACY/SAFETY PATTERNS =====
    EFFICACY_PATTERNS = {
        'percentage_change': re.compile(
            r'(\d+(?:\.\d+)?%?)\s*(?:improvement|reduction|increase|decrease|change|difference|mortality|response|survival)'
        ),
        'absolute_numbers': re.compile(
            r'(\d+(?:\.\d+)?%?)\s*(?:vs\.?|versus|compared\s*to)\s*(\d+(?:\.\d+)?%?)'
        ),
        'p_value': re.compile(
            r'p(?:\-|\s*)?(?:value)?\s*[≤=<>]\s*(\d+\.?\d*(?:e[\-\+]?\d+)?)'
        ),
        'median_survival': re.compile(
            r'median\s*(?:overall\s*)?(?:progression[\-\s]?free\s*)?survival\s*[:\s]+(\d+(?:\.\d+)?)\s*(months?|yrs?|years?)',
            re.IGNORECASE
        ),
    }
    
    # ===== ENHANCED COMPANY PATTERNS =====
    COMPANY_PATTERNS = [
        # Major Pharma
        (r'\bPfizer\b', 'PFE'),
        (r'\bMerck\b(?!\s+Research)', 'MRK'),
        (r'\bJohnson\s*&\s*Johnson\b', 'JNJ'),
        (r'\bJ&J\b', 'JNJ'),
        (r'\bAbbVie\b', 'ABBV'),
        (r'\bBristol[\s-]?Myers\s*Squibb\b', 'BMY'),
        (r'\bBMS\b', 'BMY'),
        (r'\bNovartis\b', 'NVS'),
        (r'\bRoche\b', 'RHHBY'),
        (r'\bSanofi\b', 'SNY'),
        (r'\bAstraZeneca\b', 'AZN'),
        (r'\bGlaxoSmithKline\b', 'GSK'),
        (r'\bGSK\b', 'GSK'),
        (r'\bAmgen\b', 'AMGN'),
        (r'\bGilead\s*Sciences\b', 'GILD'),
        (r'\bRegeneron\b', 'REGN'),
        (r'\bModerna\b', 'MRNA'),
        (r'\bBioNTech\b', 'BNTX'),
        (r'\bVertex\b', 'VRTX'),
        (r'\bIllumina\b', 'ILMN'),
        (r'\bDanaher\b', 'DHR'),
        (r'\bThermo\s*Fisher\b', 'TMO'),
        # Medical Devices
        (r'\bMedtronic\b', 'MDT'),
        (r'\bAbbott\s*(?:Laboratories)?\b', 'ABT'),
        (r'\bBoston\s*Scientific\b', 'BSX'),
        (r'\bStryker\b', 'SYK'),
        (r'\bGE\s*Healthcare\b', 'GEHC'),
        (r'\bPhilips\b', 'PHG'),
        # Biotech
        (r'\bBiogen\b', 'BIIB'),
        (r'\bAlexion\b', 'ALXN'),
        (r'\bIncyte\b', 'INCY'),
        (r'\bJazz\s*Pharmaceuticals\b', 'JAZZ'),
        (r'\bAlnylam\b', 'ALNY'),
        (r'\bBluebird\b', 'BLUE'),
        (r'\bCRISPR\s*Therapeutics\b', 'CRSP'),
        (r'\bIntellia\b', 'NTLA'),
        (r'\bEditas\b', 'EDIT'),
    ]
    
    # ===== CONDITION/DISEASE PATTERNS =====
    CONDITION_PATTERNS = [
        (r'\bcancer\b', 'cancer'),
        (r'\bcarcinoma\b', 'cancer'),
        (r'\btumor\b', 'cancer'),
        (r'\bleukemia\b', 'blood_cancer'),
        (r'\blymphoma\b', 'blood_cancer'),
        (r'\bdiabetes\b', 'diabetes'),
        (r'\bcardiovascular\b', 'cardiovascular'),
        (r'\bheart\s*disease\b', 'cardiovascular'),
        (r'\bstroke\b', 'cardiovascular'),
        (r'\bhypertension\b', 'cardiovascular'),
        (r'\bAlzheimer(?:\'s)?\b', 'alzheimers'),
        (r'\bdementia\b', 'dementia'),
        (r'\bParkinson\b', 'parkinsons'),
        (r'\bmultiple\s*sclerosis\b', 'MS'),
        (r'\bMS\b', 'MS'),
        (r'\bRA\b', 'rheumatoid_arthritis'),
        (r'\brheumatoid\s*arthritis\b', 'rheumatoid_arthritis'),
        (r'\bCOPD\b', 'COPD'),
        (r'\basthma\b', 'asthma'),
        (r'\bCOVID\b', 'COVID-19'),
        (r'\bSARS[\-\s]?CoV[\-\s]?2\b', 'COVID-19'),
    ]
    
    def __init__(self):
        self.cache = {}
    
    def extract_entities(self, text: str) -> List[MedicalEntity]:
        """Extract all entities from text"""
        entities = []
        
        # Extract clinical trial info
        trial_info = self.extract_trial_info(text)
        if trial_info.trial_id:
            entities.append(MedicalEntity(
                text=trial_info.trial_id,
                entity_type="trial_id",
                confidence=0.95,
                metadata={"phase": trial_info.phase}
            ))
        
        # Extract companies
        companies = self.extract_companies(text)
        entities.extend(companies)
        
        # Extract FDA decisions
        fda_entities = self.extract_fda_decisions(text)
        entities.extend(fda_entities)
        
        # Extract efficacy data
        efficacy = self.extract_efficacy(text)
        entities.extend(efficacy)
        
        # Extract conditions
        conditions = self.extract_conditions(text)
        entities.extend(conditions)
        
        # Extract trial phases
        phases = self.extract_phases(text)
        entities.extend(phases)
        
        return entities
    
    def extract_trial_info(self, text: str) -> ClinicalTrial:
        """Parse clinical trial information from text"""
        trial = ClinicalTrial()
        
        # Extract NCT ID
        nct_match = self.CLINICAL_TRIAL_PATTERNS['nct_id'].search(text)
        if nct_match:
            trial.trial_id = nct_match.group(0)
        
        # Extract phase
        phase_match = self.CLINICAL_TRIAL_PATTERNS['phase'].search(text)
        if phase_match:
            trial.phase = phase_match.group(1).strip()
        
        # Extract enrollment
        enroll_match = self.CLINICAL_TRIAL_PATTERNS['enrollment'].search(text)
        if enroll_match:
            try:
                num_str = enroll_match.group(1).replace(',', '')
                trial.enrollment = int(num_str)
            except ValueError:
                pass
        
        # Extract endpoints
        for match in self.CLINICAL_TRIAL_PATTERNS['endpoint'].finditer(text):
            endpoint_type = match.group(1).lower()
            endpoint_text = match.group(2).strip()
            trial.endpoints.append(f"{endpoint_type}: {endpoint_text}")
        
        # Extract hazard ratio
        hr_match = self.CLINICAL_TRIAL_PATTERNS['hazard_ratio'].search(text)
        if hr_match:
            try:
                trial.outcomes['hazard_ratio'] = float(hr_match.group(1))
            except ValueError:
                pass
        
        return trial
    
    def extract_companies(self, text: str) -> List[MedicalEntity]:
        """Extract company entities with ticker resolution"""
        entities = []
        text_lower = text.lower()
        
        for pattern, ticker in self.COMPANY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE)
                entities.append(MedicalEntity(
                    text=match.group(0),
                    entity_type="company",
                    ticker=ticker,
                    confidence=0.95,
                    metadata={"source": "pattern_matching"}
                ))
                break  # Only match first company to avoid duplicates
        
        # Fallback: check config ticker map
        for company, ticker in config.TICKER_MAP.items():
            if company.lower() in text_lower:
                if not any(e.ticker == ticker for e in entities):
                    entities.append(MedicalEntity(
                        text=company,
                        entity_type="company",
                        ticker=ticker,
                        confidence=0.85,
                        metadata={"source": "config_mapping"}
                    ))
        
        return entities
    
    def extract_fda_decisions(self, text: str) -> List[MedicalEntity]:
        """Extract FDA decision information"""
        entities = []
        
        for label, pattern in self.FDA_PATTERNS.items():
            for match in pattern.finditer(text):
                if label == 'decision':
                    entities.append(MedicalEntity(
                        text=match.group(0),
                        entity_type="fda_decision",
                        confidence=0.9,
                        metadata={
                            "decision": match.group(1) if len(match.groups()) > 1 else None,
                            "drug": match.group(2) if len(match.groups()) > 2 else None
                        }
                    ))
                elif label == 'approval_path':
                    entities.append(MedicalEntity(
                        text=match.group(0),
                        entity_type="approval_pathway",
                        confidence=0.85
                    ))
                elif label == 'advisory_committee':
                    entities.append(MedicalEntity(
                        text=match.group(0),
                        entity_type="advisory_committee",
                        confidence=0.85
                    ))
        
        return entities
    
    def extract_efficacy(self, text: str) -> List[MedicalEntity]:
        """Extract efficacy and safety data"""
        entities = []
        
        # Percentage changes
        for match in self.EFFICACY_PATTERNS['percentage_change'].finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type="efficacy_metric",
                confidence=0.8,
                metadata={"value": match.group(1)}
            ))
        
        # Absolute comparisons
        for match in self.EFFICACY_PATTERNS['absolute_numbers'].finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type="comparative_efficacy",
                confidence=0.8,
                metadata={
                    "treatment": match.group(1),
                    "control": match.group(2)
                }
            ))
        
        # P-values
        for match in self.EFFICACY_PATTERNS['p_value'].finditer(text):
            entities.append(MedicalEntity(
                text=f"p={match.group(1)}",
                entity_type="statistical_significance",
                confidence=0.9,
                metadata={"p_value": match.group(1)}
            ))
        
        # Median survival
        for match in self.EFFICACY_PATTERNS['median_survival'].finditer(text):
            entities.append(MedicalEntity(
                text=match.group(0),
                entity_type="survival_metric",
                confidence=0.85,
                metadata={
                    "value": match.group(1),
                    "unit": match.group(2)
                }
            ))
        
        return entities
    
    def extract_phases(self, text: str) -> List[MedicalEntity]:
        """Extract clinical trial phases"""
        entities = []
        
        for match in self.CLINICAL_TRIAL_PATTERNS['phase'].finditer(text):
            phase = match.group(1).strip()
            entities.append(MedicalEntity(
                text=f"Phase {phase}",
                entity_type="trial_phase",
                confidence=0.9,
                metadata={"phase": phase}
            ))
        
        return entities
    
    def extract_conditions(self, text: str) -> List[MedicalEntity]:
        """Extract disease conditions"""
        entities = []
        
        for pattern, condition_type in self.CONDITION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE)
                entities.append(MedicalEntity(
                    text=match.group(0),
                    entity_type="condition",
                    confidence=0.85,
                    metadata={"category": condition_type}
                ))
        
        return entities
    
    def resolve_entity(self, entity: MedicalEntity, context: str) -> MedicalEntity:
        """Resolve entity using context and additional sources"""
        # For now, just return as-is
        # Could be extended to use entity_db for resolution
        return entity


class EnhancedSentimentAnalyzer:
    """Enhanced sentiment analysis with clinical focus"""
    
    POSITIVE_KEYWORDS = {
        "breakthrough": 0.9,
        "promising": 0.85,
        "efficacy": 0.75,
        "effective": 0.8,
        "improved": 0.75,
        "superior": 0.85,
        "statistically significant": 0.9,
        "primary endpoint met": 0.95,
        "survival benefit": 0.9,
        "response rate": 0.7,
        "tolerable": 0.6,
        "favorable": 0.75,
        "approves": 0.9,
        "approved": 0.9,
        "positive": 0.7,
        "benefit": 0.7,
        "success": 0.85,
        "successful": 0.85,
    }
    
    NEGATIVE_KEYWORDS = {
        "failed": -0.85,
        "failure": -0.85,
        "adverse": -0.7,
        "toxicity": -0.75,
        "rejected": -0.9,
        "rejection": -0.9,
        "safety concern": -0.8,
        "death": -0.95,
        "hospitalization": -0.7,
        "withdrawn": -0.8,
        "terminated": -0.8,
        "worse": -0.75,
        "inferior": -0.8,
        "not met": -0.85,
        "negative": -0.7,
        "delayed": -0.5,
        "discontinued": -0.8,
        "side effect": -0.6,
    }
    
    NEUTRAL_KEYWORDS = {
        "ongoing": 0.0,
        "preliminary": 0.0,
        "mixed results": 0.0,
        "further study": 0.0,
        "interim analysis": 0.1,
        "exploratory": 0.0,
    }
    
    def analyze(self, text: str) -> Tuple[str, float]:
        """
        Analyze sentiment of medical text
        
        Returns: (sentiment, confidence)
        """
        text_lower = text.lower()
        
        # Calculate weighted sentiment
        total_weight = 0
        sentiment_score = 0
        
        for keyword, weight in self.POSITIVE_KEYWORDS.items():
            if keyword in text_lower:
                count = text_lower.count(keyword)
                sentiment_score += weight * count
                total_weight += count
        
        for keyword, weight in self.NEGATIVE_KEYWORDS.items():
            if keyword in text_lower:
                count = text_lower.count(keyword)
                sentiment_score += weight * count
                total_weight += count
        
        if total_weight == 0:
            return "neutral", 0.5
        
        avg_score = sentiment_score / total_weight
        
        # Classify
        if avg_score > 0.3:
            sentiment = "positive"
        elif avg_score < -0.3:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        # Confidence based on signal strength
        confidence = min(abs(avg_score) * 0.6 + 0.4, 0.95)
        
        return sentiment, confidence
    
    def get_clinical_sentiment(self, text: str) -> Dict[str, Any]:
        """Get detailed clinical sentiment analysis"""
        sentiment, confidence = self.analyze(text)
        text_lower = text.lower()
        
        # Trial outcome classification
        if "primary endpoint met" in text_lower:
            trial_sentiment = "success"
            trial_confidence = 0.95
        elif "primary endpoint not met" in text_lower:
            trial_sentiment = "failure"
            trial_confidence = 0.95
        elif any(kw in text_lower for kw in ["phase 3", "phase iii", "pivotal", "registration"]):
            trial_sentiment = "registration"
            trial_confidence = 0.85
        elif any(kw in text_lower for kw in ["phase 2", "phase ii"]):
            trial_sentiment = "mid-stage"
            trial_confidence = 0.75
        elif any(kw in text_lower for kw in ["phase 1", "phase i"]):
            trial_sentiment = "early-stage"
            trial_confidence = 0.6
        else:
            trial_sentiment = "unknown"
            trial_confidence = 0.5
        
        # Signal detection
        signals_detected = []
        if "fda approves" in text_lower or "fda approved" in text_lower:
            signals_detected.append("FDA_APPROVAL")
        if "fda rejects" in text_lower or "fda rejected" in text_lower:
            signals_detected.append("FDA_REJECTION")
        if "breakthrough therapy" in text_lower:
            signals_detected.append("BREAKTHROUGH_DESIGNATION")
        if "orphan drug" in text_lower:
            signals_detected.append("ORPHAN_DESIGNATION")
        
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "trial_sentiment": trial_sentiment,
            "trial_confidence": trial_confidence,
            "signals": signals_detected,
            "positive_signals": [k for k in self.POSITIVE_KEYWORDS if k in text_lower],
            "negative_signals": [k for k in self.NEGATIVE_KEYWORDS if k in text_lower],
            "raw_score": self._calculate_raw_score(text),
        }
    
    def _calculate_raw_score(self, text: str) -> float:
        """Calculate raw sentiment score"""
        text_lower = text.lower()
        score = 0
        weight = 0
        
        for keyword, w in self.POSITIVE_KEYWORDS.items():
            if keyword in text_lower:
                score += w
                weight += 1
        
        for keyword, w in self.NEGATIVE_KEYWORDS.items():
            if keyword in text_lower:
                score += w
                weight += 1
        
        return score / weight if weight > 0 else 0


# Convenience functions
def extract_entities(text: str) -> List[Dict]:
    """Extract entities from text"""
    extractor = EnhancedEntityExtractor()
    entities = extractor.extract_entities(text)
    return [
        {
            "text": e.text,
            "type": e.entity_type,
            "ticker": e.ticker,
            "confidence": e.confidence,
            "metadata": e.metadata
        }
        for e in entities
    ]


def analyze_sentiment(text: str) -> Dict:
    """Analyze sentiment of text"""
    analyzer = EnhancedSentimentAnalyzer()
    return analyzer.get_clinical_sentiment(text)


if __name__ == "__main__":
    extractor = EnhancedEntityExtractor()
    analyzer = EnhancedSentimentAnalyzer()
    
    sample = """
    NCT04876555: A Phase 3 trial of Pfizer's novel oncology drug showed 
    statistically significant improvement in progression-free survival. 
    HR=0.65 (95% CI: 0.52-0.81), p<0.001. FDA approved the treatment 
    for advanced non-small cell lung cancer. 456 patients were enrolled.
    The primary endpoint of PFS was met with 45% reduction in risk.
    """
    
    print("=== Entities ===")
    for e in extractor.extract_entities(sample):
        print(f"  {e}")
    
    print("\n=== Sentiment ===")
    print(analyzer.get_clinical_sentiment(sample))
