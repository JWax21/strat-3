"""
Polymarket API Client

Handles communication with Polymarket's APIs:
- Gamma API: Market discovery and metadata
- CLOB API: Real-time prices, orderbook depth, and trading

Documentation: https://docs.polymarket.com/quickstart/overview
"""
import httpx
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from config import get_settings
from utils.rate_limiter import RateLimiterManager

logger = logging.getLogger(__name__)


class MarketStatus(str, Enum):
    """Polymarket market status values."""
    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"


@dataclass
class PolymarketMarket:
    """Normalized Polymarket market data."""
    id: str
    condition_id: str
    question: str
    description: str
    outcomes: List[str]
    outcome_prices: List[float]  # Prices for each outcome (0-1)
    volume: float
    liquidity: float
    end_date: Optional[datetime]
    category: str
    tags: List[str]
    status: str
    slug: str
    image: Optional[str]
    
    @property
    def yes_price(self) -> float:
        """Get the YES price (first outcome)."""
        return self.outcome_prices[0] if self.outcome_prices else 0.0
    
    @property
    def no_price(self) -> float:
        """Get the NO price (second outcome)."""
        return self.outcome_prices[1] if len(self.outcome_prices) > 1 else 1 - self.yes_price
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "condition_id": self.condition_id,
            "question": self.question,
            "description": self.description,
            "outcomes": self.outcomes,
            "outcome_prices": self.outcome_prices,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "volume": self.volume,
            "liquidity": self.liquidity,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "category": self.category,
            "tags": self.tags,
            "status": self.status,
            "slug": self.slug,
            "image": self.image,
            "platform": "polymarket"
        }


