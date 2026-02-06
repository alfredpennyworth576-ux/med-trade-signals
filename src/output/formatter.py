"""
Signal formatting utilities - Convert signals to different formats
"""
from typing import Dict, Any, List
from datetime import datetime
import json
import sys
sys.path.insert(0, str(__file__).replace('output/formatter.py', ''))
from utils.logger import setup_logger

logger = setup_logger("formatter")


def to_markdown(signal: Dict) -> str:
    """
    Convert signal to Markdown format for display
    
    Args:
        signal: Signal dictionary
        
    Returns:
        Markdown formatted string
    """
    # Emoji based on sentiment
    emoji_map = {
        "positive": "🟢",
        "negative": "🔴", 
        "neutral": "⚪"
    }
    emoji = emoji_map.get(signal.get("sentiment", "neutral"), "⚪")
    
    # Emoji based on signal type
    type_emoji_map = {
        "FDA_APPROVAL": "🏥",
        "FDA_REJECTION": "🚫",
        "TRIAL_SUCCESS": "📈",
        "TRIAL_FAILURE": "📉",
        "PRICE_TARGET_UP": "🎯",
        "PRICE_TARGET_DOWN": "🎯",
        "INSIDER_BUYING": "💼",
        "REDDIT_SENTIMENT": "💬"
    }
    type_emoji = type_emoji_map.get(signal.get("signal_type", ""), "📊")
    
    lines = [
        f"### {type_emoji} {signal.get('signal_type', 'SIGNAL')}",
        f"",
        f"**{emoji} {signal.get('ticker', 'N/A')}** - {signal.get('company_name', 'N/A')}",
        f"",
        f"**Headline:** {signal.get('headline', 'N/A')}",
        f"",
        f"**Summary:** {signal.get('summary', 'N/A')}",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Confidence | {signal.get('confidence', 0)}% |",
        f"| Sentiment | {signal.get('sentiment', 'N/A')} |",
        f"| Target Upside | {signal.get('target_upside', 'N/A')}% |",
        f"| Target Downside | {signal.get('target_downside', 'N/A')}% |",
        f"",
        f"**Sources:**",
    ]
    
    # Add sources
    for source in signal.get("sources", []):
        if isinstance(source, dict):
            lines.append(f"- [{source.get('name', 'Source')}]({source.get('url', '#')})")
        else:
            lines.append(f"- {source}")
    
    created = signal.get("created_at", "")
    if created:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            created = dt.strftime("%Y-%m-%d %H:%M UTC")
        except:
            pass
    
    lines.extend([
        f"",
        f"*Generated: {created}*",
        f"*ID: {signal.get('signal_id', 'N/A')}*"
    ])
    
    return "\n".join(lines)


def to_slack(signal: Dict) -> Dict:
    """
    Convert signal to Slack block kit format
    
    Args:
        signal: Signal dictionary
        
    Returns:
        Slack blocks dictionary
    """
    # Color based on sentiment
    color_map = {
        "positive": "#36a64f",
        "negative": "#dc3545",
        "neutral": "#6c757d"
    }
    color = color_map.get(signal.get("sentiment", "neutral"), "#6c757d")
    
    # Emoji based on type
    type_emoji_map = {
        "FDA_APPROVAL": ":hospital:",
        "FDA_REJECTION": ":no_entry:",
        "TRIAL_SUCCESS": ":chart_with_upwards_trend:",
        "TRIAL_FAILURE": ":chart_with_downwards_trend:",
        "PRICE_TARGET_UP": ":dart:",
        "PRICE_TARGET_DOWN": ":dart:",
        "INSIDER_BUYING": ":briefcase:",
        "REDDIT_SENTIMENT": ":speech_balloon:"
    }
    type_emoji = type_emoji_map.get(signal.get("signal_type", ""), ":bar_chart:")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{type_emoji} {signal.get('signal_type', 'SIGNAL')}"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Ticker:*\n{signal.get('ticker', 'N/A')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Company:*\n{signal.get('company_name', 'N/A')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence:*\n{signal.get('confidence', 0)}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Sentiment:*\n{signal.get('sentiment', 'N/A')}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{signal.get('headline', 'N/A')}*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": signal.get('summary', 'N/A')
            }
        }
    ]
    
    # Add targets if available
    if signal.get('target_upside') or signal.get('target_downside'):
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Target Upside:*\n{signal.get('target_upside', 'N/A')}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Target Downside:*\n{signal.get('target_downside', 'N/A')}%"
                }
            ]
        })
    
    # Add sources
    source_text = "*Sources:*\n"
    for source in signal.get("sources", []):
        if isinstance(source, dict):
            source_text += f"• <{source.get('url', '#')}|{source.get('name', 'Source')}>\n"
        else:
            source_text += f"• {source}\n"
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": source_text
        }
    })
    
    return {
        "blocks": blocks,
        "attachments": [
            {
                "color": color,
                "footer": f"ID: {signal.get('signal_id', 'N/A')}"
            }
        ]
    }


def to_json(signal: Dict, pretty: bool = True) -> str:
    """
    Convert signal to JSON string
    
    Args:
        signal: Signal dictionary
        pretty: Pretty print the JSON
        
    Returns:
        JSON string
    """
    indent = 2 if pretty else None
    return json.dumps(signal, indent=indent)


