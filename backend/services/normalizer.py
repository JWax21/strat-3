"""
Market Normalization Service

Comprehensive mappings for normalizing team names, player names, and market 
titles between Polymarket and Kalshi.

This module provides the canonical "source of truth" for matching equivalent
entities across platforms.
"""
import re
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Sport(Enum):
    """Supported sports/leagues."""
    NBA = "nba"
    NFL = "nfl"
    NHL = "nhl"
    MLB = "mlb"
    WNBA = "wnba"
    NCAA_MBB = "ncaa_mbb"   # College Men's Basketball
    NCAA_WBB = "ncaa_wbb"   # College Women's Basketball  
    NCAA_FB = "ncaa_fb"    # College Football
    EUROLEAGUE = "euroleague"
    NBL = "nbl"            # Australian Basketball
    UFC = "ufc"
    TENNIS = "tennis"
    GOLF = "golf"
    F1 = "f1"
    NASCAR = "nascar"
    INDYCAR = "indycar"
    CRICKET = "cricket"
    CHESS = "chess"
    ESPORTS = "esports"
    UNKNOWN = "unknown"


# =============================================================================
# NBA TEAM NORMALIZATION
# Maps all variations to canonical "City Mascot" format
# =============================================================================
NBA_TEAMS: Dict[str, str] = {
    # Atlanta Hawks
    "atl": "Atlanta Hawks", "atlanta": "Atlanta Hawks", "hawks": "Atlanta Hawks",
    "atlanta hawks": "Atlanta Hawks",
    
    # Boston Celtics
    "bos": "Boston Celtics", "boston": "Boston Celtics", "celtics": "Boston Celtics",
    "boston celtics": "Boston Celtics",
    
    # Brooklyn Nets
    "bkn": "Brooklyn Nets", "bk": "Brooklyn Nets", "brooklyn": "Brooklyn Nets",
    "nets": "Brooklyn Nets", "brooklyn nets": "Brooklyn Nets",
    
    # Charlotte Hornets
    "cha": "Charlotte Hornets", "charlotte": "Charlotte Hornets", "hornets": "Charlotte Hornets",
    "charlotte hornets": "Charlotte Hornets",
    
    # Chicago Bulls
    "chi": "Chicago Bulls", "chicago bulls": "Chicago Bulls", "bulls": "Chicago Bulls",
    
    # Cleveland Cavaliers
    "cle": "Cleveland Cavaliers", "cleveland": "Cleveland Cavaliers", 
    "cavaliers": "Cleveland Cavaliers", "cavs": "Cleveland Cavaliers",
    "cleveland cavaliers": "Cleveland Cavaliers",
    
    # Dallas Mavericks
    "dal": "Dallas Mavericks", "dallas": "Dallas Mavericks", "mavericks": "Dallas Mavericks",
    "mavs": "Dallas Mavericks", "dallas mavericks": "Dallas Mavericks",
    
    # Denver Nuggets
    "den": "Denver Nuggets", "denver": "Denver Nuggets", "nuggets": "Denver Nuggets",
    "denver nuggets": "Denver Nuggets",
    
    # Detroit Pistons
    "det": "Detroit Pistons", "detroit": "Detroit Pistons", "pistons": "Detroit Pistons",
    "detroit pistons": "Detroit Pistons",
    
    # Golden State Warriors
    "gsw": "Golden State Warriors", "gs": "Golden State Warriors", 
    "golden state": "Golden State Warriors", "warriors": "Golden State Warriors",
    "golden state warriors": "Golden State Warriors",
    
    # Houston Rockets
    "hou": "Houston Rockets", "houston": "Houston Rockets", "rockets": "Houston Rockets",
    "houston rockets": "Houston Rockets",
    
    # Indiana Pacers
    "ind": "Indiana Pacers", "indiana": "Indiana Pacers", "pacers": "Indiana Pacers",
    "indiana pacers": "Indiana Pacers",
    
    # Los Angeles Clippers
    "lac": "LA Clippers", "la clippers": "LA Clippers", "clippers": "LA Clippers",
    "los angeles clippers": "LA Clippers",
    
    # Los Angeles Lakers
    "lal": "LA Lakers", "la lakers": "LA Lakers", "lakers": "LA Lakers",
    "los angeles lakers": "LA Lakers",
    
    # Memphis Grizzlies
    "mem": "Memphis Grizzlies", "memphis": "Memphis Grizzlies", "grizzlies": "Memphis Grizzlies",
    "memphis grizzlies": "Memphis Grizzlies",
    
    # Miami Heat
    "mia": "Miami Heat", "miami": "Miami Heat", "heat": "Miami Heat",
    "miami heat": "Miami Heat",
    
    # Milwaukee Bucks
    "mil": "Milwaukee Bucks", "milwaukee": "Milwaukee Bucks", "bucks": "Milwaukee Bucks",
    "milwaukee bucks": "Milwaukee Bucks",
    
    # Minnesota Timberwolves
    "min": "Minnesota Timberwolves", "minnesota": "Minnesota Timberwolves",
    "timberwolves": "Minnesota Timberwolves", "wolves": "Minnesota Timberwolves",
    "minnesota timberwolves": "Minnesota Timberwolves",
    
    # New Orleans Pelicans
    "nop": "New Orleans Pelicans", "new orleans": "New Orleans Pelicans",
    "pelicans": "New Orleans Pelicans", "new orleans pelicans": "New Orleans Pelicans",
    
    # New York Knicks
    "nyk": "New York Knicks", "ny knicks": "New York Knicks", "knicks": "New York Knicks",
    "new york knicks": "New York Knicks",
    
    # Oklahoma City Thunder
    "okc": "Oklahoma City Thunder", "oklahoma city": "Oklahoma City Thunder",
    "thunder": "Oklahoma City Thunder", "oklahoma city thunder": "Oklahoma City Thunder",
    
    # Orlando Magic
    "orl": "Orlando Magic", "orlando": "Orlando Magic", "magic": "Orlando Magic",
    "orlando magic": "Orlando Magic",
    
    # Philadelphia 76ers
    "phi": "Philadelphia 76ers", "philadelphia": "Philadelphia 76ers",
    "76ers": "Philadelphia 76ers", "sixers": "Philadelphia 76ers",
    "philadelphia 76ers": "Philadelphia 76ers",
    
    # Phoenix Suns
    "phx": "Phoenix Suns", "phoenix": "Phoenix Suns", "suns": "Phoenix Suns",
    "phoenix suns": "Phoenix Suns",
    
    # Portland Trail Blazers
    "por": "Portland Trail Blazers", "portland": "Portland Trail Blazers",
    "blazers": "Portland Trail Blazers", "trail blazers": "Portland Trail Blazers",
    "portland trail blazers": "Portland Trail Blazers",
    
    # Sacramento Kings
    "sac": "Sacramento Kings", "sacramento": "Sacramento Kings", "kings": "Sacramento Kings",
    "sacramento kings": "Sacramento Kings",
    
    # San Antonio Spurs
    "sas": "San Antonio Spurs", "sa": "San Antonio Spurs", "san antonio": "San Antonio Spurs",
    "spurs": "San Antonio Spurs", "san antonio spurs": "San Antonio Spurs",
    
    # Toronto Raptors
    "tor": "Toronto Raptors", "toronto": "Toronto Raptors", "raptors": "Toronto Raptors",
    "toronto raptors": "Toronto Raptors",
    
    # Utah Jazz
    "uta": "Utah Jazz", "utah": "Utah Jazz", "jazz": "Utah Jazz",
    "utah jazz": "Utah Jazz",
    
    # Washington Wizards
    "was": "Washington Wizards", "wsh": "Washington Wizards", 
    "washington": "Washington Wizards", "wizards": "Washington Wizards",
    "washington wizards": "Washington Wizards",
}

