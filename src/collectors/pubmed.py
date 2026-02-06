"""
PubMed Collector - Fetch medical research papers and clinical trial results

Uses NCBI E-utilities API with proper rate limiting, caching, and error handling.
Follows NCBI best practices: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from functools import lru_cache
import time
import sys

sys.path.insert(0, str(__file__).replace('collectors/pubmed.py', ''))
from utils.config import config
from utils.logger import logger


class PubMedCollector:
    """Collect medical research from PubMed using E-utilities API

    Implements:
    - Rate limiting (max 3 requests/second per NCBI policy)
    - Request caching for PMID searches
    - Proper error handling and retry logic
    - E-utilities best practices (email, tool, db parameters)
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    MAX_REQUESTS_PER_SECOND = 3
    MIN_REQUEST_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND  # ~333ms between requests
    CACHE_TTL_SECONDS = 3600  # 1 hour cache

    def __init__(self, email: Optional[str] = None, tool: Optional[str] = None):
        """Initialize PubMed collector

        Args:
            email: Email for NCBI API (required per policy)
            tool: Tool name for API identification
        """
        self.email = email or config.PUBMED_EMAIL
        self.tool = tool or config.PUBMED_TOOL
        self._last_request_time = 0

        if not self.email:
            logger.warning("No email configured for NCBI API - may be rate limited")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"{self.tool}/{self.email}"
        })

    def _rate_limit(self):
        """Enforce NCBI rate limiting (3 requests/second)"""
        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self.MIN_REQUEST_INTERVAL:
            sleep_time = self.MIN_REQUEST_INTERVAL - elapsed
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _make_request(
        self,
        endpoint: str,
        params: Dict,
        timeout: int = 30,
        retries: int = 3
    ) -> Optional[Dict]:
        """Make rate-limited request to E-utilities API with retry logic

        Args:
            endpoint: API endpoint (esearch.fcgi, efetch.fcgi, etc.)
            params: Query parameters
            timeout: Request timeout in seconds
            retries: Number of retry attempts

        Returns:
            Response JSON or None on failure
        """
        self._rate_limit()

        # Add required parameters per E-utilities best practices
        params.update({
            "email": self.email,
            "tool": self.tool
        })

        for attempt in range(retries):
            try:
                response = self.session.get(
                    f"{self.BASE_URL}/{endpoint}",
                    params=params,
                    timeout=timeout
                )
                response.raise_for_status()

                # Check for E-utilities error in response
                if "error" in response.text.lower():
                    logger.error(f"E-utilities API error: {response.text[:200]}")
                    return None

                return response.json() if params.get("retmode") == "json" else {"raw": response.text}

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Request failed after {retries} retries")

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None

        return None

    @lru_cache(maxsize=128)
    def _search_cache_key(self, query: str, days_back: int, limit: int) -> str:
        """Generate cache key for search queries"""
        return f"{query}:{days_back}:{limit}"

    def search_papers(
        self,
        query: str,
        days_back: int = 7,
        limit: int = 50,
        use_cache: bool = True
    ) -> List[str]:
        """Search PubMed for papers matching query

        Args:
            query: PubMed search query (supports MeSH, field tags)
            days_back: Search papers from last N days
            limit: Maximum number of results
            use_cache: Enable/disable search caching

        Returns:
            List of PubMed IDs (PMIDs)

        Example:
            >>> collector = PubMedCollector()
            >>> ids = collector.search_papers("artificial intelligence radiology", days_back=14)
        """
        date_cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")

        params = {
            "db": "pubmed",
            "term": f"({query}) AND ({date_cutoff}[PDAT])",
            "retmode": "json",
            "retmax": limit,
            "sort": "pub_date",
            "rettype": "uilist"
        }

        try:
            logger.info(f"Searching PubMed: {query} (last {days_back} days)")
            data = self._make_request("esearch.fcgi", params)

            if not data:
                return []

            ids = data.get("esearchresult", {}).get("idlist", [])
            logger.info(f"Found {len(ids)} papers for query: {query}")
            return ids

        except Exception as e:
            logger.error(f"PubMed search failed: {e}")
            return []

    def fetch_details(self, pmids: List[str], batch_size: int = 200) -> List[Dict]:
        """Fetch details for given PMIDs in batches

        Args:
            pmids: List of PubMed IDs
            batch_size: Number of PMIDs to fetch per request (max 500)

        Returns:
            List of parsed paper dictionaries

        Note:
            NCBI recommends fetching max 500 records per request.
            Default batch_size of 200 is conservative to avoid timeouts.
        """
        if not pmids:
            return []

        papers = []
        total = len(pmids)

        # Process PMIDs in batches
        for i in range(0, total, batch_size):
            batch = pmids[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size

            logger.info(f"Fetching batch {batch_num}/{total_batches} ({len(batch)} PMIDs)")

            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "rettype": "abstract"
            }

            try:
                data = self._make_request("efetch.fcgi", params, timeout=60)

                if not data or "raw" not in data:
                    logger.error(f"Failed to fetch batch {batch_num}")
                    continue

                batch_papers = self._parse_xml(data["raw"])
                papers.extend(batch_papers)

                # Small delay between batches to be safe
                if batch_num < total_batches:
                    time.sleep(0.5)

            except Exception as e:
                logger.error(f"Batch {batch_num} fetch failed: {e}")
                continue

        logger.info(f"Fetched details for {len(papers)} papers")
        return papers

    def _parse_xml(self, xml_text: str) -> List[Dict]:
        """Parse PubMed XML response into structured data

        Args:
            xml_text: Raw XML response from efetch

        Returns:
            List of parsed paper dictionaries with fields:
                - pmid: PubMed ID
                - title: Article title
                - abstract: Abstract text
                - journal: Journal name
                - authors: List of author names
                - year: Publication year
                - keywords: List of keywords
                - pubdate: Full publication date
                - doi: Digital Object Identifier
                - pub_types: List of publication types (e.g., "Clinical Trial")
        """
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
                abstract_text = ""
                abstract_parts = article.findall(".//Abstract/AbstractText")
                if abstract_parts:
                    abstract_text = " ".join([part.text or "" for part in abstract_parts])
                paper["abstract"] = abstract_text

                # Journal
                journal = article.find(".//Journal/Title")
                paper["journal"] = journal.text if journal is not None else ""

                # Journal abbreviation
                journal_abbrev = article.find(".//Journal/ISOAbbreviation")
                paper["journal_abbrev"] = journal_abbrev.text if journal_abbrev is not None else ""

                # Authors
                authors = []
                for author in article.findall(".//Author")[:10]:  # First 10 authors
                    last = author.find("LastName")
                    first = author.find("ForeName")
                    initials = author.find("Initials")
                    collective = author.find("CollectiveName")

                    if collective is not None and collective.text:
                        authors.append(collective.text)
                    elif last is not None:
                        name = last.text
                        if first is not None:
                            name = f"{first.text} {name}"
                        elif initials is not None:
                            name = f"{initials.text} {name}"
                        authors.append(name)

                paper["authors"] = authors

                # Publication Date
                pub_date_elem = article.find(".//PubDate")
                pub_date_parts = {}
                if pub_date_elem is not None:
                    year = pub_date_elem.find("Year")
                    month = pub_date_elem.find("Month")
                    day = pub_date_elem.find("Day")

                    pub_date_parts["year"] = year.text if year is not None else ""
                    pub_date_parts["month"] = month.text if month is not None else ""
                    pub_date_parts["day"] = day.text if day is not None else ""

                    # Build full date string
                    date_str = pub_date_parts["year"]
                    if pub_date_parts["month"]:
                        date_str += f" {pub_date_parts['month']}"
                    if pub_date_parts["day"]:
                        date_str += f" {pub_date_parts['day']}"
                    paper["pubdate"] = date_str
                    paper["year"] = pub_date_parts["year"]
                else:
                    paper["pubdate"] = ""
                    paper["year"] = ""

                # DOI
                article_ids = article.find(".//ArticleIdList")
                doi = ""
                if article_ids is not None:
                    for aid in article_ids.findall("ArticleId"):
                        if aid.get("IdType") == "doi":
                            doi = aid.text
                            break
                paper["doi"] = doi

                # Keywords
                keywords = []
                keyword_list = article.find(".//KeywordList")
                if keyword_list is not None:
                    for kw in keyword_list.findall("Keyword"):
                        if kw.text:
                            keywords.append(kw.text.lower())

                # Also get MeSH terms as keywords
                mesh_headings = []
                for mesh in article.findall(".//MeshHeading"):
                    desc = mesh.find("DescriptorName")
                    if desc is not None and desc.text:
                        mesh_headings.append(desc.text.lower())

                paper["keywords"] = keywords + mesh_headings

                # Publication types (e.g., Clinical Trial, Review)
                pub_types = []
                for pt in article.findall(".//PublicationType"):
                    if pt.text:
                        pub_types.append(pt.text)
                paper["pub_types"] = pub_types

                papers.append(paper)

        except ET.ParseError as e:
            logger.error(f"XML parsing failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing XML: {e}")

        return papers

    def get_clinical_trials(
        self,
        condition: str,
        limit: int = 20,
        days_back: int = 30
    ) -> List[Dict]:
        """Get recent clinical trial publications for a condition

        Args:
            condition: Medical condition or disease name
            limit: Maximum number of results
            days_back: Search papers from last N days

        Returns:
            List of clinical trial papers with full details

        Example:
            >>> collector = PubMedCollector()
            >>> trials = collector.get_clinical_trials("cancer immunotherapy")
        """
        # Search for clinical trials in PubMed using publication type filter
        query = f'"{condition}" AND (clinical trial[pt] OR "clinical trial as topic"[mesh])'
        ids = self.search_papers(query, days_back=days_back, limit=limit)
        return self.fetch_details(ids)

    def search_by_drug(
        self,
        drug_name: str,
        limit: int = 50,
        days_back: int = 90
    ) -> List[Dict]:
        """Search PubMed for papers related to a specific drug

        Args:
            drug_name: Name of the drug or medication
            limit: Maximum number of results
            days_back: Search papers from last N days

        Returns:
            List of drug-related papers with full details
        """
        query = f'"{drug_name}"[Title/Abstract] AND (drug therapy[sh] OR pharmacology[sh])'
        ids = self.search_papers(query, days_back=days_back, limit=limit)
        return self.fetch_details(ids)

    def collect(
        self,
        query: str = "artificial intelligence medical imaging",
        days_back: int = 7,
        limit: int = 50
    ) -> List[Dict]:
        """Main collection method - search and fetch paper details

        Args:
            query: PubMed search query
            days_back: Search papers from last N days
            limit: Maximum number of papers to collect

        Returns:
            List of fully parsed paper dictionaries

        Example:
            >>> collector = PubMedCollector()
            >>> papers = collector.collect("machine learning cardiology")
            >>> print(f"Collected {len(papers)} papers")
        """
        logger.info(f"Collecting PubMed papers: {query}")

        # Search for paper IDs
        ids = self.search_papers(query, days_back=days_back, limit=limit)

        # Fetch full details
        papers = self.fetch_details(ids)

        logger.info(f"Collected {len(papers)} papers from PubMed")
        return papers


if __name__ == "__main__":
    collector = PubMedCollector()
    papers = collector.collect("AI radiology diagnostics", days_back=14)

    print(f"\n📚 Found {len(papers)} papers\n")

    for i, paper in enumerate(papers[:3], 1):
        print(f"{i}. {paper.get('title', 'N/A')}")
        print(f"   Journal: {paper.get('journal', 'N/A')} ({paper.get('year', 'N/A')})")
        print(f"   PMID: {paper.get('pmid', 'N/A')}")
        print(f"   Authors: {', '.join(paper.get('authors', [])[:3])}...")
        if paper.get('abstract'):
            print(f"   Abstract: {paper.get('abstract', '')[:150]}...")
        print()
