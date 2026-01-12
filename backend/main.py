"""
Arbitrage Trading Platform - FastAPI Backend

Main entry point for the API server that fetches markets from
Polymarket and Kalshi, matches them, and identifies arbitrage opportunities.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_settings
from clients import PolymarketClient, KalshiClient
from services import MarketMatcher, ArbitrageDetector, ArbitrageOpportunity, SportsMarketMatcher
from services.normalizer import get_normalizer, get_slug_builder, Sport
from utils.rate_limiter import RateLimiterManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global state for caching
class AppState:
    polymarket_client: Optional[PolymarketClient] = None
    kalshi_client: Optional[KalshiClient] = None
    market_matcher: Optional[MarketMatcher] = None
    sports_matcher: Optional[SportsMarketMatcher] = None
    arbitrage_detector: Optional[ArbitrageDetector] = None
    
    # Cached data
    last_fetch: Optional[datetime] = None
    cached_opportunities: List[ArbitrageOpportunity] = []
    cached_sports_opportunities: List[Dict] = []  # Sports-specific matches
    cached_polymarket_markets: List[Dict] = []
    cached_kalshi_markets: List[Dict] = []
    is_fetching: bool = False


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    # Startup
    logger.info("Initializing application...")
    settings = get_settings()
    
    state.polymarket_client = PolymarketClient()
    state.kalshi_client = KalshiClient()
    state.market_matcher = MarketMatcher(match_threshold=settings.match_threshold)
    state.sports_matcher = SportsMarketMatcher(match_threshold=settings.match_threshold)
    state.arbitrage_detector = ArbitrageDetector(
        min_difference_percent=settings.min_price_difference_percent
    )
    
    logger.info("Application initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if state.polymarket_client:
        await state.polymarket_client.close()
    if state.kalshi_client:
        await state.kalshi_client.close()


app = FastAPI(
    title="Prediction Market Arbitrage Platform",
    description="Identify price discrepancies between Polymarket and Kalshi",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API responses
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    rate_limiters: Dict[str, int]


class MarketResponse(BaseModel):
    platform: str
    count: int
    markets: List[Dict[str, Any]]


class ArbitrageResponse(BaseModel):
    opportunities: List[Dict[str, Any]]
    summary: Dict[str, Any]
    last_updated: Optional[str]
    is_stale: bool


class RefreshResponse(BaseModel):
    status: str
    message: str
    fetched_at: Optional[str]


# Health endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and rate limiter status."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        rate_limiters=RateLimiterManager.get_status()
    )


@app.get("/api/status")
async def get_status():
    """Get detailed status of the platform."""
    settings = get_settings()
    
    return {
        "status": "operational",
        "cache": {
            "last_fetch": state.last_fetch.isoformat() if state.last_fetch else None,
            "polymarket_markets": len(state.cached_polymarket_markets),
            "kalshi_markets": len(state.cached_kalshi_markets),
            "opportunities": len(state.cached_opportunities),
            "is_fetching": state.is_fetching
        },
        "config": {
            "match_threshold": settings.match_threshold,
            "min_price_difference": settings.min_price_difference_percent,
            "polymarket_rate_limit": settings.polymarket_rate_limit,
            "kalshi_rate_limit": settings.kalshi_rate_limit
        },
        "rate_limiters": RateLimiterManager.get_status()
    }


# Market endpoints
@app.get("/api/markets/polymarket", response_model=MarketResponse)
async def get_polymarket_markets(
    limit: int = Query(100, ge=1, le=500),
    refresh: bool = Query(False)
):
    """
    Fetch markets from Polymarket.
    
    Args:
        limit: Maximum number of markets to return
        refresh: Force refresh from API (ignores cache)
    """
    if not refresh and state.cached_polymarket_markets:
        markets = state.cached_polymarket_markets[:limit]
        return MarketResponse(
            platform="polymarket",
            count=len(markets),
            markets=markets
        )
    
    try:
        markets = await state.polymarket_client.get_all_active_markets(max_markets=limit)
        market_dicts = [m.to_dict() for m in markets]
        state.cached_polymarket_markets = market_dicts
        
        return MarketResponse(
            platform="polymarket",
            count=len(market_dicts),
            markets=market_dicts
        )
    except Exception as e:
        logger.error(f"Error fetching Polymarket markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/markets/kalshi", response_model=MarketResponse)
async def get_kalshi_markets(
    limit: int = Query(100, ge=1, le=500),
    refresh: bool = Query(False)
):
    """
    Fetch markets from Kalshi.
    
    Args:
        limit: Maximum number of markets to return
        refresh: Force refresh from API (ignores cache)
    """
    if not refresh and state.cached_kalshi_markets:
        markets = state.cached_kalshi_markets[:limit]
        return MarketResponse(
            platform="kalshi",
            count=len(markets),
            markets=markets
        )
    
    try:
        # First check exchange status
        status = await state.kalshi_client.get_exchange_status()
        if not status.get("exchange_active"):
            raise HTTPException(
                status_code=503,
                detail="Kalshi exchange is currently inactive"
            )
        
        markets = await state.kalshi_client.get_all_open_markets(max_markets=limit)
        market_dicts = [m.to_dict() for m in markets]
        state.cached_kalshi_markets = market_dicts
        
        return MarketResponse(
            platform="kalshi",
            count=len(market_dicts),
            markets=market_dicts
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Kalshi markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/markets/search")
async def search_markets(
    q: str = Query(..., min_length=2),
    platform: Optional[str] = Query(None, pattern="^(polymarket|kalshi)$")
):
    """
    Search for markets by query string.
    
    Args:
        q: Search query
        platform: Optional platform filter
    """
    results = {"polymarket": [], "kalshi": []}
    
    try:
        if platform in (None, "polymarket"):
            poly_results = await state.polymarket_client.search_markets(q)
            results["polymarket"] = [m.to_dict() for m in poly_results]
        
        if platform in (None, "kalshi"):
            kalshi_results = await state.kalshi_client.search_markets(q)
            results["kalshi"] = [m.to_dict() for m in kalshi_results]
        
        return {
            "query": q,
            "results": results,
            "total": len(results["polymarket"]) + len(results["kalshi"])
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Arbitrage endpoints
@app.get("/api/arbitrage", response_model=ArbitrageResponse)
async def get_arbitrage_opportunities(
    min_difference: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get identified arbitrage opportunities.
    
    Args:
        min_difference: Minimum price difference percentage to include
        limit: Maximum number of opportunities to return
    """
    # Check if we have cached data
    if not state.cached_opportunities:
        return ArbitrageResponse(
            opportunities=[],
            summary={
                "total_opportunities": 0,
                "profitable_count": 0,
                "message": "No data available. Call /api/arbitrage/refresh to fetch markets."
            },
            last_updated=None,
            is_stale=True
        )
    
    opportunities = state.cached_opportunities
    
    # Filter by min_difference if provided
    if min_difference is not None:
        opportunities = [
            o for o in opportunities
            if o.price_difference_percent >= min_difference
        ]
    
    # Limit results
    opportunities = opportunities[:limit]
    
    # Get summary stats
    summary = state.arbitrage_detector.get_summary_stats(opportunities)
    
    # Check if data is stale (older than 5 minutes)
    is_stale = False
    if state.last_fetch:
        age = (datetime.utcnow() - state.last_fetch).total_seconds()
        is_stale = age > 300  # 5 minutes
    
    return ArbitrageResponse(
        opportunities=[o.to_dict() for o in opportunities],
        summary=summary,
        last_updated=state.last_fetch.isoformat() if state.last_fetch else None,
        is_stale=is_stale
    )