def to_csv(signals: List[Dict]) -> str:
    """
    Convert list of signals to CSV format
    
    Args:
        signals: List of signal dictionaries
        
    Returns:
        CSV string
    """
    if not signals:
        return ""
    
    # Get all unique keys
    all_keys = set()
    for signal in signals:
        all_keys.update(signal.keys())
    
    # Header
    headers = sorted(all_keys)
    lines = [",".join(headers)]
    
    # Rows
    for signal in signals:
        row = []
        for key in headers:
            value = signal.get(key, "")
            # Handle nested objects
            if isinstance(value, (dict, list)):
                value = str(value)
            # Escape commas and quotes
            value = str(value).replace('"', '""')
            if ',' in value or '"' in value:
                value = f'"{value}"'
            row.append(value)
        lines.append(",".join(row))
    
    return "\n".join(lines)


def to_discord_embed(signal: Dict) -> Dict:
    """
    Convert signal to Discord embed format
    
    Args:
        signal: Signal dictionary
        
    Returns:
        Discord embed dictionary
    """
    # Color based on sentiment
    color_map = {
        "positive": 0x00FF00,
        "negative": 0xFF0000,
        "neutral": 0x808080
    }
    color = color_map.get(signal.get("sentiment", "neutral"), 0x808080)
    
    # Title based on type
    type_title_map = {
        "FDA_APPROVAL": "🏥 FDA Approval",
        "FDA_REJECTION": "🚫 FDA Rejection",
        "TRIAL_SUCCESS": "📈 Trial Success",
        "TRIAL_FAILURE": "📉 Trial Failure",
        "PRICE_TARGET_UP": "🎯 Price Target Upgrade",
        "PRICE_TARGET_DOWN": "🎯 Price Target Downgrade",
        "INSIDER_BUYING": "💼 Insider Buying",
        "REDDIT_SENTIMENT": "💬 Reddit Sentiment"
    }
    title = type_title_map.get(signal.get("signal_type", "Signal"), "📊 Signal")
    
    embed = {
        "title": title,
        "description": signal.get("headline", "")[:256],
        "color": color,
        "fields": [
            {
                "name": "Ticker",
                "value": signal.get("ticker", "N/A"),
                "inline": True
            },
            {
                "name": "Company",
                "value": signal.get("company_name", "N/A")[:50],
                "inline": True
            },
            {
                "name": "Confidence",
                "value": f"{signal.get('confidence', 0)}%",
                "inline": True
            },
            {
                "name": "Sentiment",
                "value": signal.get("sentiment", "N/A").capitalize(),
                "inline": True
            }
        ],
        "footer": {
            "text": f"ID: {signal.get('signal_id', 'N/A')}"
        },
        "timestamp": signal.get("created_at", "")
    }
    
    # Add summary if available
    if signal.get("summary"):
        embed["fields"].append({
            "name": "Summary",
            "value": signal.get("summary", "")[:500]
        })
    
    # Add targets if available
    if signal.get("target_upside") or signal.get("target_downside"):
        embed["fields"].append({
            "name": "Price Targets",
            "value": f"↑ {signal.get('target_upside', 'N/A')}%\n↓ {signal.get('target_downside', 'N/A')}%",
            "inline": False
        })
    
    # Add source URL
    sources = signal.get("sources", [])
    if sources:
        if isinstance(sources[0], dict) and sources[0].get("url"):
            embed["url"] = sources[0].get("url")
    
    return embed


def format_signal(signal: Dict, format_type: str = "markdown") -> Any:
    """
    Format a signal in the specified format
    
    Args:
        signal: Signal dictionary
        format_type: One of "markdown", "slack", "json", "csv", "discord"
        
    Returns:
        Formatted signal in the specified format
    """
    formatters = {
        "markdown": to_markdown,
        "slack": to_slack,
        "json": to_json,
        "csv": lambda s: to_csv([s]),
        "discord": to_discord_embed
    }
    
    formatter = formatters.get(format_type)
    if not formatter:
        logger.error(f"Unknown format type: {format_type}")
        return None
    
    return formatter(signal)


def format_signals(signals: List[Dict], format_type: str = "json") -> Any:
    """
    Format multiple signals in the specified format
    
    Args:
        signals: List of signal dictionaries
        format_type: One of "json", "csv", "markdown"
        
    Returns:
        Formatted signals
    """
    if format_type == "json":
        return json.dumps(signals, indent=2)
    elif format_type == "csv":
        return to_csv(signals)
    elif format_type == "markdown":
        return "\n\n---\n\n".join([to_markdown(s) for s in signals])
    else:
        return signals


if __name__ == "__main__":
    # Test formatting
    test_signal = {
        "signal_id": "test_001",
        "signal_type": "FDA_APPROVAL",
        "ticker": "ABC",
        "company_name": "ABC Pharmaceuticals",
        "headline": "FDA approves ABC drug",
        "summary": "Clinical trials showed positive results",
        "confidence": 87,
        "sentiment": "positive",
        "target_upside": 15.2,
        "target_downside": -5.1,
        "sources": [{"name": "fda.gov", "url": "https://fda.gov"}],
        "created_at": "2024-01-15T10:30:00Z"
    }
    
    print("=== Markdown ===")
    print(to_markdown(test_signal))
    
    print("\n=== Slack ===")
    import json
    print(json.dumps(to_slack(test_signal), indent=2)[:500])
    
    print("\n=== Discord ===")
    print(json.dumps(to_discord_embed(test_signal), indent=2)[:500])
