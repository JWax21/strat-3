# Prediction Market Arbitrage Platform - Backend

A FastAPI backend that fetches markets from Polymarket and Kalshi, matches similar markets, and identifies arbitrage opportunities.

## Features

- **Polymarket Integration**: Fetches markets from Gamma API with rate limiting
- **Kalshi Integration**: Navigates Series → Events → Markets hierarchy
- **Market Matching**: Uses fuzzy string matching to find similar markets
- **Arbitrage Detection**: Identifies price discrepancies and calculates profit potential
- **Rate Limiting**: Respects API rate limits to avoid being blocked

## Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Key settings:
- `POLYMARKET_RATE_LIMIT`: Requests per minute for Polymarket (default: 60)
- `KALSHI_RATE_LIMIT`: Requests per minute for Kalshi (default: 30)
- `MIN_PRICE_DIFFERENCE_PERCENT`: Minimum difference to flag as opportunity (default: 2.0)
- `MATCH_THRESHOLD`: Similarity score threshold for market matching (default: 0.75)

## Running

```bash
uvicorn main:app --reload --port 8000
```

## API Endpoints

### Health & Status
- `GET /health` - Health check with rate limiter status
- `GET /api/status` - Detailed platform status

### Markets
- `GET /api/markets/polymarket` - Fetch Polymarket markets
- `GET /api/markets/kalshi` - Fetch Kalshi markets
- `GET /api/markets/search?q=query` - Search markets across platforms

### Arbitrage
- `GET /api/arbitrage` - Get identified opportunities
- `POST /api/arbitrage/refresh` - Trigger data refresh
- `GET /api/arbitrage/top?n=10` - Get top opportunities

### Kalshi Structure
- `GET /api/kalshi/series` - Get Kalshi series
- `GET /api/kalshi/events` - Get Kalshi events

## Rate Limits

The platform respects API rate limits:
- **Polymarket**: 60 requests/minute (configurable)
- **Kalshi**: 30 requests/minute (configurable)

The rate limiter uses a sliding window algorithm to ensure compliance.

## Architecture

```
backend/
├── main.py              # FastAPI application
├── config.py            # Settings management
├── clients/
│   ├── polymarket.py    # Polymarket API client
│   └── kalshi.py        # Kalshi API client
├── services/
│   ├── market_matcher.py    # Market matching logic
│   └── arbitrage_detector.py # Arbitrage detection
└── utils/
    └── rate_limiter.py  # Rate limiting utilities
```