@app.post("/api/arbitrage/refresh", response_model=RefreshResponse)
async def refresh_arbitrage_data(background_tasks: BackgroundTasks):
    """
    Trigger a refresh of market data and arbitrage analysis.
    
    This endpoint is rate-limited and respects API constraints.
    The actual fetch happens in the background.
    """
    if state.is_fetching:
        return RefreshResponse(
            status="in_progress",
            message="A refresh is already in progress",
            fetched_at=state.last_fetch.isoformat() if state.last_fetch else None
        )
    
    background_tasks.add_task(fetch_and_analyze)
    
    return RefreshResponse(
        status="started",
        message="Refresh started in background",
        fetched_at=state.last_fetch.isoformat() if state.last_fetch else None
    )


async def fetch_and_analyze():
    """Background task to fetch markets and analyze arbitrage opportunities."""
    if state.is_fetching:
        return
    
    state.is_fetching = True
    logger.info("Starting market fetch and analysis...")
    
    try:
        # Fetch from both platforms concurrently
        poly_task = state.polymarket_client.get_all_active_markets(max_markets=300)
        kalshi_task = state.kalshi_client.get_all_open_markets(max_markets=300)
        
        poly_markets, kalshi_markets = await asyncio.gather(
            poly_task, kalshi_task, return_exceptions=True
        )
        
        # Handle any errors
        if isinstance(poly_markets, Exception):
            logger.error(f"Polymarket fetch failed: {poly_markets}")
            poly_markets = []
        if isinstance(kalshi_markets, Exception):
            logger.error(f"Kalshi fetch failed: {kalshi_markets}")
            kalshi_markets = []
        
        logger.info(
            f"Fetched {len(poly_markets)} Polymarket and "
            f"{len(kalshi_markets)} Kalshi markets"
        )
        
        # Update cached raw markets
        state.cached_polymarket_markets = [m.to_dict() for m in poly_markets]
        state.cached_kalshi_markets = [m.to_dict() for m in kalshi_markets]
        
        # Match markets
        matched = state.market_matcher.match_markets(poly_markets, kalshi_markets)
        logger.info(f"Found {len(matched)} matched markets")
        
        # Detect arbitrage opportunities
        opportunities = state.arbitrage_detector.detect_opportunities(matched)
        logger.info(f"Found {len(opportunities)} arbitrage opportunities")
        
        # Update cache
        state.cached_opportunities = opportunities
        state.last_fetch = datetime.utcnow()
        
    except Exception as e:
        logger.error(f"Error in fetch_and_analyze: {e}", exc_info=True)
    finally:
        state.is_fetching = False