# =============================================================================
# NFL TEAM NORMALIZATION
# =============================================================================
NFL_TEAMS: Dict[str, str] = {
    # AFC East
    "buf": "Buffalo Bills", "buffalo": "Buffalo Bills", "bills": "Buffalo Bills",
    "mia": "Miami Dolphins", "miami dolphins": "Miami Dolphins", "dolphins": "Miami Dolphins",
    "ne": "New England Patriots", "new england": "New England Patriots", "patriots": "New England Patriots",
    "nyj": "New York Jets", "jets": "New York Jets", "ny jets": "New York Jets",
    
    # AFC North
    "bal": "Baltimore Ravens", "baltimore": "Baltimore Ravens", "ravens": "Baltimore Ravens",
    "cin": "Cincinnati Bengals", "cincinnati": "Cincinnati Bengals", "bengals": "Cincinnati Bengals",
    "cle": "Cleveland Browns", "cleveland": "Cleveland Browns", "browns": "Cleveland Browns",
    "pit": "Pittsburgh Steelers", "pittsburgh": "Pittsburgh Steelers", "steelers": "Pittsburgh Steelers",
    
    # AFC South
    "hou": "Houston Texans", "houston": "Houston Texans", "texans": "Houston Texans",
    "ind": "Indianapolis Colts", "indianapolis": "Indianapolis Colts", "colts": "Indianapolis Colts",
    "jax": "Jacksonville Jaguars", "jacksonville": "Jacksonville Jaguars", "jaguars": "Jacksonville Jaguars",
    "ten": "Tennessee Titans", "tennessee": "Tennessee Titans", "titans": "Tennessee Titans",
    
    # AFC West
    "den": "Denver Broncos", "denver": "Denver Broncos", "broncos": "Denver Broncos",
    "kc": "Kansas City Chiefs", "kansas city": "Kansas City Chiefs", "chiefs": "Kansas City Chiefs",
    "lv": "Las Vegas Raiders", "las vegas": "Las Vegas Raiders", "raiders": "Las Vegas Raiders",
    "lac": "LA Chargers", "la chargers": "LA Chargers", "chargers": "LA Chargers",
    "los angeles chargers": "LA Chargers",
    
    # NFC East
    "dal": "Dallas Cowboys", "dallas": "Dallas Cowboys", "cowboys": "Dallas Cowboys",
    "nyg": "New York Giants", "giants": "New York Giants", "ny giants": "New York Giants",
    "phi": "Philadelphia Eagles", "philadelphia": "Philadelphia Eagles", "eagles": "Philadelphia Eagles",
    "was": "Washington Commanders", "washington": "Washington Commanders", "commanders": "Washington Commanders",
    "wsh": "Washington Commanders",
    
    # NFC North
    "chi": "Chicago Bears", "chicago": "Chicago Bears", "bears": "Chicago Bears",
    "det": "Detroit Lions", "detroit": "Detroit Lions", "lions": "Detroit Lions",
    "gb": "Green Bay Packers", "green bay": "Green Bay Packers", "packers": "Green Bay Packers",
    "min": "Minnesota Vikings", "minnesota": "Minnesota Vikings", "vikings": "Minnesota Vikings",
    
    # NFC South
    "atl": "Atlanta Falcons", "atlanta": "Atlanta Falcons", "falcons": "Atlanta Falcons",
    "car": "Carolina Panthers", "carolina": "Carolina Panthers", "panthers": "Carolina Panthers",
    "no": "New Orleans Saints", "new orleans": "New Orleans Saints", "saints": "New Orleans Saints",
    "tb": "Tampa Bay Buccaneers", "tampa bay": "Tampa Bay Buccaneers", "buccaneers": "Tampa Bay Buccaneers",
    "bucs": "Tampa Bay Buccaneers",
    
    # NFC West
    "ari": "Arizona Cardinals", "arizona": "Arizona Cardinals", "cardinals": "Arizona Cardinals",
    "lar": "LA Rams", "la rams": "LA Rams", "rams": "LA Rams", "los angeles rams": "LA Rams",
    "sf": "San Francisco 49ers", "san francisco": "San Francisco 49ers", "49ers": "San Francisco 49ers",
    "niners": "San Francisco 49ers",
    "sea": "Seattle Seahawks", "seattle": "Seattle Seahawks", "seahawks": "Seattle Seahawks",
}

