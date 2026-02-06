# Med-Trade-Signals

**Autonomous Medical News → Trading Signal Pipeline**

Monitor medical news, clinical trials, FDA decisions, and generate actionable trading signals.

## 🎯 What It Does

1. **Collects** data from PubMed, FDA, SEC, Reddit, and Twitter
2. **Extracts** entities (drugs, companies, trial phases, tickers)
3. **Analyzes** sentiment and clinical outcomes using NLP + LLM
4. **Generates** trading signals with confidence scores
5. **Validates** signals against market data
6. **Alerts** via Discord, Slack, or REST API
7. **Simulates** paper trading to track performance

## 📊 Signal Types

| Signal | Meaning | Typical Move | Confidence |
|--------|---------|--------------|------------|
| `FDA_APPROVAL` | FDA approved a drug | +15% | 85-95% |
| `FDA_REJECTION` | FDA rejected a drug | -25% | 90% |
| `FDA_WARNING` | FDA safety warning | -10% | 70-80% |
| `TRIAL_SUCCESS` | Positive trial results | +12% | 75-85% |
| `TRIAL_FAILURE` | Negative trial results | -15% | 80-90% |
| `SEC_FILING` | 10-K/8-K material event | ±5% | 40-60% |
| `REDDIT_SENTIMENT` | Strong retail sentiment | ±5% | 40-70% |

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/alfredpennyworth576-ux/med-trade-signals.git
cd med-trade-signals
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the pipeline
python pipeline.py

# Or run from a specific source only
python pipeline.py --source fda
python pipeline.py --source pubmed --quiet
```

## 📁 Project Structure

```
med-trade-signals/
├── src/
│   ├── collectors/          # Data collection
│   │   ├── pubmed.py       # PubMed research papers
│   │   ├── fda.py          # FDA approvals/rejections
│   │   ├── reddit.py       # Reddit discussions
│   │   ├── sec.py          # SEC filings (10-K, 8-K)
│   │   └── twitter.py      # Twitter/X medical tweets
│   ├── nlp/                # Natural Language Processing
│   │   ├── utils.py        # Regex-based entity extraction
│   │   ├── llm.py          # OpenAI GPT integration
│   │   └── entity_db.py    # Wikidata entity resolution
│   ├── signals/            # Signal Generation
│   │   ├── generator.py    # Create trading signals
│   │   ├── confidence.py   # Confidence scoring
│   │   └── validator.py    # Signal validation
│   ├── output/             # Output & Alerts
│   │   ├── api.py          # FastAPI REST endpoints
│   │   ├── discord.py      # Discord webhook alerts
│   │   ├── formatter.py    # Signal formatting
│   │   └── paper_trading.py # Paper trading simulation
│   ├── utils/
│   │   ├── config.py       # Configuration
│   │   └── logger.py       # Logging
│   └── models.py           # Data models
├── tests/                  # Unit & integration tests
├── data/
│   ├── raw/                # Raw collected data
│   ├── processed/           # Processed data
│   └── signals/             # Generated signals
├── pipeline.py              # Main pipeline script
├── Makefile                # Common commands
├── requirements.txt        # Dependencies
└── README.md               # This file
```

## ⚙️ Configuration

Set these environment variables in `.env`:

```bash
# OpenAI API Key (for LLM-enhanced NLP)
OPENAI_API_KEY=your_key_here

# PubMed API (for research paper collection)
PUBMED_EMAIL=your@email.com

# Reddit API (for subreddit monitoring)
REDDIT_CLIENT_ID=your_reddit_client
REDDIT_CLIENT_SECRET=your_reddit_secret

# Twitter/X API (for medical tweets)
TWITTER_BEARER_TOKEN=your_twitter_token

# Discord Webhook (for signal alerts)
DISCORD_WEBHOOK_URL=your_webhook_url

# Slack Webhook (optional)
SLACK_WEBHOOK_URL=your_slack_webhook
```

## 📈 Example Signal

```json
{
  "signal_id": "fda_2024_01_15_abc123",
  "signal_type": "FDA_APPROVAL",
  "ticker": "ABC",
  "company": "ABC Pharmaceuticals",
  "confidence": 87,
  "sentiment": "positive",
  "target_upside": 15.2,
  "target_downside": -5.1,
  "sources": [
    {"name": "fda.gov", "url": "https://fda.gov", "reliability": 1.0}
  ],
  "created_at": "2024-01-15T10:30:00Z"
}
```

## 🔌 REST API

Start the API server:

```bash
uvicorn src.output.api:app --host 0.0.0.0 --port 8000
```

Endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `GET /signals` | List all signals (with filters) |
| `GET /signals/{id}` | Get specific signal |
| `GET /signals/latest` | Get recent signals |
| `GET /signals/tickers` | List tickers with counts |
| `GET /signals/stats` | Overall statistics |

## 🔔 Discord Alerts

Configure webhook and receive signals in Discord:

```python
from src.output.discord import send_discord_alert

signal = {...}  # Signal dictionary
success = send_discord_alert(signal)
```

## 📊 Paper Trading

Simulate trading signals:

```python
from src.output.paper_trading import PaperTrader

trader = PaperTrader(initial_cash=100000)
trader.execute_signal(signal)
print(trader.get_portfolio())
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v --cov=src

# Run specific test file
pytest tests/test_collectors.py -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html
```

## 🔄 Automation

Add to cron for regular runs:

```bash
# Every 6 hours
0 */6 * * * cd /path/to/med-trade-signals && python pipeline.py --quiet

# Every hour (quick scan)
0 * * * * cd /path/to/med-trade-signals && python pipeline.py --source fda --quiet
```

## 🎓 How It Works

### 1. Data Collection
- **PubMed**: Searches for medical papers matching keywords
- **FDA**: Fetches drug approvals, rejections, labels
- **SEC**: Collects 10-K, 10-Q, 8-K filings
- **Reddit**: Monitors r/medicine, r/wallstreetbets
- **Twitter**: Tracks healthcare stock mentions

### 2. Entity Extraction
- Uses regex patterns for clinical trials, FDA decisions
- Maps companies to ticker symbols (Wikidata SPARQL)
- Extracts efficacy numbers and statistics

### 3. LLM Analysis (Optional)
- Uses GPT-4o for advanced NLP
- Fallback to regex if API unavailable
- Sentiment classification + entity resolution

### 4. Signal Generation
- Combines all signals into actionable trades
- Calculates confidence from multiple factors:
  - Source reliability (FDA = 1.0, Reddit = 0.4)
  - Recency (decay over 24h half-life)
  - Confirmation (multiple sources)
  - Historical accuracy

### 5. Validation
- Verifies ticker exists
- Checks for market holidays
- Cross-references similar signals

## 📊 Success Metrics

- Signals generated per day
- Average confidence score
- Market reaction vs prediction
- False positive rate
- Paper trading P&L

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Add tests
4. Submit a PR

## ⚠️ Disclaimer

This is for educational purposes only. Not financial advice. Always do your own research before trading.

## 📝 License

MIT License
