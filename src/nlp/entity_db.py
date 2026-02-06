"""
Entity Database - Wikidata/SPARQL queries for company→ticker mapping
"""
import json
import os
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import sys
sys.path.insert(0, str(__file__).replace('nlp/entity_db.py', ''))
from utils.config import config
from utils.logger import logger


class EntityDatabase:
    """Company entity database with Wikidata integration"""
    
    WIKIDATA_SPARQL = """
    SELECT ?company ?companyLabel ?ticker ?exchangeLabel WHERE {
        ?company wdt:P31/wdt:P279* wd:Q4830453;
                 wdt:P249 ?ticker;
                 wdt:P414 ?exchange.
        FILTER(STR(?companyLabel) = "%s")
        SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    """
    
    # Common pharmaceutical Wikidata QIDs
    PHARMA_ENTITIES = {
        "Pfizer": {"qid": "Q784", "ticker": "PFE", "exchange": "NYSE"},
        "Merck": {"qid": "Q645", "ticker": "MRK", "exchange": "NYSE"},
        "Novartis": {"qid": "Q1024", "ticker": "NVS", "exchange": "NYSE"},
        "Roche": {"qid": "Q1077", "ticker": "RHHBY", "exchange": "SIX"},
        "Johnson & Johnson": {"qid": "Q16635", "ticker": "JNJ", "exchange": "NYSE"},
        "Bristol Myers Squibb": {"qid": "Q1530", "ticker": "BMY", "exchange": "NYSE"},
        "AbbVie": {"qid": "Q279771", "ticker": "ABBV", "exchange": "NYSE"},
        "AstraZeneca": {"qid": "Q13306", "ticker": "AZN", "exchange": "NASDAQ"},
        "Gilead Sciences": {"qid": "Q42444", "ticker": "GILD", "exchange": "NASDAQ"},
        "Moderna": {"qid": "Q5034844", "ticker": "MRNA", "exchange": "NASDAQ"},
        "BioNTech": {"qid": "Q29042872", "ticker": "BNTX", "exchange": "NASDAQ"},
        "Regeneron": {"qid": "Q1057792", "ticker": "REGN", "exchange": "NASDAQ"},
        "Amgen": {"qid": "Q604726", "ticker": "AMGN", "exchange": "NASDAQ"},
        "Vertex": {"qid": "Q1486682", "ticker": "VRTX", "exchange": "NASDAQ"},
        "Biogen": {"qid": "Q847718", "ticker": "BIIB", "exchange": "NASDAQ"},
        "Alnylam": {"qid": "Q4736819", "ticker": "ALNY", "exchange": "NASDAQ"},
        "Illumina": {"qid": "Q1462343", "ticker": "ILMN", "exchange": "NASDAQ"},
        "Medtronic": {"qid": "Q162897", "ticker": "MDT", "exchange": "NYSE"},
        "Abbott": {"qid": "Q44276", "ticker": "ABT", "exchange": "NYSE"},
        "Thermo Fisher": {"qid": "Q1059160", "ticker": "TMO", "exchange": "NYSE"},
        "Boston Scientific": {"qid": "QQ3116", "ticker": "BSX", "exchange": "NYSE"},
    }
    
    def __init__(self, cache_hours: int = 168):  # Default: 7 days
        """
        Initialize entity database
        
        Args:
            cache_hours: How long to cache Wikidata results
        """
        self.cache_hours = cache_hours
        self.cache = {}
        self.cache_dir = config.PROCESSED_DIR
        self._load_cache()
        
        # Initialize with known pharma entities
        self._init_known_entities()
    
    def _init_known_entities(self):
        """Initialize with known pharmaceutical entities"""
        for company, info in self.PHARMA_ENTITIES.items():
            self.cache[company.lower()] = {
                "company": company,
                "ticker": info["ticker"],
                "exchange": info["exchange"],
                "qid": info["qid"],
                "source": "known_mapping",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _get_cache_path(self) -> str:
        """Get cache file path"""
        return f"{self.cache_dir}/entity_cache.json"
    
    def _load_cache(self):
        """Load cached entity data"""
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                    # Filter expired entries
                    cutoff = datetime.utcnow() - timedelta(hours=self.cache_hours)
                    self.cache = {
                        k: v for k, v in data.items()
                        if datetime.fromisoformat(v.get('timestamp', '2000-01-01')) > cutoff
                    }
            except Exception as e:
                logger.warning(f"Failed to load entity cache: {e}")
                self.cache = {}
    
    def _save_cache(self):
        """Save cache to disk"""
        cache_path = self._get_cache_path()
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(cache_path, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save entity cache: {e}")
    
    def _wikidata_query(self, company_name: str) -> Optional[Dict]:
        """
        Query Wikidata for company info using SPARQL
        
        Note: This is a placeholder. For production, use the Wikidata API directly
        or the sparqlwrapper library.
        """
        # For now, return None - actual implementation would use requests
        # to query https://query.wikidata.org/sparql
        logger.debug(f"Wikidata query for: {company_name}")
        return None
    
    def lookup_company_ticker(self, company_name: str, use_wikidata: bool = True) -> Optional[Dict]:
        """
        Look up company ticker symbol
        
        Args:
            company_name: Company name to look up
            use_wikidata: Whether to query Wikidata if not found locally
            
        Returns:
            Dict with company, ticker, exchange, or None if not found
        """
        # Normalize
        normalized = company_name.strip().lower()
        
        # Check cache first
        if normalized in self.cache:
            logger.debug(f"Cache hit for: {company_name}")
            return self.cache[normalized]
        
        # Try variations
        variations = [
            normalized,
            company_name.strip(),
            company_name.replace("&", "and"),
            company_name.replace(".", ""),
        ]
        
        for variant in variations:
            if variant in self.cache:
                self.cache[normalized] = self.cache[variant]
                return self.cache[normalized]
        
        # Check config ticker map
        for company, ticker in config.TICKER_MAP.items():
            if company.lower() in normalized or normalized in company.lower():
                result = {
                    "company": company,
                    "ticker": ticker,
                    "exchange": None,
                    "source": "config_mapping",
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.cache[normalized] = result
                return result
        
        # Query Wikidata if enabled
        if use_wikidata:
            wikidata_result = self._wikidata_query(company_name)
            if wikidata_result:
                result = {
                    "company": company_name,
                    "ticker": wikidata_result.get("ticker"),
                    "exchange": wikidata_result.get("exchange"),
                    "qid": wikidata_result.get("qid"),
                    "source": "wikidata",
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.cache[normalized] = result
                return result
        
        # Not found
        logger.debug(f"No ticker found for: {company_name}")
        return None
    
    def add_company(self, company_name: str, ticker: str, exchange: str = None, 
                    qid: str = None, source: str = "manual") -> bool:
        """
        Add a company to the database
        
        Args:
            company_name: Company name
            ticker: Ticker symbol
            exchange: Stock exchange
            qid: Wikidata QID
            source: Source of the mapping
            
        Returns:
            True if added successfully
        """
        normalized = company_name.lower()
        self.cache[normalized] = {
            "company": company_name,
            "ticker": ticker,
            "exchange": exchange,
            "qid": qid,
            "source": source,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._save_cache()
        logger.info(f"Added company: {company_name} ({ticker})")
        return True
    
    def get_all_tickers(self) -> Dict[str, str]:
        """Get all company->ticker mappings"""
        return {
            v.get("company"): v.get("ticker") 
            for v in self.cache.values() 
            if v.get("ticker")
        }
    
    def search_companies(self, query: str) -> list:
        """
        Search for companies matching query
        
        Args:
            query: Search query
            
        Returns:
            List of matching companies
        """
        query_lower = query.lower()
        results = []
        
        for entry in self.cache.values():
            company = entry.get("company", "")
            if query_lower in company.lower():
                results.append(entry)
        
        # Also search in config ticker map
        for company in config.TICKER_MAP:
            if query_lower in company.lower():
                if company not in [r.get("company") for r in results]:
                    results.append({
                        "company": company,
                        "ticker": config.TICKER_MAP[company],
                        "source": "config"
                    })
        
        return results


# Convenience function
def lookup_company_ticker(company_name: str) -> Optional[str]:
    """
    Convenience function to look up ticker for a company
    
    Args:
        company_name: Company name
        
    Returns:
        Ticker symbol or None
    """
    db = EntityDatabase()
    result = db.lookup_company_ticker(company_name)
    return result.get("ticker") if result else None


if __name__ == "__main__":
    db = EntityDatabase()
    
    # Test lookups
    test_companies = [
        "Pfizer",
        "Merck",
        "Moderna",
        "Unknown Pharma Co",
    ]
    
    for company in test_companies:
        result = db.lookup_company_ticker(company)
        print(f"{company}: {result}")
