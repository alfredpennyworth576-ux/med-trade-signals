"""
Integration tests for the full pipeline
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signals.generator import SignalGenerator, TradingSignal


class TestPipelineIntegration:
    """Integration tests for the complete pipeline"""
    
    @pytest.fixture
    def generator(self):
        """Create signal generator with mocked dependencies"""
        with patch('src.signals.generator.PubMedCollector') as mock_pubmed, \
             patch('src.signals.generator.FDACollector') as mock_fda, \
             patch('src.signals.generator.RedditCollector') as mock_reddit:
            
            # Setup mock collectors
            mock_pubmed.return_value.collect.return_value = []
            mock_fda.return_value.collect.return_value = {"approvals": [], "rejections": []}
            mock_reddit.return_value.collect.return_value = {"finance": [], "medical": []}
            
            generator = SignalGenerator()
            return generator
    
    def test_pipeline_runs_successfully(self, generator):
        """Test that pipeline runs without errors"""
        signals = generator.generate_all()
        
        assert isinstance(signals, list)
    
    def test_pipeline_with_empty_data(self, generator):
        """Test pipeline behavior with no data"""
        signals = generator.generate_all()
        
        assert signals == []
    
    def test_pipeline_handles_exceptions(self, generator):
        """Test that pipeline handles exceptions gracefully"""
        with patch.object(generator, 'pubmed') as mock_pubmed:
            mock_pubmed.collect.side_effect = Exception("Test error")
            
            # Should not raise
            signals = generator.generate_all()
            
            assert isinstance(signals, list)
    
    def test_signal_types_coverage(self):
        """Test that all signal types are covered"""
        types = SignalGenerator.SIGNAL_TYPES
        
        expected_types = ["FDA_APPROVAL", "FDA_REJECTION", "TRIAL_SUCCESS", "TRIAL_FAILURE"]
        
        for expected in expected_types:
            assert expected in types, f"Missing signal type: {expected}"
    
    def test_save_and_load_signals(self, tmp_path):
        """Test saving and loading signals"""
        signals = [
            TradingSignal(
                signal_id="test_001",
                signal_type="FDA_APPROVAL",
                ticker="ABC",
                company_name="ABC Pharma",
                headline="FDA approves drug",
                summary="Summary",
                confidence=85,
                sentiment="positive",
                target_upside=15.0,
                target_downside=-5.0,
                sources=["fda.gov"],
                collected_at="2024-01-15",
                created_at=datetime.now().isoformat()
            )
        ]
        
        # Save
        filepath = tmp_path / "signals.json"
        with open(filepath, "w") as f:
            json.dump([s.to_dict() for s in signals], f)
        
        # Load
        with open(filepath, "r") as f:
            loaded = json.load(f)
        
        assert len(loaded) == 1
        assert loaded[0]["signal_id"] == "test_001"
