"""
REST API for signal retrieval
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Optional
import json
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(__file__).replace('output/api.py', ''))
from utils.config import config
from utils.logger import setup_logger

logger = setup_logger("api")

app = FastAPI(
    title="Med-Trade-Signals API",
    description="REST API for retrieving trading signals from medical news",
    version="1.0.0"
)


def load_signals() -> List[dict]:
    """Load all signals from the signals directory"""
    signals = []
    signals_dir = Path(config.signals_dir)
    
    if not signals_dir.exists():
        logger.warning(f"Signals directory does not exist: {signals_dir}")
        return signals
    
    for signal_file in signals_dir.glob("*.json"):
        try:
            with open(signal_file, 'r') as f:
                signal_data = json.load(f)
                signals.append(signal_data)
        except Exception as e:
            logger.error(f"Error loading signal file {signal_file}: {e}")
    
    # Sort by created_at, newest first
    signals.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    logger.debug(f"Loaded {len(signals)} signals")
    return signals


def get_signal_by_id(signal_id: str) -> Optional[dict]:
    """Get a specific signal by ID"""
    signals = load_signals()
    for signal in signals:
        if signal.get('signal_id') == signal_id:
            return signal
    return None


@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "online",
        "service": "Med-Trade-Signals API",
        "version": "1.0.0"
    }


@app.get("/signals")
async def list_signals(
    limit: Optional[int] = None,
    ticker: Optional[str] = None,
    min_confidence: Optional[int] = None,
    signal_type: Optional[str] = None
) -> List[dict]:
    """
    List all signals with optional filtering
    
    Parameters:
    - limit: Maximum number of signals to return (default: all)
    - ticker: Filter by ticker symbol
    - min_confidence: Filter by minimum confidence score (0-100)
    - signal_type: Filter by signal type (FDA_APPROVAL, TRIAL_SUCCESS, etc.)
    """
    signals = load_signals()
    
    # Apply filters
    if ticker:
        signals = [s for s in signals if s.get('ticker', '').upper() == ticker.upper()]
    
    if min_confidence is not None:
        signals = [s for s in signals if s.get('confidence', 0) >= min_confidence]
    
    if signal_type:
        signals = [s for s in signals if s.get('signal_type') == signal_type]
    
    # Apply limit
    if limit:
        signals = signals[:limit]
    
    logger.info(f"Returning {len(signals)} signals (filters: ticker={ticker}, min_confidence={min_confidence}, signal_type={signal_type})")
    return signals


@app.get("/signals/{signal_id}")
async def get_signal(signal_id: str) -> dict:
    """
    Get a specific signal by ID
    
    Returns:
    - Signal details if found
    - 404 error if signal not found
    """
    signal = get_signal_by_id(signal_id)
    
    if not signal:
        logger.warning(f"Signal not found: {signal_id}")
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    
    logger.debug(f"Retrieved signal: {signal_id}")
    return signal


@app.get("/signals/latest")
async def get_latest_signals(limit: int = 10) -> List[dict]:
    """
    Get the most recent signals
    
    Parameters:
    - limit: Number of recent signals to return (default: 10)
    """
    signals = load_signals()
    recent_signals = signals[:limit]
    
    logger.info(f"Returning {len(recent_signals)} latest signals")
    return recent_signals


@app.get("/signals/tickers")
async def list_tickers() -> dict:
    """
    List all unique tickers found in signals with counts
    """
    signals = load_signals()
    ticker_counts = {}
    
    for signal in signals:
        ticker = signal.get('ticker')
        if ticker:
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
    
    # Sort by count, descending
    sorted_tickers = dict(sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True))
    
    logger.info(f"Found {len(sorted_tickers)} unique tickers")
    return {"tickers": sorted_tickers, "count": len(sorted_tickers)}


@app.get("/signals/stats")
async def get_stats() -> dict:
    """
    Get overall statistics about signals
    """
    signals = load_signals()
    
    if not signals:
        return {
            "total_signals": 0,
            "message": "No signals found"
        }
    
    # Calculate statistics
    total_signals = len(signals)
    avg_confidence = sum(s.get('confidence', 0) for s in signals) / total_signals
    
    # Sentiment distribution
    sentiment_counts = {}
    for signal in signals:
        sentiment = signal.get('sentiment', 'unknown')
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
    
    # Signal type distribution
    type_counts = {}
    for signal in signals:
        signal_type = signal.get('signal_type', 'unknown')
        type_counts[signal_type] = type_counts.get(signal_type, 0) + 1
    
    # Top tickers
    ticker_counts = {}
    for signal in signals:
        ticker = signal.get('ticker')
        if ticker:
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
    top_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "total_signals": total_signals,
        "average_confidence": round(avg_confidence, 2),
        "sentiment_distribution": sentiment_counts,
        "signal_type_distribution": type_counts,
        "top_tickers": [{"ticker": t, "count": c} for t, c in top_tickers],
        "latest_signal_date": signals[0].get('created_at') if signals else None,
        "oldest_signal_date": signals[-1].get('created_at') if signals else None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
