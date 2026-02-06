"""
FDA Collector - Monitor FDA approvals, rejections, drug labels, and events

Uses open.fda.gov API with proper rate limiting, caching, and error handling.
API documentation: https://open.fda.gov/apis/
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from functools import lru_cache
import time
import hashlib
import json
import sys

sys.path.insert(0, str(__file__).replace('collectors/fda.py', ''))
from utils.config import config
from utils.logger import logger


class FDACollector:
    """Collect FDA drug/device data using open.fda.gov API

    Implements:
    - Rate limiting (respect API quotas)
    - Response caching
    - Proper error handling and retry logic
    - Multiple endpoint support (drug, event, enforcement)
    - Field filtering for efficiency

    Endpoints:
        - /drug/label.json: Drug prescribing information
        - /drug/enforcement.json: Drug recalls and safety alerts
        - /drug/event.json: Adverse event reports
        - /device/event.json: Medical device adverse events
        - /device/enforcement.json: Device recalls
    """

    BASE_URL = "https://api.fda.gov"
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    REQUEST_TIMEOUT = 30
    DEFAULT_LIMIT = 25

    def __init__(self, api_key: Optional[str] = None):
        """Initialize FDA collector

        Args:
            api_key: Optional API key for higher rate limits
        """
        self.api_key = api_key or getattr(config, 'FDA_API_KEY', None)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MedTradeSignals/1.0",
            "Accept": "application/json"
        })

        # Simple in-memory cache with timestamps
        self._cache = {}
        self._cache_ttl = 1800  # 30 minutes

        logger.info("Initialized FDA collector")

    def _cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key from endpoint and parameters"""
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(f"{endpoint}:{params_str}".encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get cached response if valid"""
        if key in self._cache:
            cached_data, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit: {key[:16]}...")
                return cached_data
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Dict):
        """Store response in cache"""
        self._cache[key] = (data, time.time())

    def _make_request(
        self,
        endpoint: str,
        params: Dict,
        timeout: int = REQUEST_TIMEOUT,
        retries: int = MAX_RETRIES
    ) -> Optional[Dict]:
        """Make request to open.fda.gov API with retry logic

        Args:
            endpoint: API endpoint (e.g., "drug/label.json")
            params: Query parameters
            timeout: Request timeout in seconds
            retries: Number of retry attempts

        Returns:
            Response JSON or None on failure
        """
        # Check cache first
        cache_key = self._cache_key(endpoint, params)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Add API key if available
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()

                data = response.json()

                # Check for API errors
                if "error" in data:
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    error_code = data.get("error", {}).get("code", "unknown")

                    # Handle rate limiting
                    if error_code == "RATE_LIMIT_EXCEEDED":
                        logger.warning("Rate limit exceeded, waiting before retry")
                        if attempt < retries - 1:
                            time.sleep(self.RETRY_DELAY * (attempt + 1))
                            continue

                    logger.error(f"FDA API error: {error_msg} (code: {error_code})")
                    return None

                # Cache successful response
                self._set_cache(cache_key, data)
                return data

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logger.warning("Rate limited, waiting before retry")
                    if attempt < retries - 1:
                        time.sleep(self.RETRY_DELAY * (attempt + 1))
                        continue
                logger.error(f"HTTP error: {e}")
                if attempt < retries - 1:
                    time.sleep(self.RETRY_DELAY)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < retries - 1:
                    time.sleep(self.RETRY_DELAY)

        return None

    def get_drug_labels(
        self,
        drug_name: Optional[str] = None,
        generic_name: Optional[str] = None,
        manufacturer: Optional[str] = None,
        limit: int = DEFAULT_LIMIT
    ) -> List[Dict]:
        """Get drug labeling information (prescribing info)

        Args:
            drug_name: Brand name of the drug
            generic_name: Generic/active ingredient name
            manufacturer: Drug manufacturer name
            limit: Maximum number of results

        Returns:
            List of drug label dictionaries

        Example:
            >>> collector = FDACollector()
            >>> labels = collector.get_drug_labels(drug_name="Tylenol")
        """
        search_parts = []

        if drug_name:
            search_parts.append(f'openfda.brand_name:"{drug_name}"')
        if generic_name:
            search_parts.append(f'openfda.generic_name:"{generic_name}"')
        if manufacturer:
            search_parts.append(f'openfda.manufacturer_name:"{manufacturer}"')

        if not search_parts:
            logger.error("Must provide at least one search parameter")
            return []

        search_query = "+AND+".join(search_parts)

        params = {
            "search": search_query,
            "limit": limit
        }

        try:
            logger.info(f"Fetching drug labels: {search_query}")
            data = self._make_request("drug/label.json", params)

            if not data:
                return []

            results = data.get("results", [])
            logger.info(f"Found {len(results)} drug labels")

            return [self._parse_drug_label(r) for r in results]

        except Exception as e:
            logger.error(f"Drug labels fetch failed: {e}")
            return []

    def _parse_drug_label(self, result: Dict) -> Dict:
        """Parse drug label record from API response

        Args:
            result: Raw drug label data from API

        Returns:
            Structured dictionary with key fields
        """
        openfda = result.get("openfda", {})

        return {
            "spl_id": result.get("id", ""),
            "brand_name": openfda.get("brand_name", [""])[0] if openfda.get("brand_name") else "",
            "generic_name": openfda.get("generic_name", [""])[0] if openfda.get("generic_name") else "",
            "manufacturer": openfda.get("manufacturer_name", [""])[0] if openfda.get("manufacturer_name") else "",
            "product_type": openfda.get("product_type", [""])[0] if openfda.get("product_type") else "",
            "route": openfda.get("route", [""])[0] if openfda.get("route") else "",
            "substance_name": openfda.get("substance_name", [""])[0] if openfda.get("substance_name") else "",
            "indications_and_usage": result.get("indications_and_usage", [{}])[0].get("") if result.get("indications_and_usage") else "",
            "warnings": result.get("warnings", [{}])[0].get("") if result.get("warnings") else "",
            "adverse_reactions": result.get("adverse_reactions", [{}])[0].get("") if result.get("adverse_reactions") else "",
            "dosage_and_administration": result.get("dosage_and_administration", [{}])[0].get("") if result.get("dosage_and_administration") else "",
            "effective_time": result.get("effective_time", ""),
            "url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={result.get('setid', '')}"
        }

    def get_drug_events(
        self,
        drug_name: Optional[str] = None,
        days_back: int = 30,
        limit: int = DEFAULT_LIMIT
    ) -> List[Dict]:
        """Get adverse drug event reports

        Args:
            drug_name: Drug name to filter by
            days_back: Search events from last N days
            limit: Maximum number of results

        Returns:
            List of adverse event reports

        Note:
            FDA adverse events are reported voluntarily; this data
            may not represent all events.
        """
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        date_to = datetime.now().strftime("%Y%m%d")

        search_parts = [f"receive_date:[{date_from}+TO+{date_to}]"]

        if drug_name:
            search_parts.append(f'patient.drug.medicinalproduct:"{drug_name}"')

        search_query = "+AND+".join(search_parts)

        params = {
            "search": search_query,
            "limit": limit,
            "sort": "receive_date:desc"
        }

        try:
            logger.info(f"Fetching adverse events: {search_query[:100]}...")
            data = self._make_request("drug/event.json", params)

            if not data:
                return []

            results = data.get("results", [])
            logger.info(f"Found {len(results)} adverse events")

            return [self._parse_drug_event(r) for r in results]

        except Exception as e:
            logger.error(f"Adverse events fetch failed: {e}")
            return []

    def _parse_drug_event(self, result: Dict) -> Dict:
        """Parse adverse drug event record

        Args:
            result: Raw event data from API

        Returns:
            Structured dictionary with key fields
        """
        patient = result.get("patient", {})
        drugs = patient.get("drug", [])

        primary_drug = drugs[0] if drugs else {}

        return {
            "safetyreportid": result.get("safetyreportid", ""),
            "receive_date": result.get("receive_date", ""),
            "primary_drug": primary_drug.get("medicinalproduct", ""),
            "drug_indication": primary_drug.get("drugindication", ""),
            "reaction": patient.get("reaction", [{}])[0].get("reactionmeddrapt", "") if patient.get("reaction") else "",
            "outcome": patient.get("reaction", [{}])[0].get("outcome", "") if patient.get("reaction") else "",
            "reporter_country": result.get("primarysourcecountry", ""),
            "age": patient.get("patientonsetage", ""),
            "sex": patient.get("patientsex", ""),
            "serious": result.get("serious", "1") == "1",
            "url": f"https://fis.fda.gov/sense/app/d10be6bb-4b0c-4343-a8f9-793a5220893b/state/analysis"
        }

    def get_drug_recalls(
        self,
        drug_name: Optional[str] = None,
        days_back: int = 90,
        limit: int = DEFAULT_LIMIT
    ) -> List[Dict]:
        """Get drug enforcement actions (recalls, safety alerts)

        Args:
            drug_name: Drug name to filter by
            days_back: Search recalls from last N days
            limit: Maximum number of results

        Returns:
            List of drug recall/enforcement records
        """
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        date_to = datetime.now().strftime("%Y%m%d")

        search_parts = [f"recall_initiation_date:[{date_from}+TO+{date_to}]"]

        if drug_name:
            search_parts.append(f'openfda.brand_name:"{drug_name}"')

        search_query = "+AND+".join(search_parts)

        params = {
            "search": search_query,
            "limit": limit,
            "sort": "recall_initiation_date:desc"
        }

        try:
            logger.info(f"Fetching drug recalls: {search_query[:100]}...")
            data = self._make_request("drug/enforcement.json", params)

            if not data:
                return []

            results = data.get("results", [])
            logger.info(f"Found {len(results)} drug recalls")

            return [self._parse_enforcement(r) for r in results]

        except Exception as e:
            logger.error(f"Drug recalls fetch failed: {e}")
            return []

    def get_device_recalls(
        self,
        device_name: Optional[str] = None,
        days_back: int = 90,
        limit: int = DEFAULT_LIMIT
    ) -> List[Dict]:
        """Get medical device recalls

        Args:
            device_name: Device name to filter by
            days_back: Search recalls from last N days
            limit: Maximum number of results

        Returns:
            List of device recall records
        """
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        date_to = datetime.now().strftime("%Y%m%d")

        search_parts = [f"recall_initiation_date:[{date_from}+TO+{date_to}]"]

        if device_name:
            search_parts.append(f'product_description:"{device_name}"')

        search_query = "+AND+".join(search_parts)

        params = {
            "search": search_query,
            "limit": limit,
            "sort": "recall_initiation_date:desc"
        }

        try:
            logger.info(f"Fetching device recalls: {search_query[:100]}...")
            data = self._make_request("device/enforcement.json", params)

            if not data:
                return []

            results = data.get("results", [])
            logger.info(f"Found {len(results)} device recalls")

            return [self._parse_enforcement(r) for r in results]

        except Exception as e:
            logger.error(f"Device recalls fetch failed: {e}")
            return []

    def _parse_enforcement(self, result: Dict) -> Dict:
        """Parse enforcement/recall record

        Args:
            result: Raw enforcement data from API

        Returns:
            Structured dictionary with key fields
        """
        return {
            "recall_id": result.get("recall_number", ""),
            "product_type": result.get("product_type", ""),
            "product_description": result.get("product_description", ""),
            "code_info": result.get("code_info", ""),
            "recalling_firm": result.get("recalling_firm", ""),
            "initiation_date": result.get("recall_initiation_date", ""),
            "classification": result.get("classification", ""),
            "status": result.get("status", ""),
            "distribution_pattern": result.get("distribution_pattern", ""),
            "country": result.get("country", ""),
            "quantity_in_commerce": result.get("quantity_in_commerce", ""),
            "reason_for_recall": result.get("reason_for_recall", ""),
            "url": result.get("url", "")
        }

    def search_drugs_by_indication(
        self,
        indication: str,
        limit: int = DEFAULT_LIMIT
    ) -> List[Dict]:
        """Search for drugs used for a specific indication

        Args:
            indication: Medical condition or indication
            limit: Maximum number of results

        Returns:
            List of drugs with labels matching the indication

        Example:
            >>> collector = FDACollector()
            >>> drugs = collector.search_drugs_by_indication("hypertension")
        """
        params = {
            "search": f'indications_and_usage:"{indication}"',
            "limit": limit
        }

        try:
            logger.info(f"Searching drugs for indication: {indication}")
            data = self._make_request("drug/label.json", params)

            if not data:
                return []

            results = data.get("results", [])
            logger.info(f"Found {len(results)} drugs for {indication}")

            return [self._parse_drug_label(r) for r in results]

        except Exception as e:
            logger.error(f"Indication search failed: {e}")
            return []

    def collect(
        self,
        days_back: int = 30,
        drug_name: Optional[str] = None
    ) -> Dict:
        """Main collection method - gather all relevant FDA data

        Args:
            days_back: Lookback period for events and recalls
            drug_name: Optional drug name to filter results

        Returns:
            Dictionary containing:
                - drug_labels: Drug labeling information
                - adverse_events: Adverse event reports
                - drug_recalls: Drug recalls
                - device_recalls: Medical device recalls

        Example:
            >>> collector = FDACollector()
            >>> data = collector.collect(days_back=7, drug_name="lisinopril")
        """
        logger.info("Collecting FDA data")

        result = {
            "drug_labels": [],
            "adverse_events": [],
            "drug_recalls": [],
            "device_recalls": [],
            "collected_at": datetime.now().isoformat()
        }

        if drug_name:
            # Get labels for specific drug
            result["drug_labels"] = self.get_drug_labels(drug_name=drug_name)
            result["adverse_events"] = self.get_drug_events(drug_name=drug_name, days_back=days_back)
            result["drug_recalls"] = self.get_drug_recalls(drug_name=drug_name, days_back=days_back)
        else:
            # Get general data without drug filter
            result["drug_recalls"] = self.get_drug_recalls(days_back=days_back)
            result["device_recalls"] = self.get_device_recalls(days_back=days_back)

        return result


if __name__ == "__main__":
    collector = FDACollector()

    # Example 1: Get drug labels
    print("\n=== Drug Labels ===")
    labels = collector.get_drug_labels(drug_name="Lipitor")
    for label in labels[:3]:
        print(f"\nBrand: {label.get('brand_name', 'N/A')}")
        print(f"Generic: {label.get('generic_name', 'N/A')}")
        print(f"Manufacturer: {label.get('manufacturer', 'N/A')}")

    # Example 2: Get adverse events
    print("\n=== Recent Adverse Events ===")
    events = collector.get_drug_events(days_back=7)
    print(f"Found {len(events)} events")

    # Example 3: Get recalls
    print("\n=== Recent Drug Recalls ===")
    recalls = collector.get_drug_recalls(days_back=30)
    for recall in recalls[:3]:
        print(f"\nProduct: {recall.get('product_description', 'N/A')}")
        print(f"Reason: {recall.get('reason_for_recall', 'N/A')}")
        print(f"Date: {recall.get('initiation_date', 'N/A')}")