# =============================================================================
# NHL TEAM NORMALIZATION
# =============================================================================
NHL_TEAMS: Dict[str, str] = {
    # Atlantic Division
    "bos": "Boston Bruins", "boston": "Boston Bruins", "bruins": "Boston Bruins",
    "buf": "Buffalo Sabres", "buffalo": "Buffalo Sabres", "sabres": "Buffalo Sabres",
    "det": "Detroit Red Wings", "detroit": "Detroit Red Wings", "red wings": "Detroit Red Wings",
    "fla": "Florida Panthers", "florida": "Florida Panthers",
    "mtl": "Montreal Canadiens", "montreal": "Montreal Canadiens", "canadiens": "Montreal Canadiens",
    "habs": "Montreal Canadiens",
    "ott": "Ottawa Senators", "ottawa": "Ottawa Senators", "senators": "Ottawa Senators",
    "sens": "Ottawa Senators",
    "tbl": "Tampa Bay Lightning", "tampa bay": "Tampa Bay Lightning", "lightning": "Tampa Bay Lightning",
    "tampa": "Tampa Bay Lightning",
    "tor": "Toronto Maple Leafs", "toronto": "Toronto Maple Leafs", "maple leafs": "Toronto Maple Leafs",
    "leafs": "Toronto Maple Leafs",
    
    # Metropolitan Division
    "car": "Carolina Hurricanes", "carolina": "Carolina Hurricanes", "hurricanes": "Carolina Hurricanes",
    "canes": "Carolina Hurricanes",
    "cbj": "Columbus Blue Jackets", "columbus": "Columbus Blue Jackets", "blue jackets": "Columbus Blue Jackets",
    "njd": "New Jersey Devils", "nj": "New Jersey Devils", "new jersey": "New Jersey Devils", 
    "devils": "New Jersey Devils",
    "nyi": "New York Islanders", "ny islanders": "New York Islanders", "islanders": "New York Islanders",
    "nyr": "New York Rangers", "ny rangers": "New York Rangers", "rangers": "New York Rangers",
    "phi": "Philadelphia Flyers", "philadelphia": "Philadelphia Flyers", "flyers": "Philadelphia Flyers",
    "pit": "Pittsburgh Penguins", "pittsburgh": "Pittsburgh Penguins", "penguins": "Pittsburgh Penguins",
    "pens": "Pittsburgh Penguins",
    "wsh": "Washington Capitals", "washington": "Washington Capitals", "capitals": "Washington Capitals",
    "caps": "Washington Capitals",
    
    # Central Division
    "chi": "Chicago Blackhawks", "chicago": "Chicago Blackhawks", "blackhawks": "Chicago Blackhawks",
    "hawks": "Chicago Blackhawks",
    "col": "Colorado Avalanche", "colorado": "Colorado Avalanche", "avalanche": "Colorado Avalanche",
    "avs": "Colorado Avalanche",
    "dal": "Dallas Stars", "dallas": "Dallas Stars", "stars": "Dallas Stars",
    "min": "Minnesota Wild", "minnesota": "Minnesota Wild", "wild": "Minnesota Wild",
    "nsh": "Nashville Predators", "nashville": "Nashville Predators", "predators": "Nashville Predators",
    "preds": "Nashville Predators",
    "stl": "St. Louis Blues", "st louis": "St. Louis Blues", "blues": "St. Louis Blues",
    "saint louis": "St. Louis Blues",
    "wpg": "Winnipeg Jets", "winnipeg": "Winnipeg Jets",
    "uta": "Utah Hockey Club", "utah": "Utah Hockey Club",  # Formerly Arizona Coyotes
    
    # Pacific Division
    "ana": "Anaheim Ducks", "anaheim": "Anaheim Ducks", "ducks": "Anaheim Ducks",
    "cgy": "Calgary Flames", "calgary": "Calgary Flames", "flames": "Calgary Flames",
    "edm": "Edmonton Oilers", "edmonton": "Edmonton Oilers", "oilers": "Edmonton Oilers",
    "lak": "LA Kings", "la": "LA Kings", "la kings": "LA Kings", "kings": "LA Kings",
    "los angeles kings": "LA Kings",
    "sjs": "San Jose Sharks", "san jose": "San Jose Sharks", "sharks": "San Jose Sharks",
    "sea": "Seattle Kraken", "seattle": "Seattle Kraken", "kraken": "Seattle Kraken",
    "van": "Vancouver Canucks", "vancouver": "Vancouver Canucks", "canucks": "Vancouver Canucks",
    "vgk": "Vegas Golden Knights", "vegas": "Vegas Golden Knights", "golden knights": "Vegas Golden Knights",
}

