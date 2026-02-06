"""
Main Pipeline - Orchestrates the entire signal generation pipeline
"""
import json
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(__file__).replace('pipeline.py', ''))

from signals.generator import SignalGenerator
from utils.config import config
from utils.logger import logger

def save_signals(signals: list, output_dir: str = None):
    """Save signals to JSON file"""
    if output_dir is None:
        output_dir = config.signals_dir
    
    Path(output_dir).mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"{output_dir}/signals_{timestamp}.json"
    
    with open(filepath, "w") as f:
        json.dump([s.to_dict() for s in signals], f, indent=2)
    
    logger.info(f"Saved {len(signals)} signals to {filepath}")
    return filepath

def save_latest(signals: list, filepath: str = "data/signals/latest.json"):
    """Save as latest.json for quick access"""
    with open(filepath, "w") as f:
        json.dump([s.to_dict() for s in signals], f, indent=2)
    
    logger.info(f"Updated latest.json")

def print_summary(signals: list):
    """Print signal summary"""
    print("\n" + "="*60)
    print("📊 MED-TRADE-SIGNALS PIPELINE COMPLETE")
    print("="*60)
    print(f"\nTotal Signals: {len(signals)}")
    
    # By type
    by_type = {}
    for s in signals:
        by_type[s.signal_type] = by_type.get(s.signal_type, 0) + 1
    
    print("\nBy Type:")
    for stype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {stype}: {count}")
    
    # By sentiment
    by_sentiment = {}
    for s in signals:
        by_sentiment[s.sentiment] = by_sentiment.get(s.sentiment, 0) + 1
    
    print("\nBy Sentiment:")
    for sent, count in sorted(by_sentiment.items(), key=lambda x: -x[1]):
        emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(sent, "⚪")
        print(f"  {emoji} {sent}: {count}")
    
    # Top signals
    print("\n🎯 Top Signals:")
    for s in signals[:5]:
        print(f"  [{s.confidence}%] {s.ticker} - {s.headline[:50]}...")
    
    print("\n" + "="*60)

def run_pipeline():
    """Main pipeline runner"""
    logger.info("Starting Med-Trade-Signals Pipeline")
    start_time = datetime.now()
    
    try:
        # Generate signals
        generator = SignalGenerator()
        signals = generator.generate_all()
        
        # Save outputs
        save_signals(signals)
        save_latest(signals)
        
        # Print summary
        print_summary(signals)
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Pipeline completed in {duration:.1f}s")
        
        return signals
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise

def main():
    """CLI entrypoint"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Medical News → Trading Signals")
    parser.add_argument("--source", choices=["pubmed", "fda", "reddit", "all"], 
                       default="all", help="Data source to use")
    parser.add_argument("--output", "-o", default="data/signals", 
                       help="Output directory")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Quiet mode (less output)")
    
    args = parser.parse_args()
    
    if args.quiet:
        import logging
        logging.getLogger().setLevel(logging.WARNING)
    
    generator = SignalGenerator()
    signals = []
    
    if args.source in ["pubmed", "all"]:
        signals.extend(generator.generate_from_pubmed())
    if args.source in ["fda", "all"]:
        signals.extend(generator.generate_from_fda())
    if args.source in ["reddit", "all"]:
        signals.extend(generator.generate_from_reddit())
    
    if not args.quiet:
        print_summary(signals)
    
    save_signals(signals, args.output)
    
    return signals

if __name__ == "__main__":
    main()
