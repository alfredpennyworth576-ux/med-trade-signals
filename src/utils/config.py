"""
Configuration for Med-Trade-Signals Pipeline
"""
import os
from dataclasses import dataclass
from typing import Dict

@dataclass
class Config:
    """Main configuration class"""
    
    # Data directories
    DATA_DIR: str = "data"
    RAW_DIR: str = "data/raw"
    PROCESSED_DIR: str = "data/processed"
    SIGNALS_DIR: str = "data/signals"
    
    # API Keys (from environment)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # PubMed Configuration
    PUBMED_EMAIL: str = os.getenv("PUBMED_EMAIL", "signals@example.com")
    PUBMED_TOOL: str = "MedTradeSignals/1.0"
    
    # FDA API
    FDA_API_URL: str = "https://api.fda.gov/drug"
    
    # Reddit API
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = "MedTradeSignals/1.0"
    
    # SEC API
    SEC_API_URL: str = "https://data.sec.gov"
    
    # Discord Webhook (for alerts)
    DISCORD_WEBHOOK: str = os.getenv("DISCORD_WEBHOOK", "")
    
    # Signal Settings
    MIN_CONFIDENCE: int = 50
    SIGNAL_CACHE_HOURS: int = 24
    
    # Ticker Mapping (major pharma)
    TICKER_MAP: Dict[str, str] = None
    
    def __post_init__(self):
        """Initialize ticker mapping"""
        self.TICKER_MAP = {
            # Major Pharma
            "Johnson & Johnson": "JNJ",
            "Pfizer": "PFE",
            "Merck": "MRK",
            "AbbVie": "ABBV",
            "Bristol Myers": "BMY",
            "BMS": "BMY",
            "Novartis": "NVS",
            "Roche": "RHHBY",
            "Sanofi": "SNY",
            "AstraZeneca": "AZN",
            "GSK": "GSK",
            "Amgen": "AMGN",
            "Gilead": "GILD",
            "Regeneron": "REGN",
            "Moderna": "MRNA",
            "BioNTech": "BNTX",
            "Vertex": "VRTX",
            "Illumina": "ILMN",
            "Danaher": "DHR",
            "Thermo Fisher": "TMO",
            # Medical Devices
            "Medtronic": "MDT",
            "Abbott": "ABT",
            "Boston Scientific": "BSX",
            "Stryker": "SYK",
            "GE Healthcare": "GEHC",
            "Philips": "PHG",
            "Siemens Healthineers": "SHL",
            # Diagnostic
            "Quest Diagnostics": "DGX",
            "Labcorp": "LH",
        }
    
    @property
    def data_dir(self) -> str:
        os.makedirs(self.DATA_DIR, exist_ok=True)
        return self.DATA_DIR
    
    @property 
    def raw_dir(self) -> str:
        os.makedirs(self.RAW_DIR, exist_ok=True)
        return self.RAW_DIR
    
    @property
    def signals_dir(self) -> str:
        os.makedirs(self.SIGNALS_DIR, exist_ok=True)
        return self.SIGNALS_DIR

# Singleton config
config = Config()