# =============================================================================
# MLB TEAM NORMALIZATION
# =============================================================================
MLB_TEAMS: Dict[str, str] = {
    # AL East
    "bal": "Baltimore Orioles", "baltimore": "Baltimore Orioles", "orioles": "Baltimore Orioles",
    "bos": "Boston Red Sox", "boston": "Boston Red Sox", "red sox": "Boston Red Sox",
    "nyy": "New York Yankees", "ny yankees": "New York Yankees", "yankees": "New York Yankees",
    "tb": "Tampa Bay Rays", "tampa bay": "Tampa Bay Rays", "rays": "Tampa Bay Rays",
    "tor": "Toronto Blue Jays", "toronto": "Toronto Blue Jays", "blue jays": "Toronto Blue Jays",
    
    # AL Central
    "cws": "Chicago White Sox", "chi": "Chicago White Sox", "white sox": "Chicago White Sox",
    "cle": "Cleveland Guardians", "cleveland": "Cleveland Guardians", "guardians": "Cleveland Guardians",
    "det": "Detroit Tigers", "detroit": "Detroit Tigers", "tigers": "Detroit Tigers",
    "kc": "Kansas City Royals", "kansas city": "Kansas City Royals", "royals": "Kansas City Royals",
    "min": "Minnesota Twins", "minnesota": "Minnesota Twins", "twins": "Minnesota Twins",
    
    # AL West
    "hou": "Houston Astros", "houston": "Houston Astros", "astros": "Houston Astros",
    "laa": "LA Angels", "la angels": "LA Angels", "angels": "LA Angels",
    "oak": "Oakland Athletics", "oakland": "Oakland Athletics", "athletics": "Oakland Athletics", "a's": "Oakland Athletics",
    "sea": "Seattle Mariners", "seattle": "Seattle Mariners", "mariners": "Seattle Mariners",
    "tex": "Texas Rangers", "texas": "Texas Rangers", "rangers": "Texas Rangers",
    
    # NL East
    "atl": "Atlanta Braves", "atlanta": "Atlanta Braves", "braves": "Atlanta Braves",
    "mia": "Miami Marlins", "miami": "Miami Marlins", "marlins": "Miami Marlins",
    "nym": "New York Mets", "ny mets": "New York Mets", "mets": "New York Mets",
    "phi": "Philadelphia Phillies", "philadelphia": "Philadelphia Phillies", "phillies": "Philadelphia Phillies",
    "wsh": "Washington Nationals", "washington": "Washington Nationals", "nationals": "Washington Nationals", "nats": "Washington Nationals",
    
    # NL Central
    "chc": "Chicago Cubs", "cubs": "Chicago Cubs",
    "cin": "Cincinnati Reds", "cincinnati": "Cincinnati Reds", "reds": "Cincinnati Reds",
    "mil": "Milwaukee Brewers", "milwaukee": "Milwaukee Brewers", "brewers": "Milwaukee Brewers",
    "pit": "Pittsburgh Pirates", "pittsburgh": "Pittsburgh Pirates", "pirates": "Pittsburgh Pirates",
    "stl": "St. Louis Cardinals", "st louis": "St. Louis Cardinals", "cardinals": "St. Louis Cardinals",
    
    # NL West
    "ari": "Arizona Diamondbacks", "arizona": "Arizona Diamondbacks", "diamondbacks": "Arizona Diamondbacks", "dbacks": "Arizona Diamondbacks",
    "col": "Colorado Rockies", "colorado": "Colorado Rockies", "rockies": "Colorado Rockies",
    "lad": "LA Dodgers", "la dodgers": "LA Dodgers", "dodgers": "LA Dodgers",
    "sd": "San Diego Padres", "san diego": "San Diego Padres", "padres": "San Diego Padres",
    "sf": "San Francisco Giants", "san francisco": "San Francisco Giants",
}