@app.get("/api/arbitrage/top")
async def get_top_opportunities(n: int = Query(10, ge=1, le=50)):
    """
    Get the top N arbitrage opportunities by profit potential.
    
    Args:
        n: Number of top opportunities to return
    """
    if not state.cached_opportunities:
        raise HTTPException(
            status_code=404,
            detail="No opportunities available. Refresh data first."
        )
    
    top = state.cached_opportunities[:n]
    
    return {
        "count": len(top),
        "opportunities": [o.to_dict() for o in top],
        "last_updated": state.last_fetch.isoformat() if state.last_fetch else None
    }


# Kalshi-specific endpoints (due to hierarchical structure)
@app.get("/api/kalshi/series")
async def get_kalshi_series(limit: int = Query(50, ge=1, le=100)):
    """Get Kalshi series (top-level categories)."""
    try:
        series = await state.kalshi_client.get_series_list(limit=limit)
        return {
            "count": len(series),
            "series": [s.to_dict() for s in series]
        }
    except Exception as e:
        logger.error(f"Error fetching Kalshi series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kalshi/events")
async def get_kalshi_events(
    series_ticker: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100)
):
    """Get Kalshi events, optionally filtered by series."""
    try:
        events = await state.kalshi_client.get_events(
            series_ticker=series_ticker,
            limit=limit
        )
        return {
            "count": len(events),
            "events": [e.to_dict() for e in events]
        }
    except Exception as e:
        logger.error(f"Error fetching Kalshi events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Sports-specific endpoints
@app.get("/api/sports/arbitrage")
async def get_sports_arbitrage(
    min_difference: float = Query(1.0, ge=0, le=100),
    league: Optional[str] = Query(None, pattern="^(nfl|nba|mlb|nhl)$"),
    expiring_within_hours: Optional[int] = Query(None, ge=1, le=720, description="Filter to markets expiring within N hours")
):
    """
    Get sports arbitrage opportunities.
    
    Args:
        min_difference: Minimum price difference percentage
        league: Filter by league (nfl, nba, mlb, nhl)
        expiring_within_hours: Only show markets expiring within N hours (e.g., 48 for next 2 days)
    """
    if not state.cached_sports_opportunities:
        return {
            "opportunities": [],
            "summary": {
                "total": 0,
                "message": "No sports data. Call /api/sports/refresh to scan."
            },
            "last_updated": None
        }
    
    opps = state.cached_sports_opportunities
    
    # Filter by min difference
    opps = [o for o in opps if o.get("price_difference_percent", 0) >= min_difference]
    
    # Filter by league if specified
    if league:
        opps = [o for o in opps if o.get("league", "").lower() == league.lower()]
    
    # Filter by expiration time if specified
    if expiring_within_hours:
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=expiring_within_hours)
        
        filtered_opps = []
        for o in opps:
            # Get expiration time from either platform (prefer Kalshi's expected_expiration_time)
            kalshi_exp = o.get("kalshi", {}).get("expected_expiration_time")
            poly_exp = o.get("polymarket", {}).get("end_date")
            
            # Use the earliest available expiration time
            exp_time = None
            if kalshi_exp:
                try:
                    exp_time = datetime.fromisoformat(kalshi_exp.replace("Z", "+00:00"))
                except:
                    pass
            
            if not exp_time and poly_exp:
                try:
                    exp_time = datetime.fromisoformat(poly_exp.replace("Z", "+00:00"))
                except:
                    pass
            
            # Include if expires within the window
            if exp_time and now < exp_time <= cutoff:
                filtered_opps.append(o)
        
        opps = filtered_opps
    
    return {
        "opportunities": opps,
        "summary": {
            "total": len(opps),
            "by_league": _count_by_league(opps),
            "avg_difference": sum(o.get("price_difference_percent", 0) for o in opps) / len(opps) if opps else 0
        },
        "last_updated": state.last_fetch.isoformat() if state.last_fetch else None
    }


