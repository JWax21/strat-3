"""
Sports Market Matching Service

Matches sports markets between Polymarket and Kalshi using
sport-specific rules for teams, leagues, championships, and seasons.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from clients.polymarket import PolymarketMarket
from clients.kalshi import KalshiMarket
from services.normalizer import get_normalizer, Sport

logger = logging.getLogger(__name__)


class League(Enum):
    """Supported sports leagues."""
    NFL = "nfl"
    NBA = "nba"
    MLB = "mlb"
    NHL = "nhl"
    SOCCER = "soccer"
    UFC = "ufc"
    GOLF = "golf"
    TENNIS = "tennis"
    UNKNOWN = "unknown"


class MarketType(Enum):
    """Types of sports markets."""
    CHAMPIONSHIP = "championship"  # Who wins the title
    MVP_SEASON = "mvp_season"  # Regular season MVP (NFL MVP, NBA MVP, etc.)
    MVP_GAME = "mvp_game"  # Championship game MVP (Super Bowl MVP, Finals MVP, etc.)
    DIVISION = "division"  # Division/conference winners
    PLAYER_AWARD = "player_award"  # ROY, DPOY, etc.
    GAME_WINNER = "game_winner"  # Single game outcomes (moneyline)
    SPREAD = "spread"  # Point spread bets (e.g., Lakers -9.5)
    OVER_UNDER = "over_under"  # Total points/goals bets (e.g., O/U 250.5)
    PLAYER_PROP = "player_prop"  # Player stats in a game
    SEASON_WINS = "season_wins"  # Win totals
    PARLAY = "parlay"  # Multi-leg bets
    UNKNOWN = "unknown"


@dataclass
class SportsMarketInfo:
    """Extracted information from a sports market."""
    league: League
    market_type: MarketType
    team: Optional[str]  # Primary team (for futures) or home team (for games)
    away_team: Optional[str]  # Away team (for games)
    player: Optional[str]
    championship: Optional[str]
    season: Optional[str]
    year: Optional[int]
    game_date: Optional[str]  # Date for single-game markets (YYYY-MM-DD)
    raw_question: str


# Team name mappings (various aliases to canonical names)
NFL_TEAMS = {
    # AFC East
    "bills": "Buffalo Bills", "buffalo": "Buffalo Bills", "buf": "Buffalo Bills",
    "dolphins": "Miami Dolphins", "miami": "Miami Dolphins", "mia": "Miami Dolphins",
    "patriots": "New England Patriots", "new england": "New England Patriots", "ne": "New England Patriots",
    "jets": "New York Jets", "nyj": "New York Jets",
    # AFC North
    "ravens": "Baltimore Ravens", "baltimore": "Baltimore Ravens", "bal": "Baltimore Ravens",
    "bengals": "Cincinnati Bengals", "cincinnati": "Cincinnati Bengals", "cin": "Cincinnati Bengals",
    "browns": "Cleveland Browns", "cleveland": "Cleveland Browns", "cle": "Cleveland Browns",
    "steelers": "Pittsburgh Steelers", "pittsburgh": "Pittsburgh Steelers", "pit": "Pittsburgh Steelers",
    # AFC South
    "texans": "Houston Texans", "houston": "Houston Texans", "hou": "Houston Texans",
    "colts": "Indianapolis Colts", "indianapolis": "Indianapolis Colts", "ind": "Indianapolis Colts",
    "jaguars": "Jacksonville Jaguars", "jacksonville": "Jacksonville Jaguars", "jax": "Jacksonville Jaguars",
    "titans": "Tennessee Titans", "tennessee": "Tennessee Titans", "ten": "Tennessee Titans",
    # AFC West
    "broncos": "Denver Broncos", "denver": "Denver Broncos", "den": "Denver Broncos",
    "chiefs": "Kansas City Chiefs", "kansas city": "Kansas City Chiefs", "kc": "Kansas City Chiefs",
    "raiders": "Las Vegas Raiders", "las vegas raiders": "Las Vegas Raiders", "lv": "Las Vegas Raiders",
    "chargers": "Los Angeles Chargers", "la chargers": "Los Angeles Chargers", "lac": "Los Angeles Chargers",
    # NFC East
    "cowboys": "Dallas Cowboys", "dallas": "Dallas Cowboys", "dal": "Dallas Cowboys",
    "giants": "New York Giants", "nyg": "New York Giants",
    "eagles": "Philadelphia Eagles", "philadelphia": "Philadelphia Eagles", "phi": "Philadelphia Eagles",
    "commanders": "Washington Commanders", "washington": "Washington Commanders", "was": "Washington Commanders",
    # NFC North
    "bears": "Chicago Bears", "chicago": "Chicago Bears", "chi": "Chicago Bears",
    "lions": "Detroit Lions", "detroit": "Detroit Lions", "det": "Detroit Lions",
    "packers": "Green Bay Packers", "green bay": "Green Bay Packers", "gb": "Green Bay Packers",
    "vikings": "Minnesota Vikings", "minnesota": "Minnesota Vikings", "min": "Minnesota Vikings",
    # NFC South
    "falcons": "Atlanta Falcons", "atlanta": "Atlanta Falcons", "atl": "Atlanta Falcons",
    "panthers": "Carolina Panthers", "carolina": "Carolina Panthers", "car": "Carolina Panthers",
    "saints": "New Orleans Saints", "new orleans": "New Orleans Saints", "no": "New Orleans Saints",
    "buccaneers": "Tampa Bay Buccaneers", "tampa bay": "Tampa Bay Buccaneers", "tb": "Tampa Bay Buccaneers",
    # NFC West
    "cardinals": "Arizona Cardinals", "arizona": "Arizona Cardinals", "ari": "Arizona Cardinals",
    "rams": "Los Angeles Rams", "la rams": "Los Angeles Rams", "lar": "Los Angeles Rams",
    "49ers": "San Francisco 49ers", "san francisco": "San Francisco 49ers", "sf": "San Francisco 49ers",
    "seahawks": "Seattle Seahawks", "seattle": "Seattle Seahawks", "sea": "Seattle Seahawks",
}

NBA_TEAMS = {
    # Eastern Conference - full names and city names
    "celtics": "Boston Celtics", "boston": "Boston Celtics", "boston celtics": "Boston Celtics",
    "nets": "Brooklyn Nets", "brooklyn": "Brooklyn Nets", "brooklyn nets": "Brooklyn Nets",
    "knicks": "New York Knicks", "new york knicks": "New York Knicks", "new york": "New York Knicks",
    "76ers": "Philadelphia 76ers", "sixers": "Philadelphia 76ers", "philadelphia 76ers": "Philadelphia 76ers", "philadelphia": "Philadelphia 76ers",
    "raptors": "Toronto Raptors", "toronto": "Toronto Raptors", "toronto raptors": "Toronto Raptors",
    "bulls": "Chicago Bulls", "chicago bulls": "Chicago Bulls", "chicago": "Chicago Bulls",
    "cavaliers": "Cleveland Cavaliers", "cavs": "Cleveland Cavaliers", "cleveland": "Cleveland Cavaliers", "cleveland cavaliers": "Cleveland Cavaliers",
    "pistons": "Detroit Pistons", "detroit pistons": "Detroit Pistons", "detroit": "Detroit Pistons",
    "pacers": "Indiana Pacers", "indiana": "Indiana Pacers", "indiana pacers": "Indiana Pacers",
    "bucks": "Milwaukee Bucks", "milwaukee": "Milwaukee Bucks", "milwaukee bucks": "Milwaukee Bucks",
    "hawks": "Atlanta Hawks", "atlanta hawks": "Atlanta Hawks", "atlanta": "Atlanta Hawks",
    "hornets": "Charlotte Hornets", "charlotte": "Charlotte Hornets", "charlotte hornets": "Charlotte Hornets",
    "heat": "Miami Heat", "miami heat": "Miami Heat", "miami": "Miami Heat",
    "magic": "Orlando Magic", "orlando": "Orlando Magic", "orlando magic": "Orlando Magic",
    "wizards": "Washington Wizards", "washington wizards": "Washington Wizards", "washington": "Washington Wizards",
    # Western Conference
    "nuggets": "Denver Nuggets", "denver nuggets": "Denver Nuggets", "denver": "Denver Nuggets",
    "timberwolves": "Minnesota Timberwolves", "wolves": "Minnesota Timberwolves", "minnesota timberwolves": "Minnesota Timberwolves", "minnesota": "Minnesota Timberwolves",
    "thunder": "Oklahoma City Thunder", "okc": "Oklahoma City Thunder", "oklahoma city": "Oklahoma City Thunder", "oklahoma city thunder": "Oklahoma City Thunder",
    "trail blazers": "Portland Trail Blazers", "blazers": "Portland Trail Blazers", "portland": "Portland Trail Blazers", "portland trail blazers": "Portland Trail Blazers",
    "jazz": "Utah Jazz", "utah": "Utah Jazz", "utah jazz": "Utah Jazz",
    "warriors": "Golden State Warriors", "golden state": "Golden State Warriors", "golden state warriors": "Golden State Warriors",
    "clippers": "Los Angeles Clippers", "la clippers": "Los Angeles Clippers", "los angeles clippers": "Los Angeles Clippers",
    "lakers": "Los Angeles Lakers", "la lakers": "Los Angeles Lakers", "los angeles lakers": "Los Angeles Lakers", "los angeles": "Los Angeles Lakers",
    "suns": "Phoenix Suns", "phoenix": "Phoenix Suns", "phoenix suns": "Phoenix Suns",
    "kings": "Sacramento Kings", "sacramento": "Sacramento Kings", "sacramento kings": "Sacramento Kings",
    "mavericks": "Dallas Mavericks", "mavs": "Dallas Mavericks", "dallas mavericks": "Dallas Mavericks", "dallas": "Dallas Mavericks",
    "rockets": "Houston Rockets", "houston rockets": "Houston Rockets", "houston": "Houston Rockets",
    "grizzlies": "Memphis Grizzlies", "memphis": "Memphis Grizzlies", "memphis grizzlies": "Memphis Grizzlies",
    "pelicans": "New Orleans Pelicans", "new orleans pelicans": "New Orleans Pelicans", "new orleans": "New Orleans Pelicans",
    "spurs": "San Antonio Spurs", "san antonio": "San Antonio Spurs", "san antonio spurs": "San Antonio Spurs",
}

NHL_TEAMS = {
    "bruins": "Boston Bruins", "boston bruins": "Boston Bruins",
    "sabres": "Buffalo Sabres", "buffalo sabres": "Buffalo Sabres",
    "red wings": "Detroit Red Wings", "detroit red wings": "Detroit Red Wings",
    "panthers": "Florida Panthers", "florida panthers": "Florida Panthers",
    "canadiens": "Montreal Canadiens", "montreal": "Montreal Canadiens",
    "senators": "Ottawa Senators", "ottawa": "Ottawa Senators",
    "lightning": "Tampa Bay Lightning", "tampa bay lightning": "Tampa Bay Lightning",
    "maple leafs": "Toronto Maple Leafs", "leafs": "Toronto Maple Leafs", "toronto": "Toronto Maple Leafs",
    "hurricanes": "Carolina Hurricanes", "carolina hurricanes": "Carolina Hurricanes",
    "blue jackets": "Columbus Blue Jackets", "columbus": "Columbus Blue Jackets",
    "devils": "New Jersey Devils", "new jersey": "New Jersey Devils",
    "islanders": "New York Islanders", "ny islanders": "New York Islanders",
    "rangers": "New York Rangers", "ny rangers": "New York Rangers",
    "flyers": "Philadelphia Flyers", "philadelphia flyers": "Philadelphia Flyers",
    "penguins": "Pittsburgh Penguins", "pittsburgh penguins": "Pittsburgh Penguins",
    "capitals": "Washington Capitals", "washington capitals": "Washington Capitals",
    "blackhawks": "Chicago Blackhawks", "chicago blackhawks": "Chicago Blackhawks",
    "avalanche": "Colorado Avalanche", "colorado": "Colorado Avalanche",
    "stars": "Dallas Stars", "dallas stars": "Dallas Stars",
    "wild": "Minnesota Wild", "minnesota wild": "Minnesota Wild",
    "predators": "Nashville Predators", "nashville": "Nashville Predators",
    "blues": "St. Louis Blues", "st louis": "St. Louis Blues",
    "jets": "Winnipeg Jets", "winnipeg": "Winnipeg Jets",
    "ducks": "Anaheim Ducks", "anaheim": "Anaheim Ducks",
    "flames": "Calgary Flames", "calgary": "Calgary Flames",
    "oilers": "Edmonton Oilers", "edmonton": "Edmonton Oilers",
    "kings": "Los Angeles Kings", "la kings": "Los Angeles Kings",
    "sharks": "San Jose Sharks", "san jose": "San Jose Sharks",
    "kraken": "Seattle Kraken", "seattle kraken": "Seattle Kraken",
    "canucks": "Vancouver Canucks", "vancouver": "Vancouver Canucks",
    "golden knights": "Vegas Golden Knights", "vegas": "Vegas Golden Knights",
}

# Championship name mappings
CHAMPIONSHIP_MAPPINGS = {
    # NFL
    "super bowl": "super bowl",
    "pro football championship": "super bowl",
    "nfl championship": "super bowl",
    "afc championship": "afc championship",
    "nfc championship": "nfc championship",
    "national football conference champion": "nfc championship",
    "american football conference champion": "afc championship",
    # NBA
    "nba finals": "nba finals",
    "nba championship": "nba finals",
    "basketball championship": "nba finals",
    "pro basketball finals": "nba finals",
    "pro basketball champion": "nba finals",
    # NHL
    "stanley cup": "stanley cup",
    "nhl championship": "stanley cup",
    # MLB
    "world series": "world series",
    "mlb championship": "world series",
}


class SportsMarketMatcher:
    """
    Matcher for sports markets across prediction platforms.
    
    Uses sport-specific rules for:
    1. League detection (NFL, NBA, MLB, NHL)
    2. Team name normalization
    3. Championship name mapping
    4. Season/year extraction
    5. Market type classification
    """
    
    def __init__(self, match_threshold: float = 0.70):
        self.match_threshold = match_threshold
    
    def detect_league(self, text: str) -> League:
        """Detect the sports league from market text."""
        text_lower = text.lower()
        
        # Direct league mentions
        if "nfl" in text_lower or "super bowl" in text_lower or "pro football" in text_lower:
            return League.NFL
        if "nba" in text_lower or "basketball" in text_lower:
            # Check it's not WNBA
            if "wnba" not in text_lower:
                return League.NBA
        if "mlb" in text_lower or "baseball" in text_lower or "world series" in text_lower:
            return League.MLB
        if "nhl" in text_lower or "hockey" in text_lower or "stanley cup" in text_lower:
            return League.NHL
        if "soccer" in text_lower or "premier league" in text_lower or "fifa" in text_lower:
            return League.SOCCER
        if "ufc" in text_lower or "mma" in text_lower:
            return League.UFC
        if "pga" in text_lower or "golf" in text_lower or "masters" in text_lower:
            return League.GOLF
        if "tennis" in text_lower or "wimbledon" in text_lower or "us open" in text_lower:
            return League.TENNIS
        
        # Check for team names
        for team in NFL_TEAMS.keys():
            if team in text_lower:
                return League.NFL
        for team in NBA_TEAMS.keys():
            if team in text_lower:
                return League.NBA
        for team in NHL_TEAMS.keys():
            if team in text_lower:
                return League.NHL
        
        return League.UNKNOWN
    
    def detect_market_type(self, text: str, ticker: str = "", slug: str = "") -> MarketType:
        """Detect the type of sports market."""
        text_lower = text.lower()
        ticker_lower = ticker.lower()
        slug_lower = slug.lower()
        
        # SPREAD MARKETS - Check FIRST to avoid misclassifying as game winner
        # Polymarket: "Spread: Lakers (-9.5)", "Spread: Oilers (-1.5)"
        # Also check for spread patterns without the "Spread:" prefix
        spread_indicators = [
            "spread:" in text_lower,
            "spread" in slug_lower,
            bool(re.search(r'\(\-?\d+\.?\d*\)', text_lower)),  # e.g., (-9.5), (+3), (-1.5)
            " -" in text_lower and ".5)" in text_lower,  # Lakers -9.5
            "handicap" in text_lower,
        ]
        if any(spread_indicators):
            return MarketType.SPREAD
        
        # OVER/UNDER MARKETS - Check before game winner
        # Polymarket: "Jazz vs. Cavaliers: O/U 250.5", "Over/Under 48.5"
        over_under_indicators = [
            "o/u" in text_lower,
            "over/under" in text_lower,
            "over under" in text_lower,
            "total points" in text_lower,
            "total goals" in text_lower,
            bool(re.search(r'\b(over|under)\s*\d+\.?\d*\b', text_lower)),  # over 250.5, under 48
        ]
        if any(over_under_indicators):
            return MarketType.OVER_UNDER
        
        # SINGLE GAME (MONEYLINE) MARKETS - Who wins the game outright
        # Polymarket slugs: nba-uta-cle-2026-01-12, nfl-hou-pit-2026-01-12
        # Kalshi tickers: KXNBAGAME-26JAN12UTACLE, KXNFLGAME-26JAN12HOUPIT
        single_game_indicators = [
            "game" in ticker_lower and any(sport in ticker_lower for sport in ["nba", "nfl", "nhl", "mlb", "ncaa", "wnba"]),
            any(slug_lower.startswith(f"{sport}-") and len(slug_lower.split("-")) >= 4 for sport in ["nba", "nfl", "nhl", "mlb", "cbb", "cfb", "wnba"]),
            " vs " in text_lower or " vs. " in text_lower or " at " in text_lower,
        ]
        
        # Single game detection - check text patterns
        if any(single_game_indicators):
            # Make sure it's not a championship or award market
            futures_keywords = ["champion", "mvp", "rookie", "award", "super bowl", "finals", "stanley cup", "world series"]
            if not any(kw in text_lower for kw in futures_keywords):
                return MarketType.GAME_WINNER
        
        # MVP - MUST distinguish between season MVP and championship game MVP
        if "mvp" in text_lower or "sbmvp" in ticker_lower:
            # Championship game MVP indicators (Super Bowl MVP, Finals MVP, etc.)
            game_mvp_indicators = [
                "championship game mvp",
                "pro football championship game mvp",
                "super bowl mvp",
                "finals mvp",
                "nba finals mvp",
                "world series mvp",
                "stanley cup mvp",
                "sbmvp",  # Kalshi ticker pattern for Super Bowl MVP
            ]
            
            # Check for championship game MVP
            if any(ind in text_lower for ind in game_mvp_indicators) or "sbmvp" in ticker_lower:
                return MarketType.MVP_GAME
            
            # Season/regular MVP indicators (NFL MVP award, NBA MVP, etc.)
            season_mvp_indicators = [
                "nfl mvp award",
                "nfl mvp",
                "nba mvp award", 
                "nba mvp",
                "mlb mvp",
                "nhl mvp",
                "mvp award",
                "regular season mvp",
                "season mvp",
            ]
            
            if any(ind in text_lower for ind in season_mvp_indicators):
                return MarketType.MVP_SEASON
            
            # Default MVP to season if not clearly a game MVP
            logger.warning(f"Ambiguous MVP market detected, defaulting to season: {text[:80]}")
            return MarketType.MVP_SEASON
        
        # Championships
        if any(champ in text_lower for champ in ["super bowl", "nba finals", "stanley cup", "world series", "championship"]):
            if "win" in text_lower:
                return MarketType.CHAMPIONSHIP
        
        # Divisions/Conferences
        if any(div in text_lower for div in ["afc", "nfc", "division", "conference"]):
            return MarketType.DIVISION
        
        # Player awards
        if any(award in text_lower for award in ["rookie of the year", "roty", "dpoy", "defensive player"]):
            return MarketType.PLAYER_AWARD
        
        # Parlays (Kalshi MVE markets)
        if "mve" in ticker_lower or "multigame" in ticker_lower:
            return MarketType.PARLAY
        
        # Player props - check for prop market patterns
        player_prop_patterns = [
            "points over", "points under", "rebounds over", "assists over",
            "yards over", "yards under", "touchdowns over", "receptions over",
            "o/u", "spread:", "1h spread", "1h moneyline",
        ]
        if any(pattern in text_lower for pattern in player_prop_patterns):
            return MarketType.PLAYER_PROP
        
        # Season wins
        if "wins" in text_lower and any(w in text_lower for w in ["season", "regular", "total"]):
            return MarketType.SEASON_WINS
        
        return MarketType.UNKNOWN
    
    def extract_team(self, text: str, league: League) -> Optional[str]:
        """Extract and normalize team name from text."""
        text_lower = text.lower()
        
        team_dict = {
            League.NFL: NFL_TEAMS,
            League.NBA: NBA_TEAMS,
            League.NHL: NHL_TEAMS,
        }.get(league, {})
        
        if not team_dict:
            return None
        
        # Sort aliases by length (longest first) to match full team names before abbreviations
        sorted_aliases = sorted(team_dict.keys(), key=len, reverse=True)
        
        for alias in sorted_aliases:
            # Use word boundary matching to avoid partial matches
            # e.g., "indiana" should not match in "Indiana University"
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower):
                canonical = team_dict[alias]
                # Verify this isn't a college team (check for common college keywords)
                college_keywords = ['college', 'university', 'ncaa', 'ncaaf', 'state']
                if any(kw in text_lower for kw in college_keywords):
                    # Skip if this looks like a college market
                    continue
                return canonical
        
        return None
    
    def extract_year(self, text: str) -> Optional[int]:
        """Extract year from market text."""
        # Match patterns like "2026", "2025-26", "25-26"
        patterns = [
            r'\b(20\d{2})\b',  # Full year: 2026
            r'\b(20\d{2})-\d{2}\b',  # Season format: 2025-26
            r"'(\d{2})",  # Short year: '26
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                year = match.group(1)
                if len(year) == 2:
                    year = "20" + year
                return int(year)
        
        return None
    
    def normalize_championship(self, text: str) -> Optional[str]:
        """Normalize championship name."""
        text_lower = text.lower()
        
        for alias, canonical in CHAMPIONSHIP_MAPPINGS.items():
            if alias in text_lower:
                return canonical
        
        return None
    
    def extract_teams_from_matchup(self, text: str, ticker: str = "", slug: str = "") -> Tuple[Optional[str], Optional[str]]:
        """
        Extract both teams from a single-game matchup.
        
        Handles formats:
        - "Jazz vs. Cavaliers" -> (Utah Jazz, Cleveland Cavaliers)
        - "Utah at Cleveland" -> (Cleveland Cavaliers, Utah Jazz) - home team first
        - Ticker: KXNBAGAME-26JAN12UTACLE -> teams from abbrevs
        - Slug: nba-uta-cle-2026-01-12 -> teams from abbrevs
        
        Returns (home_team, away_team) tuple.
        """
        text_lower = text.lower()
        
        # Sport-specific team abbreviation mappings
        # IMPORTANT: Must use separate dicts per sport to avoid conflicts like "HOU"
        # (Houston Rockets in NBA vs Houston Texans in NFL)
        NBA_ABBREVS = {
            "atl": "Atlanta Hawks", "bos": "Boston Celtics", "bkn": "Brooklyn Nets", "bk": "Brooklyn Nets",
            "cha": "Charlotte Hornets", "chi": "Chicago Bulls", "cle": "Cleveland Cavaliers",
            "dal": "Dallas Mavericks", "den": "Denver Nuggets", "det": "Detroit Pistons",
            "gsw": "Golden State Warriors", "gs": "Golden State Warriors", "hou": "Houston Rockets",
            "ind": "Indiana Pacers", "lac": "Los Angeles Clippers", "lal": "Los Angeles Lakers",
            "mem": "Memphis Grizzlies", "mia": "Miami Heat", "mil": "Milwaukee Bucks",
            "min": "Minnesota Timberwolves", "nop": "New Orleans Pelicans", "nyk": "New York Knicks",
            "okc": "Oklahoma City Thunder", "orl": "Orlando Magic", "phi": "Philadelphia 76ers",
            "phx": "Phoenix Suns", "por": "Portland Trail Blazers", "sac": "Sacramento Kings",
            "sas": "San Antonio Spurs", "tor": "Toronto Raptors", "uta": "Utah Jazz",
            "was": "Washington Wizards",
        }
        
        NFL_ABBREVS = {
            "ari": "Arizona Cardinals", "bal": "Baltimore Ravens", "buf": "Buffalo Bills",
            "car": "Carolina Panthers", "cin": "Cincinnati Bengals", "dal": "Dallas Cowboys",
            "den": "Denver Broncos", "det": "Detroit Lions", "gb": "Green Bay Packers",
            "hou": "Houston Texans", "ind": "Indianapolis Colts", "jax": "Jacksonville Jaguars",
            "kc": "Kansas City Chiefs", "lv": "Las Vegas Raiders", "lar": "Los Angeles Rams",
            "lac": "Los Angeles Chargers", "mia": "Miami Dolphins", "min": "Minnesota Vikings",
            "ne": "New England Patriots", "no": "New Orleans Saints", "nyg": "New York Giants",
            "nyj": "New York Jets", "phi": "Philadelphia Eagles", "pit": "Pittsburgh Steelers",
            "sf": "San Francisco 49ers", "sea": "Seattle Seahawks", "tb": "Tampa Bay Buccaneers",
            "ten": "Tennessee Titans", "was": "Washington Commanders",
        }
        
        NHL_ABBREVS = {
            "ana": "Anaheim Ducks", "bos": "Boston Bruins", "buf": "Buffalo Sabres",
            "cgy": "Calgary Flames", "car": "Carolina Hurricanes", "chi": "Chicago Blackhawks",
            "col": "Colorado Avalanche", "cbj": "Columbus Blue Jackets", "dal": "Dallas Stars",
            "det": "Detroit Red Wings", "edm": "Edmonton Oilers", "fla": "Florida Panthers",
            "la": "Los Angeles Kings", "lak": "Los Angeles Kings", "min": "Minnesota Wild",
            "mtl": "Montreal Canadiens", "nsh": "Nashville Predators", "njd": "New Jersey Devils",
            "nj": "New Jersey Devils", "nyi": "New York Islanders", "nyr": "New York Rangers",
            "ott": "Ottawa Senators", "phi": "Philadelphia Flyers", "pit": "Pittsburgh Penguins",
            "sjs": "San Jose Sharks", "sea": "Seattle Kraken", "stl": "St. Louis Blues",
            "tbl": "Tampa Bay Lightning", "tor": "Toronto Maple Leafs", "van": "Vancouver Canucks",
            "vgk": "Vegas Golden Knights", "wpg": "Winnipeg Jets", "wsh": "Washington Capitals",
        }
        
        MLB_ABBREVS = {
            "bal": "Baltimore Orioles", "bos": "Boston Red Sox", "nyy": "New York Yankees",
            "tb": "Tampa Bay Rays", "tor": "Toronto Blue Jays", "cws": "Chicago White Sox",
            "cle": "Cleveland Guardians", "det": "Detroit Tigers", "kc": "Kansas City Royals",
            "min": "Minnesota Twins", "hou": "Houston Astros", "laa": "LA Angels",
            "oak": "Oakland Athletics", "sea": "Seattle Mariners", "tex": "Texas Rangers",
            "atl": "Atlanta Braves", "mia": "Miami Marlins", "nym": "New York Mets",
            "phi": "Philadelphia Phillies", "wsh": "Washington Nationals", "chc": "Chicago Cubs",
            "cin": "Cincinnati Reds", "mil": "Milwaukee Brewers", "pit": "Pittsburgh Pirates",
            "stl": "St. Louis Cardinals", "ari": "Arizona Diamondbacks", "col": "Colorado Rockies",
            "lad": "LA Dodgers", "sd": "San Diego Padres", "sf": "San Francisco Giants",
        }
        
        # Detect sport from slug, ticker, or text to use correct team mapping
        sport = None
        combined = f"{slug} {ticker} {text}".lower()
        if "nba" in combined or "kxnbagame" in combined:
            sport = "nba"
        elif "nfl" in combined or "kxnflgame" in combined:
            sport = "nfl"
        elif "nhl" in combined or "kxnhlgame" in combined:
            sport = "nhl"
        elif "mlb" in combined or "kxmlbgame" in combined:
            sport = "mlb"
        
        # Select the appropriate team map based on detected sport
        if sport == "nba":
            TEAM_ABBREVS = NBA_ABBREVS
        elif sport == "nfl":
            TEAM_ABBREVS = NFL_ABBREVS
        elif sport == "nhl":
            TEAM_ABBREVS = NHL_ABBREVS
        elif sport == "mlb":
            TEAM_ABBREVS = MLB_ABBREVS
        else:
            # Fallback: NBA first, then check others (maintain original behavior for unknown sports)
            TEAM_ABBREVS = {**NHL_ABBREVS, **MLB_ABBREVS, **NFL_ABBREVS, **NBA_ABBREVS}  # NBA last = highest priority
        
        home_team = None
        away_team = None
        
        # Try to extract from Polymarket slug first (most reliable): nba-uta-cle-2026-01-12
        if slug:
            parts = slug.lower().split("-")
            if len(parts) >= 4:
                # Format: sport-away-home-date (away team travels to home)
                away_abbr = parts[1]
                home_abbr = parts[2]
                if away_abbr in TEAM_ABBREVS:
                    away_team = TEAM_ABBREVS[away_abbr]
                if home_abbr in TEAM_ABBREVS:
                    home_team = TEAM_ABBREVS[home_abbr]
        
        # Try Kalshi ticker: KXNBAGAME-26JAN12UTACLE (last part has team abbrevs)
        if ticker and not (home_team and away_team):
            ticker_upper = ticker.upper()
            # Extract last part after date: e.g., UTACLE from KXNBAGAME-26JAN12UTACLE
            parts = ticker_upper.split("-")
            for part in parts:
                # Look for team codes at end of date part (e.g., JAN12UTACLE)
                match = re.search(r'\d{2}([A-Z]{3})([A-Z]{2,3})$', part)
                if match:
                    away_abbr = match.group(1).lower()
                    home_abbr = match.group(2).lower()
                    if away_abbr in TEAM_ABBREVS:
                        away_team = TEAM_ABBREVS[away_abbr]
                    if home_abbr in TEAM_ABBREVS:
                        home_team = TEAM_ABBREVS[home_abbr]
        
        # Try text parsing: "Jazz vs. Cavaliers" or "Utah at Cleveland"
        if not (home_team and away_team):
            # "Team1 vs Team2" pattern - first team listed is often away
            vs_match = re.search(r'([a-z\s]+?)\s+(?:vs\.?|versus)\s+([a-z\s]+)', text_lower)
            at_match = re.search(r'([a-z\s]+?)\s+at\s+([a-z\s]+)', text_lower)
            
            if at_match:
                # "Team1 at Team2" - Team1 is away, Team2 is home
                away_text = at_match.group(1).strip()
                home_text = at_match.group(2).strip()
            elif vs_match:
                # "Team1 vs Team2" - assume first is away (road team listed first)
                away_text = vs_match.group(1).strip()
                home_text = vs_match.group(2).strip()
            else:
                away_text = home_text = ""
            
            if away_text and home_text:
                # Try to normalize team names
                for team_dict in [NBA_TEAMS, NFL_TEAMS, NHL_TEAMS]:
                    if away_text in team_dict and not away_team:
                        away_team = team_dict[away_text]
                    if home_text in team_dict and not home_team:
                        home_team = team_dict[home_text]
        
        return home_team, away_team
    
    def extract_game_date(self, slug: str = "", ticker: str = "", end_date: str = "") -> Optional[str]:
        """
        Extract game date from market data.
        
        Handles:
        - Slug: nba-uta-cle-2026-01-12 -> 2026-01-12
        - Ticker: KXNBAGAME-26JAN12UTACLE -> 2026-01-12
        - End date from market data
        
        Returns date string in YYYY-MM-DD format.
        """
        # Try slug first: nba-uta-cle-2026-01-12
        if slug:
            match = re.search(r'(\d{4}-\d{2}-\d{2})', slug)
            if match:
                return match.group(1)
        
        # Try ticker: KXNBAGAME-26JAN12UTACLE
        if ticker:
            match = re.search(r'(\d{2})([A-Z]{3})(\d{1,2})', ticker.upper())
            if match:
                year_short = match.group(1)
                month_abbr = match.group(2)
                day = match.group(3)
                
                month_map = {
                    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
                    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
                    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
                }
                
                if month_abbr in month_map:
                    month = month_map[month_abbr]
                    year = f"20{year_short}"
                    return f"{year}-{month}-{day.zfill(2)}"
        
        # Try end_date
        if end_date:
            match = re.search(r'(\d{4}-\d{2}-\d{2})', end_date)
            if match:
                return match.group(1)
        
        return None

    def extract_market_info(self, market: Any, platform: str) -> SportsMarketInfo:
        """Extract structured information from a market."""
        if platform == "polymarket":
            question = market.question
            ticker = ""
            slug = market.slug if hasattr(market, 'slug') else ""
            end_date = market.end_date.isoformat() if market.end_date else ""
        else:
            question = market.question or market.title
            ticker = market.ticker
            slug = ""
            end_date = market.expected_expiration_time.isoformat() if market.expected_expiration_time else ""
        
        league = self.detect_league(question + " " + ticker)
        market_type = self.detect_market_type(question, ticker, slug)
        year = self.extract_year(question + " " + ticker)
        championship = self.normalize_championship(question)
        
        # Initialize team fields
        team = None
        away_team = None
        game_date = None
        
        # Handle single-game markets differently
        if market_type == MarketType.GAME_WINNER:
            home_team, away_team = self.extract_teams_from_matchup(question, ticker, slug)
            team = home_team  # Primary team is home team
            game_date = self.extract_game_date(slug, ticker, end_date)
        else:
            # For futures, extract single team
            team = self.extract_team(question, league)
            # For Kalshi, try to extract team from ticker if not found in question
            if platform == "kalshi" and not team and ticker:
                team = self.extract_team_from_ticker(ticker, league)
        
        # Extract player name (for MVP/award markets)
        player = None
        if market_type in [MarketType.MVP_SEASON, MarketType.MVP_GAME, MarketType.PLAYER_AWARD, MarketType.PLAYER_PROP]:
            # Try to extract player name from Kalshi format: "Will [Player Name] win..."
            match = re.search(r'will\s+([a-z\s]+)\s+win', question.lower())
            if match:
                player = match.group(1).strip().title()
        
        return SportsMarketInfo(
            league=league,
            market_type=market_type,
            team=team,
            away_team=away_team,
            player=player,
            championship=championship,
            season=f"{year-1}-{str(year)[2:]}" if year else None,
            year=year,
            game_date=game_date,
            raw_question=question
        )
    
    def extract_team_from_ticker(self, ticker: str, league: League) -> Optional[str]:
        """
        Extract team from Kalshi ticker format.
        
        Kalshi tickers often end with team abbreviations:
        - KXNFLAFCCHAMP-25-TEN → Tennessee Titans
        - KXNBA-26-OKC → Oklahoma City Thunder
        """
        # Map abbreviations to full team names
        NFL_ABBREVS = {
            "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
            "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
            "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
            "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
            "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
            "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
            "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
            "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
            "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
            "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
            "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
        }
        
        NBA_ABBREVS = {
            "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
            "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
            "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
            "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
            "LAC": "Los Angeles Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
            "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
            "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
            "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
            "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
            "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
        }
        
        NHL_ABBREVS = {
            "ANA": "Anaheim Ducks", "BOS": "Boston Bruins", "BUF": "Buffalo Sabres",
            "CAR": "Carolina Hurricanes", "CBJ": "Columbus Blue Jackets", "CGY": "Calgary Flames",
            "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche", "DAL": "Dallas Stars",
            "DET": "Detroit Red Wings", "EDM": "Edmonton Oilers", "FLA": "Florida Panthers",
            "LAK": "Los Angeles Kings", "MIN": "Minnesota Wild", "MTL": "Montreal Canadiens",
            "NJD": "New Jersey Devils", "NSH": "Nashville Predators", "NYI": "New York Islanders",
            "NYR": "New York Rangers", "OTT": "Ottawa Senators", "PHI": "Philadelphia Flyers",
            "PIT": "Pittsburgh Penguins", "SEA": "Seattle Kraken", "SJS": "San Jose Sharks",
            "STL": "St. Louis Blues", "TBL": "Tampa Bay Lightning", "TOR": "Toronto Maple Leafs",
            "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights", "WPG": "Winnipeg Jets",
            "WSH": "Washington Capitals",
        }
        
        abbrev_map = {
            League.NFL: NFL_ABBREVS,
            League.NBA: NBA_ABBREVS,
            League.NHL: NHL_ABBREVS,
        }.get(league, {})
        
        # Extract last part of ticker (usually team abbrev)
        parts = ticker.upper().split("-")
        for part in reversed(parts):
            if part in abbrev_map:
                team = abbrev_map[part]
                logger.info(f"Ticker {ticker} -> Team: {team}")
                return team
        
        return None
    
    def calculate_match_score(
        self,
        poly_info: SportsMarketInfo,
        kalshi_info: SportsMarketInfo
    ) -> Tuple[float, str]:
        """
        Calculate match score between two sports markets.
        
        Returns (score, reason) tuple.
        """
        # Must be same league
        if poly_info.league != kalshi_info.league:
            return 0.0, "league_mismatch"
        
        if poly_info.league == League.UNKNOWN:
            return 0.0, "unknown_league"
        
        # Must be same market type (or compatible types)
        if poly_info.market_type != kalshi_info.market_type:
            return 0.0, "market_type_mismatch"
        
        score = 0.0
        
        # SINGLE GAME MARKETS - Match on both teams + date
        if poly_info.market_type == MarketType.GAME_WINNER:
            # Need at least one team from each market
            poly_teams = {poly_info.team, poly_info.away_team} - {None}
            kalshi_teams = {kalshi_info.team, kalshi_info.away_team} - {None}
            
            if len(poly_teams) < 2 or len(kalshi_teams) < 2:
                return 0.0, "missing_teams"
            
            # Both teams must match
            if poly_teams == kalshi_teams:
                score += 0.6
                logger.info(f"GAME MATCH FOUND: {poly_teams}")
                logger.info(f"  Poly: {poly_info.raw_question[:70]}")
                logger.info(f"  Kalshi: {kalshi_info.raw_question[:70]}")
            else:
                return 0.0, "teams_mismatch"
            
            # Date should match (important for same teams playing multiple times)
            if poly_info.game_date and kalshi_info.game_date:
                if poly_info.game_date == kalshi_info.game_date:
                    score += 0.4
                else:
                    # Different dates = different games
                    return 0.0, "date_mismatch"
            elif poly_info.game_date or kalshi_info.game_date:
                # Only one has date - accept but lower score
                score += 0.2
            
            return score, "game_winner_match"
        
        # Championship markets: match on team + championship + year
        if poly_info.market_type == MarketType.CHAMPIONSHIP:
            # REQUIRE both teams to be present for championship markets
            if not poly_info.team or not kalshi_info.team:
                return 0.0, "missing_team"
            
            # Log the comparison with full details
            logger.debug(f"Comparing: poly_team={poly_info.team} vs kalshi_team={kalshi_info.team}")
            
            # STRICT team match required
            if poly_info.team == kalshi_info.team:
                score += 0.5
                logger.info(f"TEAM MATCH FOUND: {poly_info.team}")
                logger.info(f"  Poly: {poly_info.raw_question[:70]}")
                logger.info(f"  Kalshi: {kalshi_info.raw_question[:70]}")
            else:
                return 0.0, "team_mismatch"
            
            if poly_info.championship and kalshi_info.championship:
                if poly_info.championship == kalshi_info.championship:
                    score += 0.3
                else:
                    return 0.0, "championship_mismatch"
            
            if poly_info.year and kalshi_info.year:
                if poly_info.year == kalshi_info.year:
                    score += 0.2
                elif abs(poly_info.year - kalshi_info.year) == 1:
                    score += 0.1  # Adjacent years (season boundary)
            
            return score, "championship_match"
        
        # MVP markets: match on player + year
        # IMPORTANT: MVP_SEASON and MVP_GAME are different and should NOT match each other
        if poly_info.market_type in [MarketType.MVP_SEASON, MarketType.MVP_GAME]:
            # Log the MVP types for debugging
            logger.debug(
                f"MVP comparison: poly={poly_info.market_type.value}, kalshi={kalshi_info.market_type.value} "
                f"| poly_q={poly_info.raw_question[:50]}... | kalshi_q={kalshi_info.raw_question[:50]}..."
            )
            
            if poly_info.player and kalshi_info.player:
                # Fuzzy player name matching
                if poly_info.player.lower() == kalshi_info.player.lower():
                    score += 0.6
                elif poly_info.player.lower() in kalshi_info.player.lower() or kalshi_info.player.lower() in poly_info.player.lower():
                    score += 0.4
                else:
                    return 0.0, "player_mismatch"
            
            if poly_info.year and kalshi_info.year:
                if poly_info.year == kalshi_info.year:
                    score += 0.4
            
            mvp_type = "season" if poly_info.market_type == MarketType.MVP_SEASON else "game"
            return score, f"mvp_{mvp_type}_match"
        
        # Division/Conference markets
        if poly_info.market_type == MarketType.DIVISION:
            if poly_info.team and kalshi_info.team:
                if poly_info.team == kalshi_info.team:
                    score += 0.7
                else:
                    return 0.0, "team_mismatch"
            
            if poly_info.year and kalshi_info.year:
                if poly_info.year == kalshi_info.year:
                    score += 0.3
            
            return score, "division_match"
        
        return 0.0, "unsupported_market_type"
    
    def match_markets(
        self,
        polymarket_markets: List[PolymarketMarket],
        kalshi_markets: List[KalshiMarket]
    ) -> List[Dict[str, Any]]:
        """
        Match sports markets between platforms.
        
        Returns list of matched market pairs with scores.
        """
        matches = []
        used_kalshi = set()
        
        # Pre-process Polymarket markets - categorize by type
        poly_games = []  # Single-game markets
        poly_futures = []  # Futures/awards markets
        
        for m in polymarket_markets:
            info = self.extract_market_info(m, "polymarket")
            if info.league != League.UNKNOWN and info.market_type != MarketType.UNKNOWN:
                if info.market_type == MarketType.GAME_WINNER:
                    poly_games.append((m, info))
                elif info.market_type not in [MarketType.PLAYER_PROP]:
                    poly_futures.append((m, info))
        
        # Pre-process Kalshi markets - categorize by type
        kalshi_games = []  # Single-game markets
        kalshi_futures = []  # Futures/awards markets
        
        for m in kalshi_markets:
            info = self.extract_market_info(m, "kalshi")
            if info.league != League.UNKNOWN and info.market_type != MarketType.UNKNOWN:
                # Skip parlay/MVE markets as they don't match Polymarket structure
                if info.market_type == MarketType.GAME_WINNER:
                    kalshi_games.append((m, info))
                elif info.market_type not in [MarketType.PARLAY, MarketType.PLAYER_PROP]:
                    kalshi_futures.append((m, info))
        
        logger.info(
            f"Polymarket: {len(poly_games)} single-game, {len(poly_futures)} futures | "
            f"Kalshi: {len(kalshi_games)} single-game, {len(kalshi_futures)} futures"
        )
        
        # Match single-game markets first (higher priority for arbitrage)
        for poly_market, poly_info in poly_games:
            best_match = None
            best_score = 0
            best_reason = ""
            
            for kalshi_market, kalshi_info in kalshi_games:
                if kalshi_market.ticker in used_kalshi:
                    continue
                
                score, reason = self.calculate_match_score(poly_info, kalshi_info)
                
                if score > best_score and score >= self.match_threshold:
                    best_score = score
                    best_match = kalshi_market
                    best_reason = reason
            
            if best_match:
                matches.append({
                    "polymarket": poly_market,
                    "kalshi": best_match,
                    "poly_info": poly_info,
                    "kalshi_info": self.extract_market_info(best_match, "kalshi"),
                    "score": best_score,
                    "match_reason": best_reason,
                    "market_category": "single_game"
                })
                used_kalshi.add(best_match.ticker)
        
        # Match futures markets
        for poly_market, poly_info in poly_futures:
            best_match = None
            best_score = 0
            best_reason = ""
            
            for kalshi_market, kalshi_info in kalshi_futures:
                if kalshi_market.ticker in used_kalshi:
                    continue
                
                score, reason = self.calculate_match_score(poly_info, kalshi_info)
                
                if score > best_score and score >= self.match_threshold:
                    best_score = score
                    best_match = kalshi_market
                    best_reason = reason
            
            if best_match:
                matches.append({
                    "polymarket": poly_market,
                    "kalshi": best_match,
                    "poly_info": poly_info,
                    "kalshi_info": self.extract_market_info(best_match, "kalshi"),
                    "score": best_score,
                    "match_reason": best_reason,
                    "market_category": "futures"
                })
                used_kalshi.add(best_match.ticker)
        
        game_matches = sum(1 for m in matches if m.get("market_category") == "single_game")
        futures_matches = sum(1 for m in matches if m.get("market_category") == "futures")
        logger.info(f"Found {len(matches)} matches: {game_matches} single-game, {futures_matches} futures")
        return matches


def get_sports_matcher(match_threshold: float = 0.70) -> SportsMarketMatcher:
    """Factory function for sports matcher."""
    return SportsMarketMatcher(match_threshold)