# =============================================================================
# COLLEGE BASKETBALL TEAMS (Top Programs)
# =============================================================================
COLLEGE_BASKETBALL_TEAMS: Dict[str, str] = {
    # ACC
    "duke": "Duke Blue Devils", "blue devils": "Duke Blue Devils",
    "unc": "North Carolina Tar Heels", "tar heels": "North Carolina Tar Heels", 
    "north carolina": "North Carolina Tar Heels",
    "uva": "Virginia Cavaliers", "virginia": "Virginia Cavaliers",
    "wake": "Wake Forest Demon Deacons", "wake forest": "Wake Forest Demon Deacons",
    "nc state": "NC State Wolfpack", "ncsu": "NC State Wolfpack",
    "louisville": "Louisville Cardinals",
    "syracuse": "Syracuse Orange", "cuse": "Syracuse Orange",
    "fsu": "Florida State Seminoles", "florida state": "Florida State Seminoles",
    "miami": "Miami Hurricanes",
    "pitt": "Pittsburgh Panthers",
    "gt": "Georgia Tech Yellow Jackets", "georgia tech": "Georgia Tech Yellow Jackets",
    "bc": "Boston College Eagles", "boston college": "Boston College Eagles",
    "nd": "Notre Dame Fighting Irish", "notre dame": "Notre Dame Fighting Irish",
    "clemson": "Clemson Tigers",
    "vt": "Virginia Tech Hokies", "virginia tech": "Virginia Tech Hokies",
    "smu": "SMU Mustangs",
    "cal": "California Golden Bears", "california": "California Golden Bears",
    "stanford": "Stanford Cardinal",
    
    # Big Ten
    "msu": "Michigan State Spartans", "michigan state": "Michigan State Spartans",
    "um": "Michigan Wolverines", "michigan": "Michigan Wolverines",
    "osu": "Ohio State Buckeyes", "ohio state": "Ohio State Buckeyes",
    "iu": "Indiana Hoosiers", "indiana": "Indiana Hoosiers",
    "purdue": "Purdue Boilermakers",
    "illinois": "Illinois Fighting Illini",
    "wisconsin": "Wisconsin Badgers",
    "iowa": "Iowa Hawkeyes",
    "minnesota": "Minnesota Golden Gophers",
    "maryland": "Maryland Terrapins",
    "rutgers": "Rutgers Scarlet Knights",
    "northwestern": "Northwestern Wildcats",
    "psu": "Penn State Nittany Lions", "penn state": "Penn State Nittany Lions",
    "nebraska": "Nebraska Cornhuskers",
    "ucla": "UCLA Bruins",
    "usc": "USC Trojans",
    "oregon": "Oregon Ducks",
    "washington": "Washington Huskies",
    
    # Big 12
    "ku": "Kansas Jayhawks", "kansas": "Kansas Jayhawks",
    "baylor": "Baylor Bears",
    "ttu": "Texas Tech Red Raiders", "texas tech": "Texas Tech Red Raiders",
    "texas": "Texas Longhorns",
    "tcu": "TCU Horned Frogs",
    "osu": "Oklahoma State Cowboys", "oklahoma state": "Oklahoma State Cowboys",
    "wvu": "West Virginia Mountaineers", "west virginia": "West Virginia Mountaineers",
    "ksu": "Kansas State Wildcats", "kansas state": "Kansas State Wildcats",
    "isu": "Iowa State Cyclones", "iowa state": "Iowa State Cyclones",
    "ou": "Oklahoma Sooners", "oklahoma": "Oklahoma Sooners",
    "byu": "BYU Cougars",
    "uc": "Cincinnati Bearcats", "cincinnati": "Cincinnati Bearcats",
    "uh": "Houston Cougars", "houston": "Houston Cougars",
    "ucf": "UCF Knights",
    "arizona": "Arizona Wildcats",
    "asu": "Arizona State Sun Devils", "arizona state": "Arizona State Sun Devils",
    "colorado": "Colorado Buffaloes",
    "utah": "Utah Utes",
    
    # SEC
    "uk": "Kentucky Wildcats", "kentucky": "Kentucky Wildcats",
    "tennessee": "Tennessee Volunteers", "vols": "Tennessee Volunteers",
    "auburn": "Auburn Tigers",
    "alabama": "Alabama Crimson Tide", "bama": "Alabama Crimson Tide",
    "arkansas": "Arkansas Razorbacks", "hogs": "Arkansas Razorbacks",
    "florida": "Florida Gators", "gators": "Florida Gators",
    "lsu": "LSU Tigers",
    "georgia": "Georgia Bulldogs", "uga": "Georgia Bulldogs",
    "mizzou": "Missouri Tigers", "missouri": "Missouri Tigers",
    "sc": "South Carolina Gamecocks", "south carolina": "South Carolina Gamecocks",
    "vandy": "Vanderbilt Commodores", "vanderbilt": "Vanderbilt Commodores",
    "ole miss": "Ole Miss Rebels", "mississippi": "Ole Miss Rebels",
    "miss state": "Mississippi State Bulldogs", "mississippi state": "Mississippi State Bulldogs",
    "a&m": "Texas A&M Aggies", "texas a&m": "Texas A&M Aggies",
    
    # Big East
    "uconn": "UConn Huskies", "connecticut": "UConn Huskies",
    "villanova": "Villanova Wildcats", "nova": "Villanova Wildcats",
    "creighton": "Creighton Bluejays",
    "marquette": "Marquette Golden Eagles",
    "georgetown": "Georgetown Hoyas",
    "xavier": "Xavier Musketeers",
    "st johns": "St. John's Red Storm", "st. john's": "St. John's Red Storm",
    "seton hall": "Seton Hall Pirates",
    "providence": "Providence Friars",
    "butler": "Butler Bulldogs",
    "depaul": "DePaul Blue Demons",
    
    # Other Top Programs
    "gonzaga": "Gonzaga Bulldogs", "zags": "Gonzaga Bulldogs",
    "memphis": "Memphis Tigers",
    "unlv": "UNLV Rebels",
    "sdsu": "San Diego State Aztecs", "san diego state": "San Diego State Aztecs",
}


