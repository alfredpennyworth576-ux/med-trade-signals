"""
FDA Collector - Monitor FDA approvals, rejections, and clearances
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sys
sys.path.insert(0, str(__file__).replace('collectors/fda.py', ''))
from utils.config import config
from utils.logger import logger

class FDACollector:
    """Collect FDA drug/device decisions"""
    
    BASE_URL = "https://api.fda.gov/drug"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MedTradeSignals/1.0"})
    
    def get_approvals(self, days_back: int = 30, limit: int = 50) -> List[Dict]:
        """Get recent FDA approvals"""
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        
        query = f"type:NEWDrugApplication actiondate:>={date_from}"
        
        try:
            logger.info("Fetching FDA approvals")
            response = self.session.get(
                f"{self.BASE_URL}/approvals.json",
                params={
                    "search": query,
                    "limit": limit,
                    "sort": "actiondate"
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            logger.info(f"Found {len(results)} approvals")
            return [self._parse_approval(r) for r in results]
            
        except Exception as e:
            logger.error(f"FDA approvals fetch failed: {e}")
            return []
    
    def get_rejections(self, days_back: int = 30, limit: int = 50) -> List[Dict]:
        """Get recent FDA rejections"""
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        
        query = f"actiontype:TYPE III PARAPHERNAL EXCH actiondate:>={date_from}"
        
        try:
            logger.info("Fetching FDA rejections")
            response = self.session.get(
                f"{self.BASE_URL}/approvals.json",
                params={
                    "search": query,
                    "limit": limit
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            logger.info(f"Found {len(results)} rejections")
            return [self._parse_approval(r) for r in results]
            
        except Exception as e:
            logger.error(f"FDA rejections fetch failed: {e}")
            return []
    
    def _parse_approval(self, result: Dict) -> Dict:
        """Parse FDA approval record"""
        return {
            "fda_id": result.get("application_number", ""),
            "company": result.get("sponsor_name", ""),
            "drug_name": result.get("drug_name", ""),
            "indication": result.get("indication", ""),
            "action_date": result.get("action_date", ""),
            "action_type": result.get("action_type", ""),
            "status": result.get("application_status", ""),
            "url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={result.get('application_number', '')}"
        }
    
    def get_drug_labels(self, drug_name: str, limit: int = 10) -> List[Dict]:
        """Get drug labels (prescribing information)"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/label.json",
                params={"search": f'drug_name:"{drug_name}"', "limit": limit},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            return data.get("results", [])
            
        except Exception as e:
            logger.error(f"FDA labels fetch failed: {e}")
            return []
    
    def collect(self) -> Dict:
        """Main collection method - get all FDA data"""
        logger.info("Collecting FDA data")
        
        approvals = self.get_approvals()
        rejections = self.get_rejections()
        
        return {
            "approvals": approvals,
            "rejections": rejections,
            "collected_at": datetime.now().isoformat()
        }


if __name__ == "__main__":
    collector = FDACollector()
    data = collector.collect()
    
    print(f"\n📋 Approvals: {len(data['approvals'])}")
    for item in data['approvals'][:3]:
        print(f"  - {item.get('drug_name', 'N/A')} ({item.get('company', 'N/A')})")
