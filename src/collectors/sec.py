"""
SEC Collector - Collect SEC filings (10-K, 10-Q, 8-K)
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import sys
sys.path.insert(0, str(__file__).replace('collectors/sec.py', ''))
from utils.config import config
from utils.logger import logger

class SECCollector:
    """Collect SEC filings using Edgar API"""
    
    BASE_URL = "https://data.sec.gov"
    USER_AGENT = "MedTradeSignals/1.0 (signals@example.com)"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
    
    def get_company_filings(self, cik: str, forms: List[str] = None, limit: int = 20) -> List[Dict]:
        """Get recent filings for a company by CIK"""
        if forms is None:
            forms = ["10-K", "10-Q", "8-K"]
        
        url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
        
        try:
            logger.info(f"Fetching SEC filings for CIK: {cik}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            filings = []
            for filing in data.get("filings", {}).get("recent", {}).get("items", [])[:limit]:
                if filing.get("form") in forms:
                    filings.append({
                        "form": filing.get("form"),
                        "filing_date": filing.get("filingDate"),
                        "accession_number": filing.get("accessionNumber"),
                        "cik": cik,
                        "company_name": filing.get("companyName"),
                        "description": filing.get("primaryDocDescription", ""),
                        "document_url": filing.get("primaryDocument", ""),
                        "size": filing.get("size", 0)
                    })
            
            logger.info(f"Found {len(filings)} filings")
            return filings
            
        except Exception as e:
            logger.error(f"SEC fetch failed for CIK {cik}: {e}")
            return []
    
    def get_company_by_ticker(self, ticker: str) -> Optional[str]:
        """Get CIK for a ticker symbol"""
        url = f"{self.BASE_URL}/themes/CORP_FINANCE/{ticker}.json"
        
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("cik", "")
        except:
            pass
        
        # Fallback: use ticker JSON files
        ticker_url = f"{self.BASE_URL}/files/Ticker-CIK/{ticker}.json"
        try:
            response = self.session.get(ticker_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                for entry in data:
                    if entry.get("ticker") == ticker:
                        return entry.get("cik_str", "").zfill(10)
        except:
            pass
        
        return None
    
    def search_company(self, name: str) -> Optional[Dict]:
        """Search for company by name"""
        url = f"{self.BASE_URL}/company_tickers.json"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            for entry in data.values():
                if name.lower() in entry.get("companyName", "").lower():
                    return {
                        "ticker": entry.get("ticker"),
                        "cik": str(entry.get("cik_str", "")).zfill(10),
                        "name": entry.get("companyName")
                    }
                    
        except Exception as e:
            logger.error(f"SEC company search failed: {e}")
        
        return None
    
    def get_10k_filings(self, ticker: str, years_back: int = 2) -> List[Dict]:
        """Get 10-K filings for a ticker"""
        cik = self.get_company_by_ticker(ticker)
        if not cik:
            logger.warning(f"Could not find CIK for ticker: {ticker}")
            return []
        
        date_from = (datetime.now() - timedelta(days=years_back*365)).strftime("%Y-%m-%d")
        filings = self.get_company_filings(cik, forms=["10-K"], limit=10)
        
        # Filter by date
        filtered = []
        for f in filings:
            if f["filing_date"] >= date_from:
                filtered.append(f)
        
        return filtered
    
    def get_8k_filings(self, ticker: str, days_back: int = 30) -> List[Dict]:
        """Get 8-K filings (material events) for a ticker"""
        cik = self.get_company_by_ticker(ticker)
        if not cik:
            return []
        
        filings = self.get_company_filings(cik, forms=["8-K"], limit=20)
        
        # Filter by date
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        filtered = [f for f in filings if f["filing_date"] >= date_from]
        
        return filtered
    
    def get_material_events(self, tickers: List[str] = None) -> List[Dict]:
        """Get material events (8-K) for multiple tickers"""
        if tickers is None:
            # Default healthcare tickers
            tickers = ["JNJ", "PFE", "MRK", "ABBV", "BMY", "NVS", "MRNA", "REGN"]
        
        events = []
        for ticker in tickers:
            filings = self.get_8k_filings(ticker, days_back=7)
            events.extend(filings)
            time.sleep(0.1)  # Rate limiting
        
        return sorted(events, key=lambda x: x.get("filing_date", ""), reverse=True)
    
    def collect(self, ticker: str = None) -> Dict:
        """Main collection method"""
        logger.info(f"Collecting SEC data for ticker: {ticker}")
        
        if ticker:
            return {
                "10k": self.get_10k_filings(ticker),
                "8k": self.get_8k_filings(ticker),
                "collected_at": datetime.now().isoformat()
            }
        
        return {
            "material_events": self.get_material_events(),
            "collected_at": datetime.now().isoformat()
        }


if __name__ == "__main__":
    collector = SECCollector()
    
    # Test with J&J
    print("\n📄 SEC Filings for JNJ:")
    cik = collector.get_company_by_ticker("JNJ")
    print(f"  CIK: {cik}")
    
    filings = collector.get_8k_filings("JNJ", days_back=30)
    for f in filings[:3]:
        print(f"  - {f['form']} ({f['filing_date']}): {f['description'][:50]}")
