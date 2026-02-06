# Med-Trade-Signals

**Autonomous Medical News → Trading Signal Pipeline**

Monitor medical news, clinical trials, FDA decisions, and generate actionable trading signals.

## 🎯 What It Does

1. **Collects** data from PubMed, FDA, Reddit, and SEC
2. **Extracts** entities (drugs, companies, trial phases)
3. **Analyzes** sentiment and clinical outcomes
4. **Generates** trading signals with confidence scores
5. **Outputs** JSON signals ready for execution

## 📊 Signal Types

| Signal | Meaning | Typical Move |
|--------|---------|--------------|
| `FDA_APPROVAL` | FDA approved a drug | +15% |
| `FDA_REJECTION` | FDA rejected a drug | -25% |
| `TRIAL_SUCCESS` | Positive trial results | +12% |
| `TRIAL_FAILURE` | Negative trial results | -15% |
| `REDDIT_SENTIMENT` | Strong retail sentiment | ±5% |

## 🚀 Quick Start

```bash
# Clone and install
git clone <repo>
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
│   │   └── reddit.py       # Reddit discussions
│   ├── nlp/                # Natural Language Processing
│   │   └── utils.py        # Entity extraction, sentiment
│   ├── signals/             # Signal Generation
│   │   └── generator.py    # Create trading signals
│   └── utils/
│       ├── config.py        # Configuration
│       └── logger.py        # Logging
├── data/
│   ├── raw/                # Raw collected data
│   ├── processed/           # Processed data
│   └── signals/             # Generated signals
├── pipeline.py              # Main pipeline script
├── requirements.txt         # Dependencies
└── README.md               # This file
```

## ⚙️ Configuration

Set these environment variables:

```bash
export OPENAI_API_KEY=your_key_here
export PUBMED_EMAIL=your@email.com
export REDDIT_CLIENT_ID=your_reddit_client
export REDDIT_CLIENT_SECRET=your_reddit_secret
export DISCORD_WEBHOOK=your_webhook_url
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
  "sources": ["fda.gov", "pubmed.ncbi.nlm.nih.gov"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

## 🔄 Automation

Add to cron for regular runs:

```bash
# Every 6 hours
0 */6 * * * cd /path/to/med-trade-signals && python pipeline.py --quiet
```

## 🎓 How It Works

### 1. Data Collection
- **PubMed**: Searches for medical papers matching keywords
- **FDA**: Fetches recent drug approvals and rejections
- **Reddit**: Monitors r/medicine, r/wallstreetbets, etc.

### 2. Entity Extraction
- Identifies drug names, companies, trial phases
- Maps companies to ticker symbols
- Extracts efficacy numbers and statistics

### 3. Sentiment Analysis
- Clinical sentiment (success/failure of trials)
- Financial sentiment (analyst upgrades/downgrades)
- Confidence scoring based on source quality

### 4. Signal Generation
- Combines all signals into actionable trades
- Calculates confidence and price targets
- Deduplicates overlapping signals

## 📊 Success Metrics

- Signals generated per day
- Average confidence score
- Market reaction vs prediction
- False positive rate

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Add tests
4. Submit a PR

## ⚠️ Disclaimer

This is for educational purposes only. Not financial advice. Always do your own research before trading.

## 📝 License

MIT License
