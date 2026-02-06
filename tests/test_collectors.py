"""
Test collectors module
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import responses

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.pubmed import PubMedCollector
from src.collectors.fda import FDACollector
from src.collectors.reddit import RedditCollector


class TestPubMedCollector:
    """Tests for PubMed collector"""
    
    def test_search_papers_returns_ids(self, mock_requests):
        """Test that search returns PMID list"""
        collector = PubMedCollector()
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "esearchresult": {
                "idlist": ["12345", "67890"]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        ids = collector.search_papers("test query")
        
        assert isinstance(ids, list)
        assert len(ids) == 2
    
    def test_search_papers_handles_empty(self, mock_requests):
        """Test empty result handling"""
        collector = PubMedCollector()
        
        mock_response = Mock()
        mock_response.json.return_value = {"esearchresult": {"idlist": []}}
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        ids = collector.search_papers("rare query")
        
        assert ids == []
    
    def test_search_papers_error_handling(self, mock_requests):
        """Test error handling on request failure"""
        collector = PubMedCollector()
        mock_requests.side_effect = Exception("Connection error")
        
        ids = collector.search_papers("test")
        
        assert ids == []
    
    @responses.activate
    def test_fetch_details_parses_xml(self):
        """Test XML parsing of PubMed response"""
        collector = PubMedCollector()
        
        # Mock XML response
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
        <PubmedArticleSet>
            <PubmedArticle>
                <MedlineCitation>
                    <PMID>12345</PMID>
                    <Article>
                        <ArticleTitle>Test Article</ArticleTitle>
                        <Abstract><AbstractText>Test abstract</AbstractText></Abstract>
                        <Journal>
                            <Title>Test Journal</Title>
                        </Journal>
                        <AuthorList>
                            <Author><LastName>Smith</LastName><ForeName>John</ForeName></Author>
                        </AuthorList>
                    </Article>
                </MedlineCitation>
            </PubmedArticle>
        </PubmedArticleSet>"""
        
        responses.add(
            responses.GET,
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            body=xml_response,
            status=200
        )
        
        papers = collector.fetch_details(["12345"])
        
        assert len(papers) == 1
        assert papers[0]["pmid"] == "12345"
        assert "Test Article" in papers[0]["title"]


class TestFDACollector:
    """Tests for FDA collector"""
    
    def test_approvals_returns_list(self, mock_session):
        """Test that approvals returns list of approvals"""
        collector = FDACollector()
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "application_number": "123456",
                    "drug_name": "Test Drug",
                    "sponsor_name": "Test Pharma",
                    "indication": "Treatment"
                }
            ]
        }
        mock_session.get.return_value = mock_response
        
        approvals = collector.get_approvals()
        
        assert isinstance(approvals, list)
    
    def test_rejections_returns_list(self, mock_session):
        """Test that rejections returns list"""
        collector = FDACollector()
        
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_session.get.return_value = mock_response
        
        rejections = collector.get_rejections()
        
        assert isinstance(rejections, list)
    
    def test_parse_approval_extracts_fields(self):
        """Test that approval parsing extracts key fields"""
        collector = FDACollector()
        
        result = {
            "application_number": "123456",
            "drug_name": "Test Drug",
            "sponsor_name": "Test Pharma",
            "indication": "Treatment",
            "action_date": "2024-01-15",
            "action_type": "Approval",
            "application_status": "Approved"
        }
        
        parsed = collector._parse_approval(result)
        
        assert parsed["fda_id"] == "123456"
        assert parsed["drug_name"] == "Test Drug"
        assert parsed["company"] == "Test Pharma"


class TestRedditCollector:
    """Tests for Reddit collector"""
    
    def test_get_posts_returns_list(self, mock_session):
        """Test that get_posts returns list of posts"""
        collector = RedditCollector()
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Test Post",
                            "selftext": "Test content",
                            "score": 100,
                            "num_comments": 50,
                            "permalink": "/r/test/comments/abc123/",
                            "created_utc": 1704067200
                        }
                    }
                ]
            }
        }
        mock_session.get.return_value = mock_response
        
        posts = collector.get_posts("test", limit=10)
        
        assert isinstance(posts, list)
        assert len(posts) == 1
        assert posts[0]["title"] == "Test Post"
        assert posts[0]["score"] == 100
        assert posts[0]["subreddit"] == "test"
    
    def test_get_medical_posts_handles_error(self, mock_session):
        """Test that get_medical_posts handles errors gracefully"""
        collector = RedditCollector()
        mock_session.get.side_effect = Exception("Reddit API error")
        
        posts = collector.get_medical_posts()
        
        assert posts == []
    
    def test_get_posts_extracts_permalink(self, mock_session):
        """Test that posts extract permalink correctly"""
        collector = RedditCollector()
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Test",
                            "selftext": "",
                            "score": 0,
                            "num_comments": 0,
                            "permalink": "/r/medicine/comments/abc123/test/",
                            "created_utc": 1704067200
                        }
                    }
                ]
            }
        }
        mock_session.get.return_value = mock_response
        
        posts = collector.get_posts("medicine")
        
        assert "reddit.com" in posts[0]["url"]
        assert "/r/medicine/" in posts[0]["url"]
