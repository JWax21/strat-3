# Prediction Market Arbitrage Platform

A real-time trading platform that identifies price discrepancies between **Polymarket** and **Kalshi** prediction markets.

![Arbitrage Scanner](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.11+-blue) ![Next.js](https://img.shields.io/badge/next.js-14-black)

## Overview

This platform:
1. **Fetches markets** from both Polymarket and Kalshi APIs
2. **Matches similar markets** using fuzzy string matching and keyword analysis
3. **Detects arbitrage opportunities** by comparing YES/NO prices across platforms
4. **Displays opportunities** in a beautiful, real-time dashboard

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│              Real-time Arbitrage Dashboard                   │
└─────────────────────┬───────────────────────────────────────┘
                      │ API Calls
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Polymarket  │  │    Kalshi    │  │    Arbitrage     │   │
│  │    Client    │  │    Client    │  │    Detector      │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                 │                    │             │
│  ┌──────▼─────────────────▼────────────────────▼──────────┐ │
│  │              Rate Limiter + Market Matcher              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                      │                 │
                      ▼                 ▼
        ┌─────────────────┐   ┌─────────────────┐
        │   Polymarket    │   │     Kalshi      │
        │   Gamma API     │   │   Trading API   │
        │   CLOB API      │   │                 │
        └─────────────────┘   └─────────────────┘
```

## Features

### Backend
- **Polymarket Integration**: Fetches from Gamma API (discovery) and CLOB API (pricing)
- **Kalshi Integration**: Navigates Series → Events → Markets hierarchy
- **Rate Limiting**: Sliding window rate limiter respects API constraints
- **Market Matching**: Fuzzy string matching with keyword boosting
- **Arbitrage Detection**: Calculates profit potential accounting for fees

### Frontend
- **Real-time Updates**: Auto-refreshes every 30 seconds
- **Beautiful UI**: Dark theme with electric accents and smooth animations
- **Filters**: Search markets and set minimum price difference thresholds
- **Detailed View**: Expandable cards with trading strategies

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm or yarn

### 1. Clone and Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Create .env file in backend/
cat > backend/.env << EOF
POLYMARKET_GAMMA_API_URL=https://gamma-api.polymarket.com
POLYMARKET_CLOB_API_URL=https://clob.polymarket.com
KALSHI_API_URL=https://api.elections.kalshi.com/trade-api/v2
POLYMARKET_RATE_LIMIT=60
KALSHI_RATE_LIMIT=30
MIN_PRICE_DIFFERENCE_PERCENT=2.0
MATCH_THRESHOLD=0.75
EOF
```

### 3. Start Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 4. Setup and Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Open Dashboard

Navigate to [http://localhost:3000](http://localhost:3000)

## API Endpoints

### Health & Status
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with rate limiter status |
| `/api/status` | GET | Detailed platform status |

### Markets
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/markets/polymarket` | GET | Fetch Polymarket markets |
| `/api/markets/kalshi` | GET | Fetch Kalshi markets |
| `/api/markets/search?q=query` | GET | Search across platforms |

### Arbitrage
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/arbitrage` | GET | Get identified opportunities |
| `/api/arbitrage/refresh` | POST | Trigger data refresh |
| `/api/arbitrage/top?n=10` | GET | Get top opportunities |

## Rate Limits

The platform respects API rate limits:

| Platform | Default Limit | Notes |
|----------|--------------|-------|
| Polymarket | 60 req/min | Gamma + CLOB APIs |
| Kalshi | 30 req/min | Conservative to avoid blocks |

The rate limiter uses a sliding window algorithm to ensure compliance.

## How Arbitrage Detection Works

### Price Comparison
In a binary market:
- **YES** + **NO** should equal approximately **$1.00** (100%)
- If Polymarket YES (40¢) + Kalshi NO (50¢) = 90¢, there's potential 10% arbitrage

### Profit Calculation
```
Gross Profit = 1.0 - (Price_A_YES + Price_B_NO)
Net Profit = Gross Profit - Fees (Polymarket ~2% + Kalshi ~1%)
Profit BPS = Net Profit × 10,000
```

### Match Quality
Markets are matched using:
- **Fuzzy string matching** (token sort, token set, partial ratio)
- **Keyword overlap** analysis
- **High-value keyword** boosting (elections, crypto, sports, etc.)

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `POLYMARKET_RATE_LIMIT` | 60 | Requests per minute |
| `KALSHI_RATE_LIMIT` | 30 | Requests per minute |
| `MIN_PRICE_DIFFERENCE_PERCENT` | 2.0 | Minimum difference to flag |
| `MATCH_THRESHOLD` | 0.75 | Similarity score threshold |

## Important Notes

⚠️ **This is for educational and research purposes only.**

- Always verify opportunities manually before trading
- Account for slippage, fees, and liquidity
- Markets may resolve differently on each platform
- Price differences may close quickly

## API Documentation

- [Polymarket Docs](https://docs.polymarket.com/quickstart/overview)
- [Kalshi Docs](https://docs.kalshi.com/)

## License

MIT License - See LICENSE file for details.

