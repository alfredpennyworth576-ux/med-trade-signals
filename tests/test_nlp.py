"""
Tests for NLP utilities (entity extraction, sentiment analysis)
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.nlp.utils import EnhancedEntityExtractor, EnhancedSentimentAnalyzer


class TestEntityExtractor:
    """Tests for entity extraction"""
    
    @pytest.fixture
    def extractor(self):
        """Create EnhancedEntityExtractor instance"""
        return EnhancedEntityExtractor()
    
    def test_extract_entities_returns_list(self, extractor):
        """Test that extract_entities returns a list"""
        text = "Phase 3 trial showed positive results."
        entities = extractor.extract_entities(text)
        
        assert isinstance(entities, list)
    
    def test_extract_clinical_phase(self, extractor):
        """Test extracting clinical trial phases"""
        text = "Phase 3 trial showed positive results. Phase II data was encouraging."
        entities = extractor.extract_entities(text)
        
        phases = [e.text for e in entities if e.entity_type == "trial_phase"]
        assert len(phases) >= 1
        assert any("phase" in p.lower() for p in phases)
    
    def test_extract_trial_info(self, extractor):
        """Test extracting trial information"""
        text = "Phase 3 trial for breast cancer with 500 patients"
        trial = extractor.extract_trial_info(text)
        
        assert trial.phase == "Phase 3"
        assert trial.condition == "breast cancer"
    
    def test_extract_companies(self, extractor):
        """Test extracting company entities"""
        text = "Pfizer announces new drug approval"
        companies = extractor.extract_companies(text)
        
        assert len(companies) >= 1
        company_texts = [e.text.lower() for e in companies]
        assert any("pfizer" in ct for ct in company_texts)
    
    def test_extract_efficacy_numbers(self, extractor):
        """Test extracting efficacy percentages"""
        text = "The treatment showed 45% improvement in patients"
        efficacy = extractor.extract_efficacy(text)
        
        assert len(efficacy) >= 1
    
    def test_extract_phases(self, extractor):
        """Test extracting phases specifically"""
        text = "Phase 2 trial was successful. Phase 3 will follow."
        phases = extractor.extract_phases(text)
        
        assert len(phases) >= 1
    
    def test_extract_fda_decisions(self, extractor):
        """Test extracting FDA decisions"""
        text = "FDA approves the new treatment for use"
        decisions = extractor.extract_fda_decisions(text)
        
        assert len(decisions) >= 1
        assert any(e.entity_type == "fda_decision" for e in decisions)
    
    def test_extract_conditions(self, extractor):
        """Test extracting medical conditions"""
        text = "Treatment for breast cancer and lung cancer"
        conditions = extractor.extract_conditions(text)
        
        assert len(conditions) >= 1
        assert any("cancer" in c.text.lower() for c in conditions)
    
    def test_resolve_entity(self, extractor):
        """Test resolving entity context"""
        text = "Phase 3 trial showed positive results"
        entities = extractor.extract_entities(text)
        
        if entities:
            resolved = extractor.resolve_entity(entities[0], text)
            assert isinstance(resolved, type(entities[0]))


class TestSentimentAnalyzer:
    """Tests for sentiment analysis"""
    
    @pytest.fixture
    def analyzer(self):
        """Create EnhancedSentimentAnalyzer instance"""
        return EnhancedSentimentAnalyzer()
    
    def test_positive_sentiment(self, analyzer):
        """Test positive sentiment detection"""
        text = "The drug showed excellent results with significant improvement"
        sentiment, confidence = analyzer.analyze(text)
        
        assert sentiment == "positive"
        assert confidence > 0.5
    
    def test_negative_sentiment(self, analyzer):
        """Test negative sentiment detection"""
        text = "The trial failed to meet its primary endpoint"
        sentiment, confidence = analyzer.analyze(text)
        
        assert sentiment == "negative"
        assert confidence > 0.5
    
    def test_neutral_sentiment(self, analyzer):
        """Test neutral sentiment detection"""
        text = "The study is ongoing and results are pending"
        sentiment, confidence = analyzer.analyze(text)
        
        assert sentiment == "neutral"
    
    def test_clinical_sentiment_success(self, analyzer):
        """Test clinical sentiment for success"""
        text = "The primary endpoint was met with statistical significance"
        result = analyzer.get_clinical_sentiment(text)
        
        assert result["trial_sentiment"] == "success"
        assert result["confidence"] > 0.8
    
    def test_clinical_sentiment_failure(self, analyzer):
        """Test clinical sentiment for failure"""
        text = "The primary endpoint was not met in the phase 3 trial"
        result = analyzer.get_clinical_sentiment(text)
        
        assert result["trial_sentiment"] == "failure"
    
    def test_clinical_sentiment_registration(self, analyzer):
        """Test clinical sentiment for pivotal trials"""
        text = "The phase 3 pivotal trial showed positive results"
        result = analyzer.get_clinical_sentiment(text)
        
        assert result["trial_sentiment"] == "registration"
    
    def test_confidence_bounded(self, analyzer):
        """Test that confidence is properly bounded"""
        text = "The drug works well"  # Minimal keywords
        sentiment, confidence = analyzer.analyze(text)
        
        assert 0 <= confidence <= 1
    
    def test_calculate_raw_score(self, analyzer):
        """Test raw score calculation"""
        text = "Excellent results with significant improvement"
        score = analyzer._calculate_raw_score(text)
        
        assert score > 0
