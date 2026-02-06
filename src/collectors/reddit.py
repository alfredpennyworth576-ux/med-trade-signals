"""
Reddit Collector - Monitor medical and finance subreddits

Uses PRAW (Python Reddit API Wrapper) for authenticated access,
with fallback to unauthenticated mode.
"""
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import sys
import json

sys.path.insert(0, str(__file__).replace('collectors/reddit.py', ''))
from utils.config import config
from utils.logger import logger

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not available - falling back to unauthenticated mode")


class RedditCollector:
    """Collect posts from medical and finance subreddits

    Supports two modes:
    1. Authenticated (via PRAW) - higher rate limits, more features
    2. Unauthenticated (via direct API) - limited rate limits

    Configuration:
        For authenticated mode, set these in config:
        - REDDIT_CLIENT_ID
        - REDDIT_CLIENT_SECRET
        - REDDIT_USER_AGENT
    """

    # Reddit API base URLs
    BASE_URL = "https://www.reddit.com"
    OAUTH_BASE_URL = "https://oauth.reddit.com"
    API_URL = f"{BASE_URL}/r"

    # Rate limiting for unauthenticated mode
    AUTH_REQUESTS_PER_MINUTE = 60
    UNAUTH_REQUESTS_PER_MINUTE = 30

    # Default subreddits to monitor
    MEDICAL_SUBREDDITS = [
        "medicine",
        "medical",
        "Radiology",
        "PhysicianAssistant",
        "AskDocs",
        "medicalschool",
        "Cardiology",
        "Oncology"
    ]

    FINANCE_SUBREDDITS = [
        "wallstreetbets",
        "investing",
        "StockMarket",
        "biotech",
        "stocks",
        "biopharma",
        "pharmaceuticals",
        "healthcarestocks"
    ]

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 user_agent: Optional[str] = None, use_auth: Optional[bool] = None):
        """Initialize Reddit collector

        Args:
            client_id: Reddit API client ID (for authenticated mode)
            client_secret: Reddit API client secret (for authenticated mode)
            user_agent: User agent string
            use_auth: Force authenticated mode (True) or unauthenticated (False)
                       If None, auto-detect based on credentials availability
        """
        self.client_id = client_id or getattr(config, 'REDDIT_CLIENT_ID', None)
        self.client_secret = client_secret or getattr(config, 'REDDIT_CLIENT_SECRET', None)
        self.user_agent = user_agent or getattr(config, 'REDDIT_USER_AGENT',
                                                "MedTradeSignals/1.0 by /u/medtrade")

        # Determine auth mode
        if use_auth is not None:
            self._use_auth = use_auth
        else:
            self._use_auth = (
                PRAW_AVAILABLE and
                self.client_id and
                self.client_secret
            )

        # Initialize PRAW if using authenticated mode
        self.reddit = None
        if self._use_auth and PRAW_AVAILABLE:
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent,
                    read_only=True
                )
                # Test connection
                self.reddit.user.me()
                logger.info("Reddit collector initialized with authenticated mode (PRAW)")
            except Exception as e:
                logger.warning(f"Failed to initialize PRAW auth: {e} - falling back to unauthenticated")
                self._use_auth = False
                self.reddit = None
        else:
            logger.info("Reddit collector initialized in unauthenticated mode")

        # Session for unauthenticated requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent
        })

    def _make_unauth_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        timeout: int = 30
    ) -> Optional[Dict]:
        """Make unauthenticated API request

        Args:
            endpoint: API endpoint path (e.g., "/wallstreetbets/new.json")
            params: Query parameters
            timeout: Request timeout

        Returns:
            Response JSON or None on failure
        """
        try:
            response = self.session.get(
                f"{self.API_URL}{endpoint}",
                params=params,
                timeout=timeout
            )
            response.raise_for_status()

            data = response.json()

            # Check for Reddit API errors
            if "error" in data:
                logger.error(f"Reddit API error: {data.get('error', 'Unknown')}")
                return None

            return data

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning("Reddit rate limit exceeded - wait before retrying")
            else:
                logger.error(f"Reddit HTTP error: {e}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Reddit request failed: {e}")
            return None

    def get_posts(
        self,
        subreddit: str,
        limit: int = 25,
        sort: str = "new",
        time_filter: str = "day",
        search_query: Optional[str] = None
    ) -> List[Dict]:
        """Get posts from a subreddit

        Args:
            subreddit: Subreddit name (without r/)
            limit: Maximum number of posts (max 100)
            sort: Sort order - "new", "hot", "top", "rising", "relevance"
            time_filter: Time filter for "top" sort - "hour", "day", "week", "month", "year", "all"
            search_query: Optional search query (if provided, searches within subreddit)

        Returns:
            List of post dictionaries with fields:
                - id: Post ID
                - title: Post title
                - selftext: Post body text (truncated)
                - score: Net upvotes
                - upvote_ratio: Upvote ratio (0-1)
                - num_comments: Number of comments
                - url: Full post URL
                - permalink: Reddit permalink
                - created_utc: UTC timestamp
                - created_iso: ISO format datetime
                - author: Author username
                - subreddit: Subreddit name
                - is_self: True if text post
                - link_flair_text: Post flair (if any)
                - over_18: NSFW flag
        """
        posts = []

        if self._use_auth and self.reddit:
            # Use PRAW for authenticated requests
            try:
                sub = self.reddit.subreddit(subreddit)

                if search_query:
                    # Search within subreddit
                    results = sub.search(search_query, sort=sort, limit=limit, time_filter=time_filter)
                elif sort == "hot":
                    results = sub.hot(limit=limit)
                elif sort == "top":
                    results = sub.top(limit=limit, time_filter=time_filter)
                elif sort == "rising":
                    results = sub.rising(limit=limit)
                elif sort == "new":
                    results = sub.new(limit=limit)
                else:
                    results = sub.hot(limit=limit)

                for submission in results:
                    post = self._parse_praw_submission(submission)
                    posts.append(post)

                logger.info(f"Fetched {len(posts)} posts from r/{subreddit} (authenticated)")

            except Exception as e:
                logger.error(f"PRAW request failed for r/{subreddit}: {e} - falling back to unauthenticated")
                # Try unauthenticated fallback
                posts = self._get_posts_unauth(subreddit, limit, sort, time_filter, search_query)

        else:
            # Use unauthenticated API
            posts = self._get_posts_unauth(subreddit, limit, sort, time_filter, search_query)

        return posts

    def _get_posts_unauth(
        self,
        subreddit: str,
        limit: int = 25,
        sort: str = "new",
        time_filter: str = "day",
        search_query: Optional[str] = None
    ) -> List[Dict]:
        """Get posts using unauthenticated API

        Args:
            subreddit: Subreddit name
            limit: Maximum number of posts
            sort: Sort order
            time_filter: Time filter
            search_query: Optional search query

        Returns:
            List of post dictionaries
        """
        posts = []

        try:
            endpoint = f"/{subreddit}"
            if search_query:
                endpoint += "/search"
                params = {
                    "q": search_query,
                    "restrict_sr": "on",  # Restrict to this subreddit
                    "sort": sort,
                    "t": time_filter,
                    "limit": min(limit, 100)
                }
            else:
                endpoint += f"/{sort}.json"
                params = {
                    "limit": min(limit, 100)
                }

            data = self._make_unauth_request(endpoint, params)

            if not data:
                return []

            # Parse posts from response
            for item in data.get("data", {}).get("children", []):
                post_data = item.get("data", {})
                post = self._parse_api_post(post_data)
                post["subreddit"] = subreddit
                posts.append(post)

            logger.info(f"Fetched {len(posts)} posts from r/{subreddit} (unauthenticated)")

        except Exception as e:
            logger.error(f"Unauthenticated fetch failed for r/{subreddit}: {e}")

        return posts

    def _parse_praw_submission(self, submission) -> Dict:
        """Parse PRAW submission object

        Args:
            submission: PRAW Submission object

        Returns:
            Structured post dictionary
        """
        return {
            "id": submission.id,
            "title": submission.title,
            "selftext": submission.selftext[:1000] if submission.selftext else "",
            "score": submission.score,
            "upvote_ratio": submission.upvote_ratio,
            "num_comments": submission.num_comments,
            "url": f"https://reddit.com{submission.permalink}",
            "permalink": submission.permalink,
            "created_utc": submission.created_utc,
            "created_iso": datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
            "author": str(submission.author) if submission.author else "[deleted]",
            "subreddit": str(submission.subreddit),
            "is_self": submission.is_self,
            "link_flair_text": submission.link_flair_text,
            "over_18": submission.over_18
        }

    def _parse_api_post(self, post_data: Dict) -> Dict:
        """Parse post data from API response

        Args:
            post_data: Raw post data from API

        Returns:
            Structured post dictionary
        """
        return {
            "id": post_data.get("id", ""),
            "title": post_data.get("title", ""),
            "selftext": post_data.get("selftext", "")[:1000],
            "score": post_data.get("score", 0),
            "upvote_ratio": post_data.get("upvote_ratio", 0),
            "num_comments": post_data.get("num_comments", 0),
            "url": post_data.get("url", ""),
            "permalink": post_data.get("permalink", ""),
            "created_utc": post_data.get("created_utc", 0),
            "created_iso": datetime.fromtimestamp(post_data.get("created_utc", 0), tz=timezone.utc).isoformat(),
            "author": post_data.get("author", "[deleted]"),
            "is_self": post_data.get("is_self", False),
            "link_flair_text": post_data.get("link_flair_text", ""),
            "over_18": post_data.get("over_18", False)
        }

    def search_reddit(
        self,
        query: str,
        subreddits: Optional[List[str]] = None,
        sort: str = "relevance",
        time_filter: str = "week",
        limit: int = 50
    ) -> List[Dict]:
        """Search Reddit across multiple subreddits

        Args:
            query: Search query string
            subreddits: List of subreddits to search (None = all)
            sort: Sort order - "relevance", "new", "hot", "top", "comments"
            time_filter: Time filter - "hour", "day", "week", "month", "year", "all"
            limit: Maximum results

        Returns:
            List of post dictionaries
        """
        posts = []

        # Build subreddit string
        subreddit_str = ""
        if subreddits:
            subreddit_str = "+".join(subreddits)

        if self._use_auth and self.reddit:
            try:
                if subreddit_str:
                    results = self.reddit.subreddit(subreddit_str).search(
                        query, sort=sort, limit=limit, time_filter=time_filter
                    )
                else:
                    results = self.reddit.subreddit("all").search(
                        query, sort=sort, limit=limit, time_filter=time_filter
                    )

                for submission in results:
                    post = self._parse_praw_submission(submission)
                    posts.append(post)

                logger.info(f"Found {len(posts)} posts for query: {query}")

            except Exception as e:
                logger.error(f"Reddit search failed: {e}")
        else:
            # Unauthenticated search
            endpoint = "/search"
            params = {
                "q": query,
                "sort": sort,
                "t": time_filter,
                "limit": min(limit, 100)
            }
            if subreddit_str:
                params["restrict_sr"] = "on"
                params["q"] = f"{query} subreddit:{subreddit_str}"

            data = self._make_unauth_request(endpoint, params)

            if data:
                for item in data.get("data", {}).get("children", []):
                    post_data = item.get("data", {})
                    post = self._parse_api_post(post_data)
                    posts.append(post)

                logger.info(f"Found {len(posts)} posts for query: {query}")

        return posts

    def get_medical_posts(
        self,
        limit: int = 25,
        sort: str = "new",
        time_filter: str = "day",
        search_query: Optional[str] = None
    ) -> List[Dict]:
        """Get posts from medical subreddits

        Args:
            limit: Maximum posts per subreddit
            sort: Sort order
            time_filter: Time filter for searches
            search_query: Optional search query

        Returns:
            List of medical posts sorted by score
        """
        posts = []

        for sub in self.MEDICAL_SUBREDDITS:
            try:
                sub_posts = self.get_posts(
                    sub,
                    limit=limit,
                    sort=sort,
                    time_filter=time_filter,
                    search_query=search_query
                )
                posts.extend(sub_posts)

                # Small delay between subreddit requests
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to fetch from r/{sub}: {e}")

        # Sort by score (descending)
        posts.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(f"Collected {len(posts)} medical posts from {len(self.MEDICAL_SUBREDDITS)} subreddits")
        return posts

    def get_finance_posts(
        self,
        limit: int = 25,
        sort: str = "new",
        time_filter: str = "day",
        search_query: Optional[str] = None
    ) -> List[Dict]:
        """Get posts from finance subreddits

        Args:
            limit: Maximum posts per subreddit
            sort: Sort order
            time_filter: Time filter for searches
            search_query: Optional search query

        Returns:
            List of finance posts sorted by score
        """
        posts = []

        for sub in self.FINANCE_SUBREDDITS:
            try:
                sub_posts = self.get_posts(
                    sub,
                    limit=limit,
                    sort=sort,
                    time_filter=time_filter,
                    search_query=search_query
                )
                posts.extend(sub_posts)

                # Small delay between subreddit requests
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to fetch from r/{sub}: {e}")

        # Sort by score (descending)
        posts.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(f"Collected {len(posts)} finance posts from {len(self.FINANCE_SUBREDDITS)} subreddits")
        return posts

    def search_ticker_mentions(
        self,
        ticker: str,
        subreddits: Optional[List[str]] = None,
        days_back: int = 7,
        limit: int = 50
    ) -> List[Dict]:
        """Search Reddit for mentions of a stock ticker

        Args:
            ticker: Stock ticker symbol (e.g., "GILD", "MRNA")
            subreddits: Specific subreddits to search (default: finance subreddits)
            days_back: Search posts from last N days
            limit: Maximum results

        Returns:
            List of posts mentioning the ticker

        Example:
            >>> collector = RedditCollector()
            >>> posts = collector.search_ticker_mentions("MRNA")
        """
        # Default to finance subreddits if none specified
        if not subreddits:
            subreddits = self.FINANCE_SUBREDDITS

        # Time filter based on days_back
        time_filter = "day"
        if days_back <= 1:
            time_filter = "hour"
        elif days_back <= 7:
            time_filter = "week"
        elif days_back <= 30:
            time_filter = "month"
        else:
            time_filter = "year"

        # Build search query (search for ticker with $ prefix and standalone)
        query = f'"{ticker}" OR "${ticker}"'

        return self.search_reddit(
            query=query,
            subreddits=subreddits,
            sort="new",
            time_filter=time_filter,
            limit=limit
        )

    def collect(
        self,
        medical_limit: int = 25,
        finance_limit: int = 25,
        sort: str = "new",
        days_back: int = 1
    ) -> Dict:
        """Main collection method - gather posts from all monitored subreddits

        Args:
            medical_limit: Maximum posts per medical subreddit
            finance_limit: Maximum posts per finance subreddit
            sort: Sort order
            days_back: Time filter for searches

        Returns:
            Dictionary containing:
                - medical: Medical-related posts
                - finance: Finance-related posts
                - collected_at: ISO timestamp
        """
        logger.info("Collecting Reddit data")

        # Determine time filter
        time_filter = "day"
        if days_back <= 1:
            time_filter = "hour"
        elif days_back <= 7:
            time_filter = "week"
        else:
            time_filter = "month"

        medical = self.get_medical_posts(
            limit=medical_limit,
            sort=sort,
            time_filter=time_filter
        )

        finance = self.get_finance_posts(
            limit=finance_limit,
            sort=sort,
            time_filter=time_filter
        )

        return {
            "medical": medical,
            "finance": finance,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }


