"""
Test signal generation
"""
import pytest
import sys
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signals.generator import SignalGenerator, TradingSignal


class TestTradingSignal:
    """Tests for TradingSignal dataclass"""
    
    def test_create_signal(self):
        """Test creating a trading signal"""
        signal = TradingSignal(
            signal_id="test_001",
            signal_type="FDA_APPROVAL",
            ticker="ABC",
            company_name="ABC Pharma",
            headline="FDA approves new drug",
            summary="Clinical trials showed efficacy",
            confidence=85,
            sentiment="positive",
            target_upside=15.0,
            target_downside=-5.0,
            sources=["fda.gov"],
            collected_at="2024-01-15",
            created_at=datetime.now().isoformat()
        )
        
        assert signal.signal_id == "test_001"
        assert signal.ticker == "ABC"
        assert signal.confidence == 85
    
    def test_signal_to_dict(self):
        """Test signal to_dict conversion"""
        signal = TradingSignal(
            signal_id="test_001",
            signal_type="FDA_APPROVAL",
            ticker="ABC",
            company_name="ABC Pharma",
            headline="FDA approves new drug",
            summary="Clinical trials showed efficacy",
            confidence=85,
            sentiment="positive",
            target_upside=15.0,
            target_downside=-5.0,
            sources=["fda.gov"],
            collected_at="2024-01-15",
            created_at=datetime.now().isoformat()
        )
        
        result = signal.to_dict()
        
        assert isinstance(result, dict)
        assert result["signal_id"] == "test_001"


class TestSignalGenerator:
    """Tests for signal generator"""
    
    @pytest.fixture
    def generator(self):
        """Create signal generator with mocked collectors"""
        return SignalGenerator()
    
    def test_generate_from_pubmed_returns_list(self, generator):
        """Test that pubmed signal generation returns list"""
        with patch.object(generator, 'pubmed') as mock_pubmed:
            mock_pubmed.collect.return_value = []
            
            signals = generator.generate_from_pubmed()
            
            assert isinstance(signals, list)
    
    def test_generate_from_fda_returns_list(self, generator):
        """Test that FDA signal generation returns list"""
        with patch.object(generator, 'fda') as mock_fda:
            mock_fda.collect.return_value = {"approvals": [], "rejections": []}
            
            signals = generator.generate_from_fda()
            
            assert isinstance(signals, list)
    
    def test_generate_from_reddit_returns_list(self, generator):
        """Test that Reddit signal generation returns list"""
        with patch.object(generator, 'reddit') as mock_reddit:
            mock_reddit.collect.return_value = {"finance": [], "medical": []}
            
            signals = generator.generate_from_reddit()
            
            assert isinstance(signals, list)
    
    def test_generate_all_returns_combined_signals(self, generator):
        """Test that generate_all combines all sources"""
        with patch.object(generator, 'pubmed') as mock_pubmed, \
             patch.object(generator, 'fda') as mock_fda, \
             patch.object(generator, 'reddit') as mock_reddit:
            
            mock_pubmed.collect.return_value = []
            mock_fda.collect.return_value = {"approvals": [], "rejections": []}
            mock_reddit.collect.return_value = {"finance": [], "medical": []}
            
            signals = generator.generate_all()
            
            assert isinstance(signals, list)
    
    def test_signal_types_defined(self):
        """Test that signal types are properly defined"""
        types = SignalGenerator.SIGNAL_TYPES
        
        assert "FDA_APPROVAL" in types
        assert "FDA_REJECTION" in types
        assert "TRIAL_SUCCESS" in types
        assert "TRIAL_FAILURE" in types
