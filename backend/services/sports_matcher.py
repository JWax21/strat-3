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
    GAME_WINNER = "game_winner"  # Single game outcomes
    PLAYER_PROP = "player_prop"  # Player stats in a game
    SEASON_WINS = "season_wins"  # Win totals
    PARLAY = "parlay"  # Multi-leg bets
    UNKNOWN = "unknown"


@dataclass
class SportsMarketInfo:
    """Extracted information from a sports market."""
    league: League
    market_type: MarketType
    team: Optional[str]
    player: Optional[str]
    championship: Optional[str]
    season: Optional[str]
    year: Optional[int]
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
    
    def detect_market_type(self, text: str, ticker: str = "") -> MarketType:
        """Detect the type of sports market."""
        text_lower = text.lower()
        ticker_lower = ticker.lower()
        
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
            # But be cautious - log for investigation
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
        if "mve" in ticker_lower or "multigame" in ticker_lower or "singlegame" in ticker_lower:
            return MarketType.PARLAY
        
        # Player props
        if ":" in text_lower or "yards" in text_lower or "points" in text_lower or "receptions" in text_lower:
            return MarketType.PLAYER_PROP
        
        # Season wins
        if "wins" in text_lower and any(w in text_lower for w in ["season", "regular", "total"]):
            return MarketType.SEASON_WINS
        
        # Single game
        if "game" in text_lower or "match" in text_lower:
            return MarketType.GAME_WINNER
        
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
    
    def extract_market_info(self, market: Any, platform: str) -> SportsMarketInfo:
        """Extract structured information from a market."""
        if platform == "polymarket":
            question = market.question
            ticker = ""
        else:
            question = market.question or market.title
            ticker = market.ticker
        
        league = self.detect_league(question + " " + ticker)
        market_type = self.detect_market_type(question, ticker)
        team = self.extract_team(question, league)
        year = self.extract_year(question + " " + ticker)
        championship = self.normalize_championship(question)
        
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
            player=player,
            championship=championship,
            season=f"{year-1}-{str(year)[2:]}" if year else None,
            year=year,
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
        
        # Pre-process Polymarket markets
        poly_sports = []
        for m in polymarket_markets:
            info = self.extract_market_info(m, "polymarket")
            if info.league != League.UNKNOWN and info.market_type != MarketType.UNKNOWN:
                poly_sports.append((m, info))
        
        # Pre-process Kalshi markets
        kalshi_sports = []
        for m in kalshi_markets:
            info = self.extract_market_info(m, "kalshi")
            if info.league != League.UNKNOWN and info.market_type != MarketType.UNKNOWN:
                # Skip parlay/MVE markets as they don't match Polymarket structure
                if info.market_type not in [MarketType.PARLAY, MarketType.PLAYER_PROP]:
                    kalshi_sports.append((m, info))
        
        logger.info(
            f"Found {len(poly_sports)} Polymarket and {len(kalshi_sports)} Kalshi "
            f"sports markets (excluding parlays)"
        )
        
        # Match markets
        for poly_market, poly_info in poly_sports:
            best_match = None
            best_score = 0
            best_reason = ""
            
            for kalshi_market, kalshi_info in kalshi_sports:
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
                    "match_reason": best_reason
                })
                used_kalshi.add(best_match.ticker)
        
        logger.info(f"Found {len(matches)} sports market matches")
        return matches


def get_sports_matcher(match_threshold: float = 0.70) -> SportsMarketMatcher:
    """Factory function for sports matcher."""
    return SportsMarketMatcher(match_threshold)