class PolymarketClient:
    """
    Client for interacting with Polymarket APIs.
    
    Uses the Gamma API for market discovery and the CLOB API for pricing data.
    Implements rate limiting to respect API constraints.
    """
    
    def __init__(self):
        settings = get_settings()
        self.gamma_url = settings.polymarket_gamma_api_url
        self.clob_url = settings.polymarket_clob_api_url
        self.rate_limiter = RateLimiterManager.get_limiter(
            "polymarket", 
            settings.polymarket_rate_limit
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ArbitragePlatform/1.0"
                }
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def _request(
        self, 
        base_url: str, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a rate-limited request to the API.
        
        Args:
            base_url: Base URL for the API
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response data
        """
        await self.rate_limiter.acquire()
        
        client = await self._get_client()
        url = f"{base_url}{endpoint}"
        
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Polymarket: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching from Polymarket: {e}")
            raise
    
    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False
    ) -> List[PolymarketMarket]:
        """
        Fetch markets from the Gamma API.
        
        Args:
            limit: Maximum number of markets to return
            offset: Pagination offset
            active: Include active markets
            closed: Include closed markets
            
        Returns:
            List of normalized market objects
        """
        params = {
            "limit": min(limit, 100),  # Gamma API max is 100
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }
        
        data = await self._request(self.gamma_url, "/markets", params)
        
        markets = []
        for item in data if isinstance(data, list) else data.get("markets", []):
            try:
                market = self._parse_market(item)
                if market:
                    markets.append(market)
            except Exception as e:
                logger.warning(f"Failed to parse Polymarket market: {e}")
                continue
        
        return markets
    
    async def get_all_active_markets(self, max_markets: int = 500) -> List[PolymarketMarket]:
        """
        Fetch all active markets using both the /markets and /events endpoints
        for comprehensive coverage.
        
        Args:
            max_markets: Maximum total markets to fetch
            
        Returns:
            List of all active markets
        """
        all_markets = []
        seen_ids = set()
        
        # Strategy 1: Get markets from /events endpoint (better for nested markets)
        logger.info("Fetching markets from /events endpoint...")
        try:
            event_markets = await self.get_markets_from_events(max_markets=max_markets)
            for market in event_markets:
                if market.id not in seen_ids:
                    all_markets.append(market)
                    seen_ids.add(market.id)
        except Exception as e:
            logger.warning(f"Failed to fetch from events: {e}")
        
        # Strategy 2: Also get from /markets endpoint to catch any missed
        if len(all_markets) < max_markets:
            logger.info("Fetching additional markets from /markets endpoint...")
            offset = 0
            batch_size = 100
            
            while len(all_markets) < max_markets:
                markets = await self.get_markets(
                    limit=batch_size,
                    offset=offset,
                    active=True,
                    closed=False
                )
                
                if not markets:
                    break
                
                for market in markets:
                    if market.id not in seen_ids:
                        all_markets.append(market)
                        seen_ids.add(market.id)
                        
                offset += batch_size
                await asyncio.sleep(0.1)
        
        logger.info(f"Total active markets fetched: {len(all_markets)}")
        return all_markets[:max_markets]
    
    async def get_market_prices(self, token_ids: List[str]) -> Dict[str, float]:
        """
        Fetch current prices for specific tokens from the CLOB API.
        
        Args:
            token_ids: List of token IDs to fetch prices for
            
        Returns:
            Dictionary mapping token_id to price
        """
        if not token_ids:
            return {}
        
        prices = {}
        
        # Batch token IDs to avoid very long URLs
        batch_size = 20
        for i in range(0, len(token_ids), batch_size):
            batch = token_ids[i:i + batch_size]
            
            try:
                data = await self._request(
                    self.clob_url,
                    "/prices",
                    params={"token_ids": ",".join(batch)}
                )
                
                for token_id, price_data in data.items():
                    if isinstance(price_data, dict):
                        prices[token_id] = float(price_data.get("price", 0))
                    else:
                        prices[token_id] = float(price_data) if price_data else 0
                        
            except Exception as e:
                logger.warning(f"Failed to fetch prices for batch: {e}")
        
        return prices
    
    async def get_market_by_id(self, market_id: str) -> Optional[PolymarketMarket]:
        """
        Fetch a specific market by ID.
        
        Args:
            market_id: The market's condition ID
            
        Returns:
            Market object or None if not found
        """
        try:
            data = await self._request(self.gamma_url, f"/markets/{market_id}")
            return self._parse_market(data)
        except Exception as e:
            logger.error(f"Failed to fetch market {market_id}: {e}")
            return None
    
    async def get_events(
        self, 
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        tag: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch active events from the Gamma API.
        
        Events can contain multiple markets.
        
        Args:
            limit: Maximum number of events to return
            offset: Pagination offset
            active: Include active events
            closed: Include closed events
            tag: Filter by tag (e.g., "sports", "politics")
            
        Returns:
            List of event data
        """
        params = {
            "limit": min(limit, 100),
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }
        if tag:
            params["tag"] = tag
            
        data = await self._request(self.gamma_url, "/events", params)
        return data if isinstance(data, list) else data.get("events", [])
    
    async def get_all_active_events(self, max_events: int = 200) -> List[Dict[str, Any]]:
        """
        Fetch all active events with pagination.
        
        Args:
            max_events: Maximum total events to fetch
            
        Returns:
            List of all active events
        """
        all_events = []
        offset = 0
        batch_size = 100
        
        while len(all_events) < max_events:
            events = await self.get_events(
                limit=batch_size,
                offset=offset,
                active=True,
                closed=False
            )
            
            if not events:
                break
                
            all_events.extend(events)
            offset += batch_size
            
            await asyncio.sleep(0.1)
        
        logger.info(f"Fetched {len(all_events)} active events from Polymarket")
        return all_events[:max_events]
    
    async def get_markets_from_events(self, max_markets: int = 500) -> List[PolymarketMarket]:
        """
        Fetch markets by first getting active events, then extracting their markets.
        This provides better coverage than the /markets endpoint alone.
        
        Args:
            max_markets: Maximum total markets to fetch
            
        Returns:
            List of markets from active events
        """
        all_markets = []
        seen_ids = set()
        
        # Get active events
        events = await self.get_all_active_events(max_events=200)
        
        for event in events:
            # Each event can have multiple markets
            event_markets = event.get("markets", [])
            
            for market_data in event_markets:
                if len(all_markets) >= max_markets:
                    break
                    
                market_id = market_data.get("id", "")
                if market_id in seen_ids:
                    continue
                    
                try:
                    market = self._parse_market(market_data)
                    if market:
                        all_markets.append(market)
                        seen_ids.add(market_id)
                except Exception as e:
                    logger.warning(f"Failed to parse market from event: {e}")
                    
            if len(all_markets) >= max_markets:
                break
        
        logger.info(f"Extracted {len(all_markets)} markets from {len(events)} events")
        return all_markets
    
    def _parse_market(self, data: Dict[str, Any]) -> Optional[PolymarketMarket]:
        """
        Parse raw API data into a PolymarketMarket object.
        
        Args:
            data: Raw market data from API
            
        Returns:
            Normalized market object
        """
        if not data:
            return None
        
        # Extract outcome data
        outcomes = []
        outcome_prices = []
        
        # Handle different response formats
        if "outcomes" in data:
            outcomes = data["outcomes"] if isinstance(data["outcomes"], list) else []
        
        if "outcomePrices" in data:
            prices = data["outcomePrices"]
            if isinstance(prices, list):
                outcome_prices = [float(p) if p else 0 for p in prices]
            elif isinstance(prices, str):
                # Sometimes it's a JSON string
                try:
                    import json
                    outcome_prices = [float(p) for p in json.loads(prices)]
                except:
                    outcome_prices = []
        
        # If outcomes not set, default to Yes/No
        if not outcomes:
            outcomes = ["Yes", "No"]
        
        # Parse end date
        end_date = None
        if data.get("endDate"):
            try:
                end_date = datetime.fromisoformat(
                    data["endDate"].replace("Z", "+00:00")
                )
            except:
                pass
        
        return PolymarketMarket(
            id=str(data.get("id", "")),
            condition_id=data.get("conditionId", data.get("condition_id", "")),
            question=data.get("question", ""),
            description=data.get("description", ""),
            outcomes=outcomes,
            outcome_prices=outcome_prices,
            volume=float(data.get("volume", 0) or 0),
            liquidity=float(data.get("liquidity", 0) or 0),
            end_date=end_date,
            category=data.get("category", ""),
            tags=data.get("tags", []) if isinstance(data.get("tags"), list) else [],
            status=data.get("active", True) and "active" or "closed",
            slug=data.get("slug", ""),
            image=data.get("image", None)
        )
    
    async def search_markets(self, query: str, limit: int = 50) -> List[PolymarketMarket]:
        """
        Search for markets matching a query.
        
        Args:
            query: Search query string
            limit: Maximum results
            
        Returns:
            Matching markets
        """
        try:
            data = await self._request(
                self.gamma_url,
                "/markets",
                params={"_q": query, "limit": limit, "active": "true"}
            )
            
            markets = []
            for item in data if isinstance(data, list) else data.get("markets", []):
                market = self._parse_market(item)
                if market:
                    markets.append(market)
            
            return markets
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def get_sports_markets(self, max_markets: int = 500) -> List[PolymarketMarket]:
        """
        Fetch sports-related markets from Polymarket.
        
        Strategy: Get all active events with deep pagination (up to offset 6000+)
        to capture single-game markets which are created earlier and have lower IDs.
        
        Filter for:
        1. Single-game markets (identified by slug pattern: sport-team-team-date)
        2. Futures/awards markets (championship, MVP, etc.)
        
        Args:
            max_markets: Maximum markets to return
            
        Returns:
            List of sports-related markets
        """
        all_sports_markets = []
        seen_ids = set()
        
        # Slug prefixes for single-game markets
        single_game_prefixes = [
            'nba-', 'nfl-', 'nhl-', 'mlb-', 'cbb-', 'cfb-', 'wnba-', 
            'cwbb-',  # Women's college basketball
            'atp-', 'wta-',  # Tennis
            'ufc-',  # UFC/MMA
        ]
        
        # Sports-related keywords for futures/awards
        sports_title_keywords = [
            "super bowl", "nfl", "nba", "mlb", "nhl", "ufc", "mma",
            "championship", "playoffs", "world series", "stanley cup",
            "mvp", "rookie of the year", "coach of the year", "player of the year",
            "football", "basketball", "baseball", "hockey", "soccer",
            "premier league", "world cup", "ncaa", "college", 
            "passing yards", "rushing yards", "touchdown", "home run",
            "defensive", "offensive", "protector", "comeback", "halftime",
            "afc", "nfc", "division", "conference"
        ]
        
        logger.info("Fetching sports markets from Polymarket (deep pagination for single-game)...")
        
        try:
            # IMPORTANT: Single-game markets for TODAY are at offset 3000+
            # because they were created earlier (lower event IDs).
            # We need to paginate through ~6000 events to get all recent games.
            all_events = []
            offset = 0
            batch_size = 500  # Increased batch size for efficiency
            max_offset = 6000  # Go deep enough to find today's games
            
            while offset < max_offset:
                params = {
                    "order": "id",
                    "ascending": "false",
                    "closed": "false",
                    "limit": batch_size,
                    "offset": offset
                }
                
                data = await self._request(self.gamma_url, "/events", params)
                events = data if isinstance(data, list) else data.get("events", [])
                
                if not events:
                    logger.info(f"No more events at offset {offset}")
                    break
                    
                all_events.extend(events)
                offset += batch_size
                
                # Log progress every 1000 events
                if offset % 1000 == 0:
                    logger.info(f"Fetched {len(all_events)} events so far (offset {offset})...")
                
                await asyncio.sleep(0.05)  # Slightly faster pagination
            
            logger.info(f"Retrieved {len(all_events)} total events from Polymarket, filtering for sports...")
            
            single_game_count = 0
            futures_count = 0
            
            for event in all_events:
                event_title = event.get("title", "").lower()
                event_slug = event.get("slug", "").lower()
                event_category = (event.get("category") or "").lower()
                
                # Check if it's a single-game market (e.g., nba-uta-cle-2026-01-12)
                is_single_game = any(
                    event_slug.startswith(prefix) and len(event_slug.split('-')) >= 4
                    for prefix in single_game_prefixes
                )
                
                # Check if it's a sports futures/awards market
                is_sports_futures = (
                    event_category == "sports" or
                    any(kw in event_title for kw in sports_title_keywords)
                )
                
                if not (is_single_game or is_sports_futures):
                    continue
                
                # Extract markets from this event
                event_markets = event.get("markets", [])
                
                for market_data in event_markets:
                    if len(all_sports_markets) >= max_markets:
                        break
                    
                    market_id = str(market_data.get("id", ""))
                    if market_id in seen_ids or not market_id:
                        continue
                    
                    try:
                        market = self._parse_market(market_data)
                        if market and market.yes_price > 0:
                            # Add sport type info to the market based on slug
                            if is_single_game:
                                market.category = f"single_game_{event_slug.split('-')[0]}"
                                single_game_count += 1
                            else:
                                futures_count += 1
                            all_sports_markets.append(market)
                            seen_ids.add(market_id)
                    except Exception as e:
                        logger.warning(f"Failed to parse sports market: {e}")
                
                if len(all_sports_markets) >= max_markets:
                    break
            
            logger.info(f"Found {single_game_count} single-game markets, {futures_count} futures/awards markets")
            
        except Exception as e:
            logger.error(f"Failed to fetch sports events: {e}", exc_info=True)
        
        logger.info(f"Total sports markets on Polymarket: {len(all_sports_markets)}")
        return all_sports_markets[:max_markets]