@app.post("/api/sports/refresh")
async def refresh_sports_data(background_tasks: BackgroundTasks):
    """
    Refresh sports market data and find arbitrage opportunities.
    """
    if state.is_fetching:
        return {"status": "in_progress", "message": "A refresh is already running"}
    
    background_tasks.add_task(fetch_and_analyze_sports)
    
    return {
        "status": "started",
        "message": "Sports scan started in background"
    }


async def fetch_and_analyze_sports():
    """
    Background task to fetch and analyze sports markets.
    
    Uses "Kalshi-first" strategy:
    1. Fetch Kalshi sports games (well-structured by series)
    2. Parse game info (teams, dates) from Kalshi markets
    3. Build Polymarket slugs from that data
    4. Fetch Polymarket markets by those specific slugs
    5. Match and analyze for arbitrage
    """
    if state.is_fetching:
        return
    
    state.is_fetching = True
    logger.info("Starting sports market fetch and analysis (Kalshi-first strategy)...")
    
    try:
        normalizer = get_normalizer()
        slug_builder = get_slug_builder()
        
        # Step 1: Fetch Kalshi sports games first
        logger.info("Step 1: Fetching Kalshi sports markets...")
        kalshi_markets = await state.kalshi_client.get_sports_markets()
        
        if isinstance(kalshi_markets, Exception):
            logger.error(f"Kalshi fetch failed: {kalshi_markets}")
            kalshi_markets = []
        
        logger.info(f"Found {len(kalshi_markets)} Kalshi sports markets")
        
        # Step 2: Parse Kalshi games and build Polymarket slugs
        logger.info("Step 2: Building Polymarket slugs from Kalshi games...")
        polymarket_slugs = set()
        kalshi_game_info = {}  # Map slug -> kalshi game info for matching
        
        for market in kalshi_markets:
            ticker = market.ticker
            # Parse the Kalshi ticker to extract teams and date
            away_team, home_team, game_date, sport = normalizer.parse_kalshi_ticker(ticker)
            
            if away_team and home_team and game_date and sport != Sport.UNKNOWN:
                # Build the Polymarket slug
                slug = slug_builder.build_slug(sport, away_team, home_team, game_date)
                if slug:
                    polymarket_slugs.add(slug)
                    kalshi_game_info[slug] = {
                        "away": away_team,
                        "home": home_team,
                        "date": game_date,
                        "sport": sport
                    }
                    logger.debug(f"Built slug: {slug} from ticker: {ticker}")
        
        logger.info(f"Built {len(polymarket_slugs)} unique Polymarket slugs to query")
        
        # Step 3: Fetch Polymarket markets by those specific slugs
        logger.info("Step 3: Fetching Polymarket events by slug...")
        poly_markets = await state.polymarket_client.get_events_by_slugs(list(polymarket_slugs))
        
        if isinstance(poly_markets, Exception):
            logger.error(f"Polymarket fetch failed: {poly_markets}")
            poly_markets = []
        
        logger.info(f"Fetched {len(poly_markets)} Polymarket markets from {len(polymarket_slugs)} slugs")
        
        # Update raw market cache
        state.cached_polymarket_markets = [m.to_dict() for m in poly_markets]
        state.cached_kalshi_markets = [m.to_dict() for m in kalshi_markets]
        
        # Use sports matcher
        matches = state.sports_matcher.match_markets(poly_markets, kalshi_markets)
        
        # Calculate arbitrage opportunities from sports matches
        # IMPORTANT: Align prices correctly by team!
        # - Polymarket: YES = away team wins (first team in slug)
        # - Kalshi: Ticker ends with winner abbreviation (e.g., -SAC means YES = Kings win)
        sports_opportunities = []
        normalizer = get_normalizer()
        
        for match in matches:
            poly = match["polymarket"]
            kalshi = match["kalshi"]
            poly_info = match.get("poly_info")
            
            # Parse Polymarket teams from slug
            # Format: nba-lal-sac-2026-01-12 -> away=lal (Lakers), home=sac (Kings)
            poly_slug = poly.slug if hasattr(poly, 'slug') else ""
            poly_away, poly_home, game_date, sport = normalizer.parse_polymarket_slug(poly_slug)
            
            # Parse which team Kalshi's YES refers to from the ticker
            # Format: KXNBAGAME-26JAN12LALSAC-SAC (last part is the winner)
            kalshi_ticker = kalshi.ticker
            ticker_parts = kalshi_ticker.split("-")
            kalshi_yes_team_abbrev = ticker_parts[-1].lower() if ticker_parts else ""
            kalshi_yes_team = normalizer.normalize_team(kalshi_yes_team_abbrev, sport)
            
            # Skip if we can't determine alignment
            if not poly_away or not poly_home or not kalshi_yes_team:
                continue
            
            # Polymarket: YES = away team wins, NO = home team wins
            poly_away_price = poly.yes_price  # Price for away team winning
            poly_home_price = poly.no_price   # Price for home team winning
            
            # Align prices based on which team Kalshi's YES refers to
            if kalshi_yes_team == poly_away:
                # Both refer to away team
                aligned_poly_price = poly_away_price
                aligned_kalshi_price = kalshi.yes_price
                market_team = poly_away
            elif kalshi_yes_team == poly_home:
                # Kalshi YES is for home team, Poly NO is for home team
                aligned_poly_price = poly_home_price
                aligned_kalshi_price = kalshi.yes_price
                market_team = poly_home
            else:
                # Can't align - skip
                continue
            
            # Calculate TRUE price difference (after alignment)
            price_diff = abs(aligned_poly_price - aligned_kalshi_price)
            price_diff_pct = price_diff * 100
            
            # Skip tiny differences (less than 1%)
            if price_diff_pct < 1.0:
                continue
            
            # Determine arbitrage direction
            if aligned_poly_price < aligned_kalshi_price:
                buy_platform = "polymarket"
                sell_platform = "kalshi"
            else:
                buy_platform = "kalshi"
                sell_platform = "polymarket"
            
            # Calculate profit potential (in basis points)
            profit_bps = int(price_diff * 10000)
            
            # Get current timestamp for price freshness
            price_timestamp = datetime.utcnow().isoformat()
            
            opp = {
                "polymarket": {
                    "id": poly.id,
                    "question": poly.question,
                    "yes_price": poly.yes_price,
                    "no_price": poly.no_price,
                    "aligned_price": aligned_poly_price,  # Price for market_team
                    "url": f"https://polymarket.com/event/{poly.slug}" if hasattr(poly, 'slug') else "",
                    "end_date": poly.end_date.isoformat() if poly.end_date else None,
                    # Market metrics
                    "volume": getattr(poly, 'volume', 0) or 0,
                    "liquidity": getattr(poly, 'liquidity', 0) or 0,
                    "volume_24h": getattr(poly, 'volume_24h', None),  # May not be available
                    "open_interest": getattr(poly, 'open_interest', None),  # May not be available
                    "fetched_at": price_timestamp
                },
                "kalshi": {
                    "id": kalshi.ticker,
                    "question": kalshi.question,
                    "yes_price": kalshi.yes_price,
                    "no_price": kalshi.no_price,
                    "aligned_price": aligned_kalshi_price,  # Price for market_team
                    "url": f"https://kalshi.com/markets/{kalshi.ticker}",
                    "expected_expiration_time": kalshi.expected_expiration_time.isoformat() if kalshi.expected_expiration_time else None,
                    "close_time": kalshi.close_time.isoformat() if kalshi.close_time else None,
                    # Market metrics
                    "volume": getattr(kalshi, 'volume', 0) or 0,
                    "volume_24h": getattr(kalshi, 'volume_24h', 0) or 0,
                    "open_interest": getattr(kalshi, 'open_interest', 0) or 0,
                    "liquidity": None,  # Kalshi doesn't provide liquidity directly
                    "fetched_at": price_timestamp
                },
                "market_team": market_team,  # Which team this arbitrage is for
                "league": poly_info.league.value if poly_info else "unknown",
                "market_type": poly_info.market_type.value if poly_info else "unknown",
                "team": market_team,
                "price_difference": price_diff,
                "price_difference_percent": price_diff_pct,
                "profit_bps": profit_bps,
                "buy_on": buy_platform,
                "sell_on": sell_platform,
                "match_score": match.get("score", 0),
                "match_reason": match.get("match_reason", "")
            }
            
            sports_opportunities.append(opp)
        
        # Sort by price difference
        sports_opportunities.sort(key=lambda x: x["price_difference_percent"], reverse=True)
        
        state.cached_sports_opportunities = sports_opportunities
        state.last_fetch = datetime.utcnow()
        
        logger.info(f"Found {len(sports_opportunities)} sports arbitrage opportunities")
        
    except Exception as e:
        logger.error(f"Error in fetch_and_analyze_sports: {e}", exc_info=True)
    finally:
        state.is_fetching = False


