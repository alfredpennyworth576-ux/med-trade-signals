"""
Main pipeline configuration with environment loading
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class Config:
    """Main configuration"""
    
    # Project paths
    PROJECT_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = PROJECT_DIR / "data"
    RAW_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DIR: Path = DATA_DIR / "processed"
    SIGNALS_DIR: Path = DATA_DIR / "signals"
    LOGS_DIR: Path = PROJECT_DIR / "logs"
    
    # API Keys
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    
    # PubMed
    PUBMED_EMAIL: str = field(default_factory=lambda: os.getenv("PUBMED_EMAIL", "signals@example.com"))
    PUBMED_TOOL: str = "MedTradeSignals/1.0"
    PUBMED_RATE_LIMIT: int = 3  # requests per second
    
    # FDA (open.fda.gov)
    FDA_API_BASE: str = "https://api.fda.gov/drug"
    FDA_RATE_LIMIT: int = 1
    
    # Reddit
    REDDIT_CLIENT_ID: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", ""))
    REDDIT_CLIENT_SECRET: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", ""))
    REDDIT_USER_AGENT: str = "MedTradeSignals/1.0"
    
    # SEC
    SEC_API_BASE: str = "https://data.sec.gov"
    
    # Twitter/X
    TWITTER_BEARER_TOKEN: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))
    
    # Discord
    DISCORD_WEBHOOK_URL: str = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", ""))
    
    # Slack
    SLACK_WEBHOOK_URL: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))
    
    # Signal Settings
    MIN_CONFIDENCE: int = 50
    SIGNAL_CACHE_HOURS: int = 24
    MAX_SIGNALS_PER_RUN: int = 50
    
    # Source Reliability Scores (0-1)
    SOURCE_RELIABILITY: Dict[str, float] = field(default_factory=lambda: {
        "fda.gov": 1.0,
        "pubmed.ncbi.nlm.nih.gov": 0.95,
        "sec.gov": 0.9,
        "reuters.com": 0.85,
        "wsj.com": 0.85,
        "reddit.com": 0.5,
        "twitter.com": 0.4,
        "cnn.com": 0.6,
        "bbc.com": 0.7,
        "forbes.com": 0.7,
    })
    
    # Ticker Mapping (major healthcare companies)
    TICKER_MAP: Dict[str, str] = field(default_factory=lambda: {
        # Major Pharma
        "Johnson & Johnson": "JNJ",
        "Pfizer": "PFE",
        "Merck": "MRK",
        "AbbVie": "ABBV",
        "Bristol Myers": "BMY",
        "Novartis": "NVS",
        "Roche": "RHHBY",
        "Sanofi": "SNY",
        "AstraZeneca": "AZN",
        "GlaxoSmithKline": "GSK",
        "GSK": "GSK",
        "Amgen": "AMGN",
        "Gilead Sciences": "GILD",
        "Regeneron": "REGN",
        "Moderna": "MRNA",
        "BioNTech": "BNTX",
        "Vertex": "VRTX",
        "Illumina": "ILMN",
        "Danaher": "DHR",
        "Thermo Fisher": "TMO",
        # Medical Devices
        "Medtronic": "MDT",
        "Abbott Laboratories": "ABT",
        "Boston Scientific": "BSX",
        "Stryker": "SYK",
        "GE Healthcare": "GEHC",
        "Philips": "PHG",
        "Siemens Healthineers": "SHL",
        "Intuitive Surgical",
        "DexCom": "DX": "ISRGCM",
        "Insulet": "PODD",
        # Diagnostics
        "Quest Diagnostics": "DGX",
        "Labcorp": "LH",
        "Dharma": "DHA",
        # Biotech
        "Biogen": "BIIB",
        "Alexion": "ALXN",
        "Incyte": "INCY",
        "Alnylam": "ALNY",
        "Exact Sciences": "EXAS",
        "Guardant Health": "GH",
        # Insurance
        "UnitedHealth": "UNH",
        "Humana": "HUM",
        "Cigna": "CI",
        "Anthem": "ELV",
    })
    
    # Clinical trial keywords
    TRIAL_KEYWORDS: List[str] = field(default_factory=lambda: [
        "phase 1", "phase 2", "phase 3", "phase 4",
        "phase i", "phase ii", "phase iii", "phase iv",
        "clinical trial", "pivotal study", "registration trial",
        "primary endpoint", "secondary endpoint",
        "statistically significant", "p-value"
    ])
    
    # FDA decision keywords
    FDA_KEYWORDS: List[str] = field(default_factory=lambda: [
        "fda approves", "fda approved", "approval",
        "fda rejects", "fda rejected", "rejection",
        "fda warning", "fda caution", "fda advisory",
        "fast track", "breakthrough therapy", "orphan drug",
        "complete response letter", " CRL "
    ])
    
    def __post_init__(self):
        """Create directories"""
        for dir_path in [self.DATA_DIR, self.RAW_DIR, self.PROCESSED_DIR, 
                        self.SIGNALS_DIR, self.LOGS_DIR]:
            dir_path.mkdir(exist_ok=True)
    
    def get_ticker(self, company_name: str) -> Optional[str]:
        """Get ticker for company name"""
        return self.TICKER_MAP.get(company_name)
    
    def lookup_ticker(self, text: str) -> Optional[str]:
        """Search for ticker in text"""
        for company, ticker in self.TICKER_MAP.items():
            if company.lower() in text.lower():
                return ticker
        return None
    
    def get_source_reliability(self, source: str) -> float:
        """Get reliability score for source"""
        for domain, score in self.SOURCE_RELIABILITY.items():
            if domain in source.lower():
                return score
        return 0.5  # Default reliability

# Global config
config = Config()
