"""
PubMed Collector - Fetch medical research papers and clinical trial results
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sys
sys.path.insert(0, str(__file__).replace('collectors/pubmed.py', ''))
from utils.config import config
from utils.logger import logger

class PubMedCollector:
    """Collect medical research from PubMed"""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self):
        self.email = config.PUBMED_EMAIL
        self.tool = config.PUBMED_TOOL
    
    def search_papers(self, query: str, days_back: int = 7, limit: int = 50) -> List[str]:
        """Search PubMed for papers matching query"""
        date_cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        
        params = {
            "db": "pubmed",
            "term": f"({query}) AND ({date_cutoff}[PDAT])",
            "retmode": "json",
            "retmax": limit,
            "sort": "pub_date"
        }
        
        try:
            logger.info(f"Searching PubMed: {query}")
            response = requests.get(
                f"{self.BASE_URL}/esearch.fcgi",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            ids = data.get("esearchresult", {}).get("idlist", [])
            logger.info(f"Found {len(ids)} papers")
            return ids
            
        except Exception as e:
            logger.error(f"PubMed search failed: {e}")
            return []
    
    def fetch_details(self, pmids: List[str]) -> List[Dict]:
        """Fetch details for given PMIDs"""
        if not pmids:
            return []
        
        ids_str = ",".join(pmids[:10])  # Limit to 10 at a time
        
        params = {
            "db": "pubmed",
            "id": ids_str,
            "retmode": "xml"
        }
        
        try:
            logger.info(f"Fetching details for {len(pmids)} PMIDs")
            response = requests.get(
                f"{self.BASE_URL}/efetch.fcgi",
                params=params,
                timeout=60
            )
            response.raise_for_status()
            
            return self._parse_xml(response.text)
            
        except Exception as e:
            logger.error(f"PubMed fetch failed: {e}")
            return []
    
    def _parse_xml(self, xml_text: str) -> List[Dict]:
        """Parse PubMed XML response"""
        papers = []
        
        try:
            root = ET.fromstring(xml_text)
            
            for article in root.findall(".//PubmedArticle"):
                paper = {}
                
                # PMID
                pmid = article.find(".//PMID")
                paper["pmid"] = pmid.text if pmid is not None else ""
                
                # Title
                title = article.find(".//ArticleTitle")
                paper["title"] = title.text if title is not None else ""
                
                # Abstract
                abstract = article.find(".//AbstractText")
                paper["abstract"] = abstract.text if abstract is not None else ""
                
                # Journal
                journal = article.find(".//Journal/Title")
                paper["journal"] = journal.text if journal is not None else ""
                
                # Authors
                authors = []
                for author in article.findall(".//Author")[:5]:  # First 5
                    last = author.find("LastName")
                    first = author.find("ForeName")
                    if last is not None:
                        name = last.text
                        if first is not None:
                            name = f"{first.text} {name}"
                        authors.append(name)
                paper["authors"] = authors
                
                # Publication Date
                pub_date = article.find(".//PubDate/Year")
                paper["year"] = pub_date.text if pub_date is not None else ""
                
                # Keywords
                keywords = []
                for kw in article.findall(".//Keyword"):
                    if kw.text:
                        keywords.append(kw.text.lower())
                paper["keywords"] = keywords
                
                papers.append(paper)
                
        except Exception as e:
            logger.error(f"XML parsing failed: {e}")
        
        return papers
    
    def get_clinical_trials(self, condition: str, limit: int = 20) -> List[Dict]:
        """Get recent clinical trials for a condition"""
        # Search for clinical trials in PubMed
        query = f'"{condition}" AND (clinical trial[pt] OR clinical trial[Publication Type])'
        ids = self.search_papers(query, days_back=30, limit=limit)
        return self.fetch_details(ids)
    
    def collect(self, query: str = "artificial intelligence medical imaging") -> List[Dict]:
        """Main collection method"""
        logger.info(f"Collecting PubMed papers: {query}")
        
        # Search
        ids = self.search_papers(query)
        
        # Fetch details
        papers = self.fetch_details(ids)
        
        logger.info(f"Collected {len(papers)} papers")
        return papers


if __name__ == "__main__":
    collector = PubMedCollector()
    papers = collector.collect("AI radiology diagnostics")
    
    for paper in papers[:3]:
        print(f"\n{paper.get('title', 'N/A')}")
        print(f"  Journal: {paper.get('journal', 'N/A')}")
        print(f"  PMID: {paper.get('pmid', 'N/A')}")
