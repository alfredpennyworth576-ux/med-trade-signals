"""
Reddit Collector - Monitor medical and finance subreddits
"""
import requests
from datetime import datetime
from typing import List, Dict
import sys
sys.path.insert(0, str(__file__).replace('collectors/reddit.py', ''))
from utils.config import config
from utils.logger import logger

class RedditCollector:
    """Collect posts from medical and finance subreddits"""
    
    BASE_URL = "https://www.reddit.com/r"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.REDDIT_USER_AGENT
        })
    
    def get_posts(self, subreddit: str, limit: int = 25) -> List[Dict]:
        """Get recent posts from a subreddit"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/{subreddit}/new.json",
                params={"limit": limit, "sort": "new"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            posts = []
            for item in data.get("data", {}).get("children", []):
                post = item.get("data", {})
                posts.append({
                    "id": post.get("id"),
                    "title": post.get("title"),
                    "selftext": post.get("selftext", "")[:500],
                    "score": post.get("score"),
                    "num_comments": post.get("num_comments"),
                    "url": f"https://reddit.com{post.get('permalink')}",
                    "created_utc": datetime.fromtimestamp(
                        post.get("created_utc", 0)
                    ).isoformat(),
                    "subreddit": subreddit
                })
            
            logger.info(f"Fetched {len(posts)} posts from r/{subreddit}")
            return posts
            
        except Exception as e:
            logger.error(f"Reddit fetch failed: {e}")
            return []
    
    def get_medical_posts(self) -> List[Dict]:
        """Get posts from medical subreddits"""
        subreddits = ["medicine", "medical", "Radiology", "PhysicianAssistant"]
        posts = []
        
        for sub in subreddits:
            posts.extend(self.get_posts(sub))
        
        return sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
    
    def get_finance_posts(self) -> List[Dict]:
        """Get posts from finance subreddits"""
        subreddits = ["wallstreetbets", "investing", "StockMarket", "biotech"]
        posts = []
        
        for sub in subreddits:
            posts.extend(self.get_posts(sub))
        
        return sorted(posts, key=lambda x: x.get("score", 0), reverse=True)
    
    def collect(self) -> Dict:
        """Main collection method"""
        logger.info("Collecting Reddit data")
        
        medical = self.get_medical_posts()
        finance = self.get_finance_posts()
        
        return {
            "medical": medical,
            "finance": finance,
            "collected_at": datetime.now().isoformat()
        }


if __name__ == "__main__":
    collector = RedditCollector()
    data = collector.collect()
    
    print(f"\n🏥 Medical posts: {len(data['medical'])}")
    for post in data['medical'][:2]:
        print(f"  - {post.get('title', 'N/A')[:60]}...")
    
    print(f"\n💰 Finance posts: {len(data['finance'])}")
    for post in data['finance'][:2]:
        print(f"  - {post.get('title', 'N/A')[:60]}...")
