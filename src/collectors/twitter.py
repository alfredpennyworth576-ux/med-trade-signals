"""
Twitter/X Collector - Collect medical/ticker tweets
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import sys
sys.path.insert(0, str(__file__).replace('collectors/twitter.py', ''))
from utils.config import config
from utils.logger import logger

class TwitterCollector:
    """Collect tweets about healthcare and tickers"""
    
    BASE_URL = "https://api.twitter.com/2"
    
    def __init__(self):
        self.bearer_token = config.TWITTER_BEARER_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.bearer_token}"
        })
    
    def search_tweets(self, query: str, max_results: int = 100) -> List[Dict]:
        """Search for tweets matching query"""
        if not self.bearer_token:
            logger.warning("Twitter bearer token not configured")
            return []
        
        url = f"{self.BASE_URL}/tweets/search/recent"
        
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,author_id,context_annotations",
            "expansions": "author_id"
        }
        
        try:
            logger.info(f"Twitter search: {query}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            tweets = []
            for tweet in data.get("data", []):
                tweets.append({
                    "id": tweet.get("id"),
                    "text": tweet.get("text"),
                    "created_at": tweet.get("created_at"),
                    "metrics": tweet.get("public_metrics", {}),
                    "author_id": tweet.get("author_id")
                })
            
            logger.info(f"Found {len(tweets)} tweets")
            return tweets
            
        except Exception as e:
            logger.error(f"Twitter search failed: {e}")
            return []
    
    def get_healthcare_tweets(self, hours_back: int = 24) -> List[Dict]:
        """Get tweets about healthcare/biotech"""
        since = (datetime.now() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        queries = [
            '(FDA OR "clinical trial" OR biotech) lang:en',
            '(JNJ OR PFE OR MRK OR ABBV OR MRNA) (FDA OR approval OR trial) lang:en',
            '("phase 3" OR "phase 2") (drug OR treatment) lang:en',
            'medical device FDA approval lang:en'
        ]
        
        tweets = []
        for query in queries:
            results = self.search_tweets(f"{query} since:{since}", max_results=50)
            for t in results:
                t["query"] = query
            tweets.extend(results)
            time.sleep(1)  # Rate limiting
        
        return sorted(tweets, key=lambda x: x.get("metrics", {}).get("retweet_count", 0), reverse=True)
    
    def get_ticker_sentiment(self, ticker: str, hours_back: int = 24) -> Dict:
        """Get sentiment for a ticker based on recent tweets"""
        since = (datetime.now() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        query = f"${ticker} (FDA OR approval OR trial OR earnings OR upgrade OR downgrade) lang:en since:{since}"
        tweets = self.search_tweets(query, max_results=100)
        
        if not tweets:
            return {"ticker": ticker, "sentiment": "neutral", "count": 0}
        
        # Simple sentiment analysis
        positive_words = ["up", "buy", "upgrade", "bullish", "growth", "profit", "success", "approve"]
        negative_words = ["down", "sell", "downgrade", "bearish", "loss", "failure", "reject", "lawsuit"]
        
        pos_count = 0
        neg_count = 0
        
        for tweet in tweets:
            text = tweet.get("text", "").lower()
            pos_count += sum(1 for w in positive_words if w in text)
            neg_count += sum(1 for w in negative_words if w in text)
        
        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        return {
            "ticker": ticker,
            "sentiment": sentiment,
            "count": len(tweets),
            "positive_signals": pos_count,
            "negative_signals": neg_count,
            "top_tweets": tweets[:3]
        }
    
    def collect(self, ticker: str = None) -> Dict:
        """Main collection method"""
        logger.info("Collecting Twitter data")
        
        if ticker:
            sentiment = self.get_ticker_sentiment(ticker)
            return {
                "ticker": ticker,
                "sentiment": sentiment,
                "collected_at": datetime.now().isoformat()
            }
        
        return {
            "healthcare_tweets": self.get_healthcare_tweets(),
            "collected_at": datetime.now().isoformat()
        }


if __name__ == "__main__":
    collector = TwitterCollector()
    
    if collector.bearer_token:
        tweets = collector.get_healthcare_tweets(hours=6)
        print(f"\n🐦 Found {len(tweets)} healthcare tweets")
        for t in tweets[:3]:
            print(f"  - {t.get('text', '')[:80]}...")
    else:
        print("\n⚠️ Twitter bearer token not configured")
        print("Set TWITTER_BEARER_TOKEN in .env")