@dataclass
class NormalizedMarket:
    """Normalized market representation for cross-platform matching."""
    sport: Sport
    normalized_name: str  # e.g., "Utah Jazz vs Cleveland Cavaliers"
    home_team: Optional[str]
    away_team: Optional[str]
    game_date: Optional[str]  # YYYY-MM-DD
    market_type: str  # "game_winner", "championship", "mvp", etc.
    player: Optional[str]
    original_question: str
    platform: str
    platform_id: str


class MarketNormalizer:
    """
    Normalizes market data from different platforms into a consistent format.
    
    Usage:
        normalizer = MarketNormalizer()
        
        # From Polymarket slug: nba-uta-cle-2026-01-12
        poly_market = normalizer.normalize_polymarket(slug="nba-uta-cle-2026-01-12", ...)
        
        # From Kalshi ticker: KXNBAGAME-26JAN12UTACLE-UTA
        kalshi_market = normalizer.normalize_kalshi(ticker="KXNBAGAME-26JAN12UTACLE-UTA", ...)
        
        # Check if markets match
        if normalizer.markets_match(poly_market, kalshi_market):
            # Same game!
    """
    
    def __init__(self):
        # Build unified lookup dictionary by sport
        self.team_maps = {
            Sport.NBA: NBA_TEAMS,
            Sport.NFL: NFL_TEAMS,
            Sport.NHL: NHL_TEAMS,
            Sport.MLB: MLB_TEAMS,
            Sport.NCAA_MBB: COLLEGE_BASKETBALL_TEAMS,
            Sport.NCAA_WBB: COLLEGE_BASKETBALL_TEAMS,
        }
    
    def detect_sport(self, text: str, ticker: str = "", slug: str = "") -> Sport:
        """Detect sport from text, ticker, or slug."""
        combined = f"{text} {ticker} {slug}".lower()
        
        # Check explicit sport markers first
        sport_markers = [
            (["kxnbagame", "nba-", "nba ", "basketball"], Sport.NBA),
            (["kxnflgame", "nfl-", "nfl ", "super bowl"], Sport.NFL),
            (["kxnhlgame", "nhl-", "nhl ", "hockey", "stanley cup"], Sport.NHL),
            (["kxmlbgame", "mlb-", "mlb ", "baseball", "world series"], Sport.MLB),
            (["kxwnbagame", "wnba"], Sport.WNBA),
            (["kxncaabgame", "kxncaambgame", "cbb-", "college basketball"], Sport.NCAA_MBB),
            (["kxncaawbgame", "cwbb-", "women's basketball"], Sport.NCAA_WBB),
            (["kxncaafgame", "kxncaafbgame", "cfb-", "college football"], Sport.NCAA_FB),
            (["kxufcfight", "ufc", "mma"], Sport.UFC),
            (["kxtennismatch", "kxatptour", "kxwtatour", "tennis", "wimbledon", "us open"], Sport.TENNIS),
            (["kxpgatour", "kxlpgatour", "golf", "pga", "masters"], Sport.GOLF),
            (["kxf1race", "formula 1", "f1"], Sport.F1),
            (["kxnascarrace", "nascar"], Sport.NASCAR),
            (["kxindycarrace", "indycar"], Sport.INDYCAR),
            (["kxcricket", "cricket"], Sport.CRICKET),
            (["kxchessmatch", "chess"], Sport.CHESS),
            (["kxdota2game", "esports", "dota"], Sport.ESPORTS),
        ]
        
        for markers, sport in sport_markers:
            if any(m in combined for m in markers):
                return sport
        
        return Sport.UNKNOWN
    
    def normalize_team(self, team_ref: str, sport: Sport) -> Optional[str]:
        """
        Normalize a team reference to canonical name.
        
        Args:
            team_ref: Team abbreviation, city, mascot, or full name
            sport: The sport context (determines which team map to use)
            
        Returns:
            Canonical team name or None if not found
        """
        if not team_ref:
            return None
        
        team_ref_lower = team_ref.lower().strip()
        
        # Get the appropriate team map
        team_map = self.team_maps.get(sport, {})
        
        # Direct lookup
        if team_ref_lower in team_map:
            return team_map[team_ref_lower]
        
        # Try partial match (for longer strings containing team name)
        for alias, canonical in team_map.items():
            if alias in team_ref_lower or team_ref_lower in alias:
                return canonical
        
        return None
    
    def parse_polymarket_slug(self, slug: str) -> Tuple[Optional[str], Optional[str], Optional[str], Sport]:
        """
        Parse Polymarket slug to extract teams and date.
        
        Format: sport-away-home-YYYY-MM-DD
        Example: nba-uta-cle-2026-01-12
        
        Returns: (away_team, home_team, game_date, sport)
        """
        if not slug:
            return None, None, None, Sport.UNKNOWN
        
        parts = slug.lower().split("-")
        if len(parts) < 5:
            return None, None, None, Sport.UNKNOWN
        
        sport_prefix = parts[0]
        sport_map = {
            "nba": Sport.NBA,
            "nfl": Sport.NFL,
            "nhl": Sport.NHL,
            "mlb": Sport.MLB,
            "cbb": Sport.NCAA_MBB,
            "cwbb": Sport.NCAA_WBB,
            "cfb": Sport.NCAA_FB,
        }
        
        sport = sport_map.get(sport_prefix, Sport.UNKNOWN)
        
        # Extract teams (parts[1] = away, parts[2] = home)
        away_abbr = parts[1]
        home_abbr = parts[2]
        
        away_team = self.normalize_team(away_abbr, sport)
        home_team = self.normalize_team(home_abbr, sport)
        
        # Extract date (parts[3]-parts[4]-parts[5])
        game_date = None
        if len(parts) >= 6:
            try:
                game_date = f"{parts[3]}-{parts[4]}-{parts[5]}"
            except:
                pass
        
        return away_team, home_team, game_date, sport
    
    def parse_kalshi_ticker(self, ticker: str) -> Tuple[Optional[str], Optional[str], Optional[str], Sport]:
        """
        Parse Kalshi ticker to extract teams and date.
        
        Format: KXSPORTGAME-YYMMMDDTEAMS-WINNER
        Example: KXNBAGAME-26JAN12UTACLE-UTA
        
        Returns: (away_team, home_team, game_date, sport)
        """
        if not ticker:
            return None, None, None, Sport.UNKNOWN
        
        ticker_upper = ticker.upper()
        
        # Detect sport from ticker prefix
        sport = Sport.UNKNOWN
        if "NBAGAME" in ticker_upper:
            sport = Sport.NBA
        elif "NFLGAME" in ticker_upper:
            sport = Sport.NFL
        elif "NHLGAME" in ticker_upper:
            sport = Sport.NHL
        elif "MLBGAME" in ticker_upper:
            sport = Sport.MLB
        elif "NCAAB" in ticker_upper or "NCAAMB" in ticker_upper:
            sport = Sport.NCAA_MBB
        
        # Parse date and teams from middle segment
        # Example: 26JAN12UTACLE -> year=26, month=JAN, day=12, teams=UTACLE
        parts = ticker_upper.split("-")
        if len(parts) < 2:
            return None, None, None, sport
        
        middle = parts[1] if len(parts) > 1 else ""
        
        # Extract date: 26JAN12 pattern
        date_match = re.match(r'(\d{2})([A-Z]{3})(\d{1,2})([A-Z]+)', middle)
        game_date = None
        teams_str = ""
        
        if date_match:
            year = f"20{date_match.group(1)}"
            month_map = {
                "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
                "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
                "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
            }
            month = month_map.get(date_match.group(2), "01")
            day = date_match.group(3).zfill(2)
            game_date = f"{year}-{month}-{day}"
            teams_str = date_match.group(4)
        
        # Parse teams from concatenated abbrevs (e.g., UTACLE -> UTA, CLE)
        # Usually 3-char abbrevs
        away_team = None
        home_team = None
        
        if len(teams_str) >= 6:
            # Try 3+3 split
            away_abbr = teams_str[:3]
            home_abbr = teams_str[3:6]
            away_team = self.normalize_team(away_abbr, sport)
            home_team = self.normalize_team(home_abbr, sport)
        
        # If last part is a team (winner market), use it as confirmation
        if len(parts) >= 3:
            winner_abbr = parts[2]
            winner_team = self.normalize_team(winner_abbr, sport)
            # Winner should match one of the teams
            if winner_team and winner_team not in [away_team, home_team]:
                logger.warning(f"Winner {winner_team} doesn't match teams {away_team}, {home_team}")
        
        return away_team, home_team, game_date, sport
    
    def create_normalized_name(self, away_team: str, home_team: str) -> str:
        """Create standardized game name: 'Away Team vs Home Team'"""
        if away_team and home_team:
            return f"{away_team} vs {home_team}"
        return ""
    
    def markets_match(
        self, 
        poly_away: Optional[str], poly_home: Optional[str], poly_date: Optional[str],
        kalshi_away: Optional[str], kalshi_home: Optional[str], kalshi_date: Optional[str]
    ) -> bool:
        """
        Check if two markets represent the same game.
        
        Requires:
        1. Same two teams (order doesn't matter)
        2. Same date
        """
        if not all([poly_away, poly_home, kalshi_away, kalshi_home]):
            return False
        
        poly_teams = {poly_away, poly_home}
        kalshi_teams = {kalshi_away, kalshi_home}
        
        if poly_teams != kalshi_teams:
            return False
        
        # Date must match if both present
        if poly_date and kalshi_date:
            return poly_date == kalshi_date
        
        # If only one has date, accept but with lower confidence
        return True


# Global normalizer instance
_normalizer = None

def get_normalizer() -> MarketNormalizer:
    """Get or create the global normalizer instance."""
    global _normalizer
    if _normalizer is None:
        _normalizer = MarketNormalizer()
    return _normalizer

