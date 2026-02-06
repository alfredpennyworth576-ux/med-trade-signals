"""
Med-Trade-Signals - Medical News → Trading Signal Pipeline
"""

__version__ = "1.0.0"
__author__ = "Alfred"

from .models import (
    SignalType,
    Sentiment,
    TradingSignal,
    PaperTrade,
    Portfolio,
    Source,
    Entity,
    ClinicalData
)

__all__ = [
    "SignalType",
    "Sentiment", 
    "TradingSignal",
    "PaperTrade",
    "Portfolio",
    "Source",
    "Entity",
    "ClinicalData"
]