def _count_by_league(opportunities: List[Dict]) -> Dict[str, int]:
    """Count opportunities by league."""
    counts = {}
    for opp in opportunities:
        league = opp.get("league", "unknown")
        counts[league] = counts.get(league, 0) + 1
    return counts


@app.get("/api/debug/markets")
async def debug_markets():
    """Debug endpoint to see sample markets from both platforms."""
    poly_samples = state.cached_polymarket_markets[:20] if state.cached_polymarket_markets else []
    kalshi_samples = state.cached_kalshi_markets[:20] if state.cached_kalshi_markets else []
    
    return {
        "polymarket": {
            "count": len(state.cached_polymarket_markets),
            "samples": [
                {"id": m.get("id"), "question": m.get("question", m.get("title", ""))[:100]}
                for m in poly_samples
            ]
        },
        "kalshi": {
            "count": len(state.cached_kalshi_markets),
            "samples": [
                {"id": m.get("id", m.get("ticker")), "question": m.get("question", m.get("title", ""))[:100]}
                for m in kalshi_samples
            ]
        },
        "matcher_config": {
            "threshold": state.market_matcher.match_threshold if state.market_matcher else None,
            "high_value_keywords": state.market_matcher.HIGH_VALUE_KEYWORDS[:10] if state.market_matcher else [],
            "topic_categories": list(state.market_matcher.TOPIC_CATEGORIES.keys()) if state.market_matcher else []
        },
        "sports_matcher": {
            "threshold": state.sports_matcher.match_threshold if state.sports_matcher else None,
            "cached_sports_opps": len(state.cached_sports_opportunities)
        }
    }


