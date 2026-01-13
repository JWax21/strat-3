"""
Kalshi API Client

Handles communication with Kalshi's trading API.
Structure: Series → Events → Markets

Documentation: https://docs.kalshi.com/
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


class KalshiMarketStatus(str, Enum):
    """Kalshi market status values."""
    OPEN = "open"
    CLOSED = "closed"
    SETTLED = "settled"


@dataclass
class KalshiSeries:
    """Kalshi series data (collection of related events)."""
    ticker: str
    title: str
    category: str
    tags: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "title": self.title,
            "category": self.category,
            "tags": self.tags
        }


@dataclass
class KalshiEvent:
    """Kalshi event data (specific occurrence within a series)."""
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    category: str
    mutually_exclusive: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_ticker": self.event_ticker,
            "series_ticker": self.series_ticker,
            "title": self.title,
            "subtitle": self.subtitle,
            "category": self.category,
            "mutually_exclusive": self.mutually_exclusive
        }


@dataclass
class KalshiMarket:
    """Normalized Kalshi market data."""
    ticker: str
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    question: str  # Combined title for matching
    yes_price: float  # Price in cents (0-100) -> converted to 0-1
    no_price: float
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    volume: int
    volume_24h: int
    open_interest: int
    status: str
    close_time: Optional[datetime]
    expected_expiration_time: Optional[datetime]  # When market is expected to expire
    result: Optional[str]
    category: str
    
    @property
    def mid_price(self) -> float:
        """Get the mid price between bid and ask."""
        if self.yes_bid and self.yes_ask:
            return (self.yes_bid + self.yes_ask) / 2
        return self.yes_price
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.ticker,
            "ticker": self.ticker,
            "event_ticker": self.event_ticker,
            "series_ticker": self.series_ticker,
            "title": self.title,
            "subtitle": self.subtitle,
            "question": self.question,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "yes_bid": self.yes_bid,
            "yes_ask": self.yes_ask,
            "no_bid": self.no_bid,
            "no_ask": self.no_ask,
            "mid_price": self.mid_price,
            "volume": self.volume,
            "volume_24h": self.volume_24h,
            "open_interest": self.open_interest,
            "status": self.status,
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "expected_expiration_time": self.expected_expiration_time.isoformat() if self.expected_expiration_time else None,
            "result": self.result,
            "category": self.category,
            "platform": "kalshi"
        }


class KalshiClient:
    """
    Client for interacting with Kalshi's trading API.
    
    Kalshi uses a hierarchical structure:
    - Series: A category of related events (e.g., "US Presidential Election")
    - Events: Specific occurrences (e.g., "2024 Presidential Election Winner")
    - Markets: Trading contracts (e.g., "Will Biden win?")
    
    Implements rate limiting to respect API constraints.
    """
    
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.kalshi_api_url
        self.rate_limiter = RateLimiterManager.get_limiter(
            "kalshi",
            settings.kalshi_rate_limit
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
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a rate-limited request to the Kalshi API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response data
        """
        await self.rate_limiter.acquire()
        
        client = await self._get_client()
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Kalshi: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching from Kalshi: {e}")
            raise
    
    async def get_exchange_status(self) -> Dict[str, Any]:
        """
        Check the exchange status.
        
        Returns:
            Exchange status information
        """
        return await self._request("/exchange/status")
    
    async def get_series_list(self, limit: int = 100, cursor: str = None) -> List[KalshiSeries]:
        """
        Fetch list of all series.
        
        Args:
            limit: Maximum number of series to return
            cursor: Pagination cursor
            
        Returns:
            List of series objects
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        data = await self._request("/series", params)
        
        series_list = []
        for item in data.get("series", []):
            series = KalshiSeries(
                ticker=item.get("ticker", ""),
                title=item.get("title", ""),
                category=item.get("category", ""),
                tags=item.get("tags", [])
            )
            series_list.append(series)
        
        return series_list
    
    async def get_series(self, series_ticker: str) -> Optional[KalshiSeries]:
        """
        Fetch a specific series by ticker.
        
        Args:
            series_ticker: The series ticker
            
        Returns:
            Series object or None
        """
        try:
            data = await self._request(f"/series/{series_ticker}")
            series_data = data.get("series", data)
            
            return KalshiSeries(
                ticker=series_data.get("ticker", ""),
                title=series_data.get("title", ""),
                category=series_data.get("category", ""),
                tags=series_data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Failed to fetch series {series_ticker}: {e}")
            return None
    
    async def get_events(
        self,
        series_ticker: str = None,
        status: str = None,
        limit: int = 100,
        cursor: str = None
    ) -> List[KalshiEvent]:
        """
        Fetch events, optionally filtered by series.
        
        Args:
            series_ticker: Filter by series ticker
            status: Filter by status (e.g., "open")
            limit: Maximum results
            cursor: Pagination cursor
            
        Returns:
            List of event objects
        """
        params = {"limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        
        data = await self._request("/events", params)
        
        events = []
        for item in data.get("events", []):
            event = KalshiEvent(
                event_ticker=item.get("event_ticker", ""),
                series_ticker=item.get("series_ticker", ""),
                title=item.get("title", ""),
                subtitle=item.get("sub_title", item.get("subtitle", "")),
                category=item.get("category", ""),
                mutually_exclusive=item.get("mutually_exclusive", False)
            )
            events.append(event)
        
        return events
    
    async def get_event(self, event_ticker: str) -> Optional[KalshiEvent]:
        """
        Fetch a specific event by ticker.
        
        Args:
            event_ticker: The event ticker
            
        Returns:
            Event object or None
        """
        try:
            data = await self._request(f"/events/{event_ticker}")
            item = data.get("event", data)
            
            return KalshiEvent(
                event_ticker=item.get("event_ticker", ""),
                series_ticker=item.get("series_ticker", ""),
                title=item.get("title", ""),
                subtitle=item.get("sub_title", item.get("subtitle", "")),
                category=item.get("category", ""),
                mutually_exclusive=item.get("mutually_exclusive", False)
            )
        except Exception as e:
            logger.error(f"Failed to fetch event {event_ticker}: {e}")
            return None
    
    async def get_markets(
        self,
        event_ticker: str = None,
        series_ticker: str = None,
        status: str = None,
        limit: int = 100,
        cursor: str = None,
        min_close_ts: int = None,
        max_close_ts: int = None
    ) -> List[KalshiMarket]:
        """
        Fetch markets, optionally filtered.
        
        Args:
            event_ticker: Filter by event ticker
            series_ticker: Filter by series ticker
            status: Filter by status ("open", "closed", "settled")
            limit: Maximum results
            cursor: Pagination cursor
            min_close_ts: Minimum close timestamp (Unix seconds) - games closing after this time
            max_close_ts: Maximum close timestamp (Unix seconds) - games closing before this time
            
        Returns:
            List of market objects
        """
        params = {"limit": limit}
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        if min_close_ts:
            params["min_close_ts"] = min_close_ts
        if max_close_ts:
            params["max_close_ts"] = max_close_ts
        
        data = await self._request("/markets", params)
        
        markets = []
        for item in data.get("markets", []):
            market = self._parse_market(item)
            if market:
                markets.append(market)
        
        return markets
    
    # =========================================================================
    # SINGLE GAME MARKETS - Highest priority for arbitrage
    # =========================================================================
    SINGLE_GAME_SERIES = [
        # US Major Leagues
        "KXNBAGAME",       # NBA single games
        "KXNFLGAME",       # NFL single games
        "KXNHLGAME",       # NHL single games
        "KXMLBGAME",       # MLB single games
        "KXWNBAGAME",      # WNBA single games
        
        # College Sports
        "KXNCAABGAME",     # NCAA Men's Basketball (CBB)
        "KXNCAAMBGAME",    # NCAA Men's Basketball (alternate)
        "KXNCAAWBGAME",    # NCAA Women's Basketball
        "KXNCAAFGAME",     # NCAA Football
        "KXNCAAFBGAME",    # NCAA Football (alternate)
        "KXNCAAFCSGAME",   # NCAA Football Championship Series
        
        # International Basketball
        "KXEUROLEAGUEGAME", # EuroLeague Basketball
        "KXNBLGAME",       # NBL (Australian Basketball)
        
        # MMA/UFC
        "KXUFCFIGHT",      # UFC Fights
        
        # Tennis
        "KXTENNISMATCH",   # Tennis matches
        "KXATPTOUR",       # ATP Tour matches
        "KXWTATOUR",       # WTA Tour matches
        
        # Golf
        "KXPGATOUR",       # PGA Tour
        "KXLPGATOUR",      # LPGA Tour
        "KXGOLFTOURNAMENT", # Golf tournaments
        
        # Motorsport
        "KXF1RACE",        # Formula 1 races
        "KXNASCARRACE",    # NASCAR races
        "KXINDYCARRACE",   # IndyCar races
        
        # Cricket
        "KXCRICKETTESTMATCH",  # Cricket Test matches
        "KXCRICKETT20IMATCH",  # Cricket T20 International
        
        # Chess
        "KXCHESSMATCH",    # Chess matches
        
        # Esports
        "KXDOTA2GAME",     # Dota 2 games
    ]
    
    # =========================================================================
    # PLAYER PROPS - Player performance markets
    # =========================================================================
    PLAYER_PROPS_SERIES = [
        # NBA Props
        "KXNBAPTS",        # NBA Player Points
        "KXNBAREBS",       # NBA Player Rebounds
        "KXNBAASTS",       # NBA Player Assists
        "KXNBA3S",         # NBA Player 3-Pointers
        
        # NFL Props
        "KXNFLTD",         # NFL Touchdowns
        "KXNFLPASS",       # NFL Passing Yards
        "KXNFLRUSH",       # NFL Rushing Yards
        "KXNFLREC",        # NFL Receiving Yards
        
        # NHL Props
        "KXNHLPTS",        # NHL Player Points
        "KXNHLGOALS",      # NHL Player Goals
        
        # MLB Props
        "KXMLBHITS",       # MLB Player Hits
        "KXMLBHR",         # MLB Home Runs
        "KXMLBRBI",        # MLB RBIs
    ]
    
    # =========================================================================
    # FUTURES/AWARDS MARKETS - Championship and season-long markets
    # =========================================================================
    SPORTS_FUTURES_SERIES = [
        # NFL Championships & Awards
        "KXSB",            # Super Bowl
        "KXAFC",           # AFC Championship
        "KXNFC",           # NFC Championship
        "KXNFLSBMVP",      # Super Bowl MVP
        "KXNFLDPOY",       # Defensive Player of Year
        "KXNFLOROTY",      # Offensive Rookie of Year
        "KXNFLCPOY",       # Comeback Player of Year
        "KXNFLCOACH",      # Coach of the Year
        "KXNFLMVP",        # NFL MVP
        
        # NBA Championships & Awards
        "KXNBA",           # NBA Championship
        "KXNBAROY",        # NBA Rookie of the Year
        "KXNBAMVP",        # NBA MVP
        
        # NHL Championships & Awards
        "KXNHL",           # NHL Stanley Cup
        "KXNHLEAST",       # Eastern Conference
        "KXNHLWEST",       # Western Conference
        "KXNHLMVP",        # Hart Trophy
        
        # MLB Championships & Awards
        "KXMLB",           # MLB World Series
        "KXMLBALEAST",     # AL East Winner
        "KXMLBNLEAST",     # NL East Winner
        "KXMLBALROTY",     # AL Rookie of Year
        "KXMLBNLROTY",     # NL Rookie of Year
    ]
    
    async def get_sports_markets(
        self, 
        include_single_games: bool = True,
        max_expiration_hours: int = 48
    ) -> List[KalshiMarket]:
        """
        Fetch sports markets from Kalshi including:
        1. Single-game markets (NBA, NFL, NHL, MLB, etc.)
        2. Championship/award futures
        
        Args:
            include_single_games: Whether to include single-game markets
            max_expiration_hours: For single games, only include markets expiring within this many hours
                                  (default 48 = today and tomorrow). Uses expected_expiration_time, 
                                  not close_time (which is when trading closes, usually 2 weeks later).
            
        Returns:
            List of sports markets
        """
        from datetime import datetime, timezone, timedelta
        
        all_markets = []
        seen_tickers = set()
        single_game_count = 0
        futures_count = 0
        
        # Calculate cutoff for filtering single-game markets by expiration
        now = datetime.now(timezone.utc)
        max_expiration = now + timedelta(hours=max_expiration_hours)
        
        # Combine series lists
        all_series = []
        if include_single_games:
            all_series.extend(self.SINGLE_GAME_SERIES)
            all_series.extend(self.PLAYER_PROPS_SERIES)  # Include props with single games
        all_series.extend(self.SPORTS_FUTURES_SERIES)
        
        logger.info(f"Fetching sports markets from {len(all_series)} Kalshi series (games within {max_expiration_hours}h)...")
        
        props_count = 0
        
        for series_ticker in all_series:
            try:
                is_single_game = series_ticker in self.SINGLE_GAME_SERIES
                is_player_props = series_ticker in self.PLAYER_PROPS_SERIES
                
                # Fetch markets for this series
                # Note: We fetch all open markets, then filter client-side by expected_expiration_time
                # because the API's max_close_ts filters by trading close, not game time
                markets = await self.get_markets(
                    series_ticker=series_ticker,
                    status="open",
                    limit=200  # Fetch more to ensure we get recent games
                )
                
                for market in markets:
                    if market.ticker not in seen_tickers:
                        # Set the series ticker if not already set
                        if not market.series_ticker:
                            market.series_ticker = series_ticker
                        
                        # Tag the market type and apply date filtering
                        if is_single_game or is_player_props:
                            # Filter single-game and props markets by expected_expiration_time
                            if market.expected_expiration_time:
                                # Ensure timezone-aware comparison
                                exp_time = market.expected_expiration_time
                                if exp_time.tzinfo is None:
                                    exp_time = exp_time.replace(tzinfo=timezone.utc)
                                
                                # Skip games that are past the cutoff
                                if exp_time > max_expiration:
                                    continue
                                # Skip games that have already expired
                                if exp_time < now:
                                    continue
                            
                            # Categorize based on market type
                            if is_player_props:
                                # Extract sport from series ticker (e.g., KXNBAPTS -> nba)
                                sport = series_ticker.replace('KX', '').replace('PTS', '').replace('REBS', '').replace('ASTS', '').replace('3S', '').replace('TD', '').replace('PASS', '').replace('RUSH', '').replace('REC', '').replace('GOALS', '').replace('HITS', '').replace('HR', '').replace('RBI', '').lower()
                                market.category = f"props_{sport}"
                                props_count += 1
                            else:
                                market.category = f"single_game_{series_ticker.replace('KX', '').replace('GAME', '').lower()}"
                                single_game_count += 1
                        else:
                            market.category = "futures"
                            futures_count += 1
                        
                        all_markets.append(market)
                        seen_tickers.add(market.ticker)
                
                if markets:
                    logger.debug(f"Found {len(markets)} markets in series {series_ticker}")
                
                await asyncio.sleep(0.15)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Failed to fetch series {series_ticker}: {e}")
                continue
        
        logger.info(f"Kalshi sports: {single_game_count} single-game, {props_count} props, {futures_count} futures = {len(all_markets)} total")
        return all_markets
    
    async def get_all_open_markets(self, max_markets: int = 500) -> List[KalshiMarket]:
        """
        Fetch open markets directly from the /markets endpoint.
        Simple and fast - avoids excessive API calls.
        
        Args:
            max_markets: Maximum total markets to fetch
            
        Returns:
            List of open markets
        """
        all_markets = []
        seen_tickers = set()
        cursor = None
        batch_size = 100
        
        while len(all_markets) < max_markets:
            params = {"limit": batch_size, "status": "open"}
            if cursor:
                params["cursor"] = cursor
            
            try:
                data = await self._request("/markets", params)
                markets_data = data.get("markets", [])
                
                if not markets_data:
                    break
                
                for item in markets_data:
                    market = self._parse_market(item)
                    if market and market.ticker not in seen_tickers:
                        all_markets.append(market)
                        seen_tickers.add(market.ticker)
                
                cursor = data.get("cursor")
                if not cursor:
                    break
                
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Failed to fetch markets: {e}")
                break
        
        logger.info(f"Fetched {len(all_markets)} open markets from Kalshi")
        return all_markets[:max_markets]
    
    async def get_market(self, ticker: str) -> Optional[KalshiMarket]:
        """
        Fetch a specific market by ticker.
        
        Args:
            ticker: The market ticker
            
        Returns:
            Market object or None
        """
        try:
            data = await self._request(f"/markets/{ticker}")
            return self._parse_market(data.get("market", data))
        except Exception as e:
            logger.error(f"Failed to fetch market {ticker}: {e}")
            return None
    
    async def get_orderbook(self, ticker: str, depth: int = 10) -> Dict[str, Any]:
        """
        Fetch the orderbook for a market.
        
        Args:
            ticker: Market ticker
            depth: Number of price levels to return
            
        Returns:
            Orderbook data with bids and asks
        """
        data = await self._request(
            f"/markets/{ticker}/orderbook",
            params={"depth": depth}
        )
        return data.get("orderbook", data)
    
    def _parse_market(self, data: Dict[str, Any]) -> Optional[KalshiMarket]:
        """
        Parse raw API data into a KalshiMarket object.
        
        Args:
            data: Raw market data from API
            
        Returns:
            Normalized market object
        """
        if not data:
            return None
        
        # Parse close time
        close_time = None
        if data.get("close_time"):
            try:
                close_time = datetime.fromisoformat(
                    data["close_time"].replace("Z", "+00:00")
                )
            except:
                pass
        
        # Parse expected expiration time
        expected_expiration_time = None
        if data.get("expected_expiration_time"):
            try:
                expected_expiration_time = datetime.fromisoformat(
                    data["expected_expiration_time"].replace("Z", "+00:00")
                )
            except:
                pass
        
        # Kalshi prices are in cents (0-100), convert to decimal (0-1)
        def cents_to_decimal(cents: Any) -> float:
            if cents is None:
                return 0.0
            return float(cents) / 100.0
        
        # Get yes price - prefer last_price, fallback to yes_ask
        yes_price = cents_to_decimal(
            data.get("last_price") or 
            data.get("yes_ask") or 
            data.get("yes_bid") or 
            50  # Default to 50 cents if no price data
        )
        
        # Construct question from title and subtitle
        title = data.get("title", "")
        subtitle = data.get("subtitle", data.get("sub_title", ""))
        question = f"{title} - {subtitle}" if subtitle else title
        
        return KalshiMarket(
            ticker=data.get("ticker", ""),
            event_ticker=data.get("event_ticker", ""),
            series_ticker=data.get("series_ticker", ""),
            title=title,
            subtitle=subtitle,
            question=question,
            yes_price=yes_price,
            no_price=1.0 - yes_price,
            yes_bid=cents_to_decimal(data.get("yes_bid")),
            yes_ask=cents_to_decimal(data.get("yes_ask")),
            no_bid=cents_to_decimal(data.get("no_bid")),
            no_ask=cents_to_decimal(data.get("no_ask")),
            volume=int(data.get("volume", 0) or 0),
            volume_24h=int(data.get("volume_24h", 0) or 0),
            open_interest=int(data.get("open_interest", 0) or 0),
            status=data.get("status", ""),
            close_time=close_time,
            expected_expiration_time=expected_expiration_time,
            result=data.get("result"),
            category=data.get("category", "")
        )
    
    async def search_markets(self, query: str) -> List[KalshiMarket]:
        """
        Search for markets matching a query.
        
        Note: Kalshi doesn't have a direct search endpoint,
        so we fetch markets and filter locally.
        
        Args:
            query: Search query string
            
        Returns:
            Matching markets
        """
        markets = await self.get_all_open_markets(max_markets=500)
        
        query_lower = query.lower()
        matching = [
            m for m in markets 
            if query_lower in m.title.lower() or 
               query_lower in m.subtitle.lower() or
               query_lower in m.ticker.lower()
        ]
        
        return matching

