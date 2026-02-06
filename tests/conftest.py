"""
Test configuration for Med-Trade-Signals
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def sample_signal():
    """Sample trading signal for testing"""
    return {
        "signal_id": "test_signal_001",
        "signal_type": "FDA_APPROVAL",
        "ticker": "ABC",
        "company_name": "ABC Pharmaceuticals",
        "headline": "FDA approves ABC drug for condition",
        "summary": "Clinical trials showed significant improvement...",
        "confidence": 87,
        "sentiment": "positive",
        "target_upside": 15.2,
        "target_downside": -5.1,
        "sources": [
            {"name": "fda.gov", "url": "https://fda.gov", "reliability_score": 1.0}
        ],
        "entities": [
            {"text": "ABC drug", "entity_type": "drug", "confidence": 0.9}
        ],
        "created_at": datetime.now().isoformat()
    }

@pytest.fixture
def sample_paper():
    """Sample PubMed paper for testing"""
    return {
        "pmid": "12345678",
        "title": "AI Improves MRI Interpretation Time",
        "abstract": "A deep learning model showed 37% reduction in interpretation time...",
        "journal": "Radiology",
        "authors": ["Smith J", "Doe A"],
        "year": "2024"
    }

@pytest.fixture
def sample_fda_approval():
    """Sample FDA approval for testing"""
    return {
        "application_number": "123456",
        "drug_name": "New Drug",
        "company": "Test Pharma",
        "indication": "Treatment of condition",
        "action_date": "2024-01-15",
        "action_type": "Approval",
        "status": "Approved"
    }

@pytest.fixture
def mock_requests():
    """Mock requests for HTTP testing"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get

@pytest.fixture
def mock_session():
    """Mock requests Session"""
    mock = Mock(spec=requests.Session)
    mock.get.return_value.json.return_value = {"results": []}
    mock.get.return_value.raise_for_status.return_value = None
    return mock
