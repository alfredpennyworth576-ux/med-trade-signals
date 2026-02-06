# Medical News → Trading Signal Pipeline

## Mission
Build an autonomous system that monitors medical news, extracts trading signals, and generates actionable trade recommendations.

## Architecture

```
med-trade-signals/
├── src/
│   ├── collectors/          # Data collection
│   │   ├── pubmed.py       # PubMed abstracts
│   │   ├── fda.py          # FDA approvals/rejections
│   │   ├── reddit.py       # r/medicine, r/financial
│   │   └── sec.py          # 10-K, 10-Q filings
│   ├── nlp/                # Natural Language Processing
│   │   ├── entities.py     # Drug/company extraction
│   │   ├── sentiment.py    # Clinical sentiment
│   │   └── mapper.py       # Company → Ticker mapping
│   ├── signals/             # Signal Generation
│   │   ├── generator.py    # Create trading signals
│   │   ├── confidence.py   # Confidence scoring
│   │   └── validator.py    # Signal validation
│   ├── output/              # Output & Delivery
│   │   ├── api.py          # REST API
│   │   ├── alerts.py        # Discord/Slack/Telegram
│   │   └── paper.py        # Paper trading executor
│   └── utils/
│       ├── config.py        # Configuration
│       └── logger.py        # Logging
├── data/
│   ├── raw/                # Raw data
│   ├── processed/           # Processed data
│   └── signals/            # Generated signals
├── tests/                   # Tests
├── scripts/                 # Automation scripts
├── requirements.txt         # Dependencies
├── README.md                # Documentation
└── .env.example            # Environment variables
```

## Data Sources

### Priority 1 (High Value)
- **PubMed** - Clinical trial outcomes, efficacy data
- **FDA** - Approvals, rejections, clearances
- **SEC EDGAR** - Financial disclosures, insider trading

### Priority 2 (Medium Value)  
- **Reddit** - r/medicine, r/financialindependence
- **Conference Abstracts** - RSNA, AHA, ASCO, RSNA

## Signal Types

### Signal Categories
1. **FDA Approval** - BUY (upside potential)
2. **FDA Rejection** - SELL/AVOID
3. **Trial Success** - BUY (target population)
4. **Trial Failure** - SELL (avoid)
5. **Insider Buying** - Signal boost
6. **Price Target Upgrade** - Positive sentiment

### Confidence Scoring
- **High (80-100%)**: Multiple sources, clear outcome, large market impact
- **Medium (50-79%)**: Single source, some uncertainty
- **Low (<50%)**: Rumor, small impact, conflicting data

## Ticker Mapping
- Manual mapping for major pharma
- Wikidata SPARQL query for entity resolution
- Regex pattern matching for company names

## Output Format
```json
{
  "signal_id": "fd_2024_01_15_abc123",
  "type": "FDA_APPROVAL",
  "ticker": "ABC",
  "company": "ABC Pharmaceuticals",
  "confidence": 87,
  "headline": "FDA approves ABC's drug for indication",
  "summary": "Clinical trial showed 45% improvement...",
  "targets": {
    "upside_pct": 15.2,
    "downside_pct": -5.1
  },
  "sources": ["fda.gov", "pubmed.ncbi.nlm.nih.gov"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Cron Schedule
- Every 6 hours: Full pipeline run
- Every 1 hour: FDA/Reddit quick scan
- Daily at 8 AM: Signal digest report

## Success Metrics
- Signals generated per day
- Average confidence score
- Market reaction vs prediction
- False positive rate