if __name__ == "__main__":
    collector = RedditCollector()

    print(f"\n=== Reddit Collector Status ===")
    print(f"Authenticated: {collector._use_auth}")
    print(f"PRAW Available: {PRAW_AVAILABLE}")

    # Test medical posts
    print(f"\n=== Recent Medical Posts ===")
    medical = collector.get_medical_posts(limit=10)
    for post in medical[:3]:
        print(f"\n{post.get('title', 'N/A')[:60]}...")
        print(f"  r/{post.get('subreddit')} | Score: {post.get('score')} | Comments: {post.get('num_comments')}")

    # Test finance posts
    print(f"\n=== Recent Finance Posts ===")
    finance = collector.get_finance_posts(limit=10)
    for post in finance[:3]:
        print(f"\n{post.get('title', 'N/A')[:60]}...")
        print(f"  r/{post.get('subreddit')} | Score: {post.get('score')} | Comments: {post.get('num_comments')}")

    # Test ticker search
    print(f"\n=== Ticker Search: MRNA ===")
    ticker_posts = collector.search_ticker_mentions("MRNA", limit=5)
    for post in ticker_posts[:3]:
        print(f"\n{post.get('title', 'N/A')[:60]}...")
        print(f"  r/{post.get('subreddit')} | Score: {post.get('score')}")
