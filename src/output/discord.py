"""
Discord webhook alerts for trading signals
"""
import requests
import time
from typing import Dict, Optional
import json
from datetime import datetime
import sys
sys.path.insert(0, str(__file__).replace('output/discord.py', ''))
from utils.config import config
from utils.logger import setup_logger

logger = setup_logger("discord")


class RateLimiter:
    """Simple rate limiter for webhook calls"""
    
    def __init__(self, min_interval: float = 1.0):
        """
        Initialize rate limiter
        
        Parameters:
        - min_interval: Minimum seconds between requests (default: 1.0)
        """
        self.min_interval = min_interval
        self.last_call_time = 0
    
    def wait_if_needed(self):
        """Wait if we need to respect rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_call_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()


# Global rate limiter instance
_rate_limiter = RateLimiter(min_interval=1.0)


def get_color_from_sentiment(sentiment: str) -> int:
    """
    Get Discord embed color based on sentiment
    
    Parameters:
    - sentiment: "positive", "negative", or "neutral"
    
    Returns:
    - Color integer (hex)
    """
    color_map = {
        "positive": 0x00ff00,   # Green
        "negative": 0xff0000,   # Red
        "neutral": 0x808080     # Gray
    }
    return color_map.get(sentiment.lower(), 0x808080)


def get_emoji_from_signal_type(signal_type: str) -> str:
    """
    Get emoji based on signal type
    
    Parameters:
    - signal_type: Type of signal (FDA_APPROVAL, TRIAL_SUCCESS, etc.)
    
    Returns:
    - Emoji string
    """
    emoji_map = {
        "FDA_APPROVAL": "🏥",
        "FDA_REJECTION": "🚫",
        "TRIAL_SUCCESS": "📈",
        "TRIAL_FAILURE": "📉",
        "PRICE_TARGET_UP": "🎯",
        "REDDIT_SENTIMENT": "💬"
    }
    return emoji_map.get(signal_type, "📊")


def create_discord_embed(signal: Dict) -> Dict:
    """
    Create a Discord embed from a trading signal
    
    Parameters:
    - signal: Signal dictionary (from TradingSignal.to_dict())
    
    Returns:
    - Discord embed dictionary
    """
    # Get sentiment color
    color = get_color_from_sentiment(signal.get('sentiment', 'neutral'))
    
    # Get emoji
    emoji = get_emoji_from_signal_type(signal.get('signal_type', ''))
    
    # Create embed title
    ticker = signal.get('ticker', 'UNKNOWN')
    signal_type = signal.get('signal_type', 'UNKNOWN')
    title = f"{emoji} {signal_type.replace('_', ' ')} - ${ticker}"
    
    # Create embed
    embed = {
        "title": title,
        "description": signal.get('headline', ''),
        "color": color,
        "fields": [
            {
                "name": "📊 Confidence",
                "value": f"{signal.get('confidence', 0)}%",
                "inline": True
            },
            {
                "name": "💹 Sentiment",
                "value": signal.get('sentiment', 'neutral').capitalize(),
                "inline": True
            }
        ],
        "footer": {
            "text": f"ID: {signal.get('signal_id', 'N/A')} | {signal.get('created_at', '')}"
        }
    }
    
    # Add company name if available
    if signal.get('company_name'):
        embed["fields"].append({
            "name": "🏢 Company",
            "value": signal.get('company_name'),
            "inline": True
        })
    
    # Add target prices if available
    upside = signal.get('target_upside')
    downside = signal.get('target_downside')
    
    if upside is not None or downside is not None:
        price_field = {"name": "🎯 Targets", "value": ""}
        if upside is not None:
            price_field["value"] += f"Upside: {upside:+.1f}%\n"
        if downside is not None:
            price_field["value"] += f"Downside: {downside:+.1f}%"
        embed["fields"].append(price_field)
    
    # Add summary if available
    summary = signal.get('summary', '')
    if summary and len(summary) > 0:
        # Truncate if too long (Discord embed description max 4096, field value 1024)
        if len(summary) > 500:
            summary = summary[:497] + "..."
        embed["fields"].append({
            "name": "📝 Summary",
            "value": summary,
            "inline": False
        })
    
    # Add sources if available
    sources = signal.get('sources', [])
    if sources:
        sources_text = ", ".join(sources)
        if len(sources_text) > 100:
            sources_text = sources_text[:97] + "..."
        embed["fields"].append({
            "name": "🔗 Sources",
            "value": sources_text,
            "inline": True
        })
    
    return embed


def send_discord_alert(signal: Dict) -> bool:
    """
    Send a Discord webhook alert for a trading signal
    
    Parameters:
    - signal: Signal dictionary (from TradingSignal.to_dict())
    
    Returns:
    - True if successful, False otherwise
    """
    webhook_url = config.DISCORD_WEBHOOK
    
    if not webhook_url:
        logger.warning("Discord webhook URL not configured in config")
        return False
    
    # Respect rate limiting
    _rate_limiter.wait_if_needed()
    
    # Create embed
    embed = create_discord_embed(signal)
    
    # Prepare payload
    payload = {
        "embeds": [embed],
        "username": "Med-Trade-Signals",
        "avatar_url": "https://cdn.discordapp.com/embed/avatars/0.png"
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"Successfully sent Discord alert for {signal.get('ticker', 'UNKNOWN')} ({signal.get('signal_type', 'UNKNOWN')})")
            return True
        else:
            logger.error(f"Failed to send Discord alert: HTTP {response.status_code} - {response.text}")
            return False
    
    except requests.exceptions.Timeout:
        logger.error("Timeout while sending Discord webhook")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Discord webhook: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Discord alert: {e}")
        return False


def send_discord_alerts_bulk(signals: list) -> Dict[str, int]:
    """
    Send multiple Discord alerts with rate limiting
    
    Parameters:
    - signals: List of signal dictionaries
    
    Returns:
    - Dictionary with counts: {"success": X, "failed": Y}
    """
    results = {"success": 0, "failed": 0}
    
    logger.info(f"Sending {len(signals)} Discord alerts")
    
    for i, signal in enumerate(signals):
        success = send_discord_alert(signal)
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1
        
        # Log progress every 10 signals
        if (i + 1) % 10 == 0:
            logger.info(f"Progress: {i + 1}/{len(signals)} alerts sent")
    
    logger.info(f"Finished: {results['success']} successful, {results['failed']} failed")
    return results


def send_discord_message(message: str, title: Optional[str] = None) -> bool:
    """
    Send a simple text message via Discord webhook
    
    Parameters:
    - message: Message content
    - title: Optional title (will be sent as an embed title)
    
    Returns:
    - True if successful, False otherwise
    """
    webhook_url = config.DISCORD_WEBHOOK
    
    if not webhook_url:
        logger.warning("Discord webhook URL not configured in config")
        return False
    
    # Respect rate limiting
    _rate_limiter.wait_if_needed()
    
    # Prepare payload
    if title:
        payload = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": 0x0099ff
            }],
            "username": "Med-Trade-Signals"
        }
    else:
        payload = {
            "content": message,
            "username": "Med-Trade-Signals"
        }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            logger.info("Successfully sent Discord message")
            return True
        else:
            logger.error(f"Failed to send Discord message: HTTP {response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending Discord message: {e}")
        return False


if __name__ == "__main__":
    # Test with a sample signal
    test_signal = {
        "signal_id": "test_123",
        "signal_type": "FDA_APPROVAL",
        "ticker": "PFE",
        "company_name": "Pfizer Inc.",
        "headline": "FDA approves new treatment for rare disease",
        "summary": "FDA granted approval for new drug showing 95% efficacy in clinical trials.",
        "confidence": 90,
        "sentiment": "positive",
        "target_upside": 15.0,
        "target_downside": -5.0,
        "sources": ["fda.gov"],
        "collected_at": "2024-02-06",
        "created_at": datetime.now().isoformat()
    }
    
    print("Testing Discord alert...")
    success = send_discord_alert(test_signal)
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")