@app.get("/api/sports/all-markets")
async def get_all_sports_markets():
    """
    Get all sports markets from both platforms for debugging/comparison.
    Shows normalized names for easy matching comparison.
    """
    normalizer = get_normalizer()
    poly_markets = state.cached_polymarket_markets
    kalshi_markets = state.cached_kalshi_markets
    
    # Format Polymarket markets with normalized names
    poly_formatted = []
    for m in poly_markets:
        category = m.get("category", "")
        question = m.get("question", "")
        slug = m.get("slug", "")
        
        # Use normalizer to extract teams and create normalized name
        away_team, home_team, game_date, sport = normalizer.parse_polymarket_slug(slug)
        normalized_name = normalizer.create_normalized_name(away_team, home_team) if away_team and home_team else question
        
        poly_formatted.append({
            "id": m.get("id"),
            "name": question,
            "normalized_name": normalized_name,
            "away_team": away_team,
            "home_team": home_team,
            "game_date": game_date,
            "sport": sport.value if sport else None,
            "slug": slug,
            "yes_price": m.get("yes_price", 0),
            "no_price": m.get("no_price", 0),
            "category": category,
            "end_date": m.get("end_date"),
        })
    
    # Format Kalshi markets with normalized names
    kalshi_formatted = []
    for m in kalshi_markets:
        category = m.get("category", "")
        ticker = m.get("ticker", m.get("id", ""))
        question = m.get("question", m.get("title", ""))
        
        # Use normalizer to extract teams and create normalized name
        away_team, home_team, game_date, sport = normalizer.parse_kalshi_ticker(ticker)
        normalized_name = normalizer.create_normalized_name(away_team, home_team) if away_team and home_team else question
        
        kalshi_formatted.append({
            "id": ticker,
            "name": question,
            "normalized_name": normalized_name,
            "away_team": away_team,
            "home_team": home_team,
            "game_date": game_date,
            "sport": sport.value if sport else None,
            "series": m.get("series_ticker", ""),
            "yes_price": m.get("yes_price", 0),
            "no_price": m.get("no_price", 0),
            "category": category,
            "expiration": m.get("expected_expiration_time"),
        })
    
    # Group by market type for easier viewing
    # Polymarket: identify single-game markets by slug pattern (nba-xxx-xxx-YYYY-MM-DD)
    single_game_slugs = ['nba-', 'nfl-', 'nhl-', 'mlb-', 'cbb-', 'cfb-', 'wnba-', 'cwbb-', 'ufc-']
    poly_single_game = [m for m in poly_formatted 
                        if any(m.get("slug", "").lower().startswith(prefix) for prefix in single_game_slugs)
                        and m.get("away_team") and m.get("home_team")]
    poly_futures = [m for m in poly_formatted if m not in poly_single_game]
    
    # Kalshi: identify by category or series ticker
    kalshi_single_game = [m for m in kalshi_formatted if "single_game" in m.get("category", "")]
    kalshi_futures = [m for m in kalshi_formatted if m.get("category", "") == "futures"]
    
    # Find potential matches (same normalized name and date)
    # IMPORTANT: Align outcomes correctly!
    # - Polymarket: YES = away_team wins (first team in slug)
    # - Kalshi: Separate markets for each team, ticker ends with winner abbreviation
    #   e.g., KXNBAGAME-26JAN12LALSAC-SAC means YES = Kings win
    #         KXNBAGAME-26JAN12LALSAC-LAL means YES = Lakers win
    matches = []
    seen_game_dates = set()  # Track unique games to avoid duplicates
    
    for pm in poly_single_game:
        if not pm.get("normalized_name") or pm["normalized_name"] == pm["name"]:
            continue  # Skip if normalization failed
        
        poly_away = pm.get("away_team")
        poly_home = pm.get("home_team")
        if not poly_away or not poly_home:
            continue
            
        for km in kalshi_single_game:
            if not km.get("normalized_name") or km["normalized_name"] == km["name"]:
                continue
            
            # Check if teams match (order-agnostic)
            kalshi_away = km.get("away_team")
            kalshi_home = km.get("home_team")
            poly_teams = {poly_away, poly_home}
            kalshi_teams = {kalshi_away, kalshi_home} - {None}
            
            if poly_teams != kalshi_teams or len(kalshi_teams) != 2:
                continue
                
            # Check date matches
            if pm.get("game_date") != km.get("game_date"):
                continue
            
            # Parse which team Kalshi's YES refers to from the ticker
            # Format: KXNBAGAME-26JAN12LALSAC-SAC (last part is the winner)
            kalshi_ticker = km.get("id", "")
            ticker_parts = kalshi_ticker.split("-")
            kalshi_yes_team_abbrev = ticker_parts[-1].lower() if ticker_parts else ""
            
            # Normalize the Kalshi winner abbreviation to canonical team name
            kalshi_yes_team = normalizer.normalize_team(kalshi_yes_team_abbrev, 
                                                        normalizer.detect_sport("", kalshi_ticker, ""))
            
            # Skip if we can't determine which team Kalshi YES is for
            if not kalshi_yes_team or kalshi_yes_team not in poly_teams:
                continue
            
            # Polymarket: YES = away_team wins, NO = home_team wins
            poly_away_price = pm["yes_price"]  # Price for away team winning
            poly_home_price = pm["no_price"]   # Price for home team winning
            
            # Align prices based on which team Kalshi's YES refers to
            if kalshi_yes_team == poly_away:
                # Both refer to away team - compare directly
                aligned_poly_price = poly_away_price
                aligned_kalshi_price = km["yes_price"]
                market_team = poly_away
            else:
                # Kalshi YES is for home team, Poly NO is for home team
                aligned_poly_price = poly_home_price
                aligned_kalshi_price = km["yes_price"]
                market_team = poly_home
            
            # Calculate true price difference (should be small if no arbitrage)
            price_diff = abs(aligned_poly_price - aligned_kalshi_price) * 100
            
            # Create unique key to avoid duplicate matches
            game_key = f"{pm['game_date']}_{poly_away}_{poly_home}_{market_team}"
            if game_key in seen_game_dates:
                continue
            seen_game_dates.add(game_key)
            
            matches.append({
                "normalized_name": pm["normalized_name"],
                "game_date": pm["game_date"],
                "market_for_team": market_team,  # Which team this comparison is for
                "polymarket": {
                    "id": pm["id"],
                    "price": aligned_poly_price,  # Price for market_team to win
                    "slug": pm.get("slug", ""),
                },
                "kalshi": {
                    "id": km["id"],
                    "price": aligned_kalshi_price,  # Price for market_team to win
                },
                "price_diff": price_diff,  # True arbitrage difference
            })
    
    return {
        "polymarket": {
            "total": len(poly_formatted),
            "single_game": {
                "count": len(poly_single_game),
                "markets": poly_single_game[:100]
            },
            "futures": {
                "count": len(poly_futures),
                "markets": poly_futures[:100]
            }
        },
        "kalshi": {
            "total": len(kalshi_formatted),
            "single_game": {
                "count": len(kalshi_single_game),
                "markets": kalshi_single_game[:100]
            },
            "futures": {
                "count": len(kalshi_futures),
                "markets": kalshi_futures[:100]
            }
        },
        "matches": {
            "count": len(matches),
            "markets": matches[:50]
        },
        "last_updated": state.last_fetch.isoformat() if state.last_fetch else None
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )

