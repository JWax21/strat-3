"""
Market Matching Service

Matches similar markets between Polymarket and Kalshi using
fuzzy string matching and semantic similarity.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

from clients.polymarket import PolymarketMarket
from clients.kalshi import KalshiMarket
from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MatchedMarket:
    """A matched pair of markets from different platforms."""
    polymarket: PolymarketMarket
    kalshi: KalshiMarket
    similarity_score: float  # 0-1 score of match confidence
    match_method: str  # How the match was determined
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "polymarket": self.polymarket.to_dict(),
            "kalshi": self.kalshi.to_dict(),
            "similarity_score": self.similarity_score,
            "match_method": self.match_method
        }


class MarketMatcher:
    """
    Service for matching similar markets across prediction platforms.
    
    Uses multiple matching strategies with STRICT validation:
    1. Exact keyword matching for key terms (multi-word phrases only)
    2. Fuzzy string matching for titles/questions
    3. Topic category alignment
    4. Entity name matching (people, companies, countries)
    """
    
    # High-value MULTI-WORD keywords (single words are too ambiguous)
    HIGH_VALUE_KEYWORDS = [
        # Politics - specific entities
        "donald trump", "trump administration", "joe biden", "biden administration",
        "presidential election", "2024 election", "2026 election",
        "supreme court", "federal reserve", "interest rate",
        # Sports - specific events  
        "super bowl", "world series", "stanley cup", "nba finals",
        "fifa world cup", "champions league", "wimbledon",
        # Tech - specific entities
        "openai", "artificial intelligence", "chatgpt", "gpt-5",
        "tesla", "spacex", "elon musk",
        # Crypto - specific assets
        "bitcoin price", "ethereum price", "btc", "eth",
        # Geopolitics - specific conflicts/entities
        "ukraine russia", "russia ukraine", "israel hamas", "gaza",
        "china taiwan", "north korea"
    ]
    
    # Topic categories - markets must share a category to match
    TOPIC_CATEGORIES = {
        "politics_us": ["president", "election", "congress", "senate", "republican", "democrat", "trump", "biden", "white house"],
        "politics_intl": ["prime minister", "parliament", "brexit", "eu", "nato", "united nations"],
        "sports_football": ["nfl", "super bowl", "touchdown", "quarterback"],
        "sports_soccer": ["fifa", "world cup", "premier league", "champions league", "soccer", "football"],
        "sports_basketball": ["nba", "basketball", "lakers", "celtics"],
        "sports_baseball": ["mlb", "world series", "baseball"],
        "crypto": ["bitcoin", "ethereum", "btc", "eth", "crypto", "cryptocurrency"],
        "tech": ["ai", "openai", "gpt", "tesla", "spacex", "apple", "google", "microsoft", "meta"],
        "climate": ["temperature", "celsius", "warming", "climate", "carbon"],
        "economy": ["inflation", "gdp", "interest rate", "federal reserve", "recession", "unemployment"],
    }
    
    # Common words to ignore when matching
    STOP_WORDS = {
        "will", "the", "a", "an", "be", "is", "are", "was", "were",
        "to", "of", "in", "for", "on", "at", "by", "with", "from",
        "or", "and", "this", "that", "it", "as", "if", "than",
        "yes", "no", "before", "after", "during", "what", "who",
        "when", "where", "how", "which", "would", "could", "should",
        "may", "might", "can", "does", "do", "did", "has", "have",
        "world"  # Too common - "World Cup" vs "world temperature"
    }
    
    # Minimum match threshold - balance between strictness and coverage
    MIN_MATCH_THRESHOLD = 0.60
    
    def __init__(self, match_threshold: float = None):
        """
        Initialize the market matcher.
        
        Args:
            match_threshold: Minimum similarity score to consider a match (0-1)
        """
        settings = get_settings()
        # Use at least MIN_MATCH_THRESHOLD even if config says lower
        self.match_threshold = max(
            match_threshold or settings.match_threshold,
            self.MIN_MATCH_THRESHOLD
        )
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        - Lowercase
        - Remove punctuation
        - Remove stop words
        - Collapse whitespace
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Remove punctuation except hyphens
        text = re.sub(r'[^\w\s-]', ' ', text)
        
        # Split into words
        words = text.split()
        
        # Remove stop words
        words = [w for w in words if w not in self.STOP_WORDS]
        
        # Rejoin and collapse whitespace
        return ' '.join(words)
    
    def extract_keywords(self, text: str) -> Set[str]:
        """Extract significant keywords from text."""
        normalized = self.normalize_text(text)
        words = set(normalized.split())
        
        # Only add multi-word keywords (not single words)
        text_lower = text.lower()
        for keyword in self.HIGH_VALUE_KEYWORDS:
            if keyword in text_lower:
                words.add(keyword)
        
        return words
    
    def get_topic_categories(self, text: str) -> Set[str]:
        """Determine which topic categories a text belongs to."""
        text_lower = text.lower()
        categories = set()
        
        for category, keywords in self.TOPIC_CATEGORIES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    categories.add(category)
                    break
        
        return categories
    
    def extract_entities(self, text: str) -> Set[str]:
        """
        Extract named entities (people, companies, countries) from text.
        These are crucial for matching - markets about different entities shouldn't match.
        """
        entities = set()
        text_lower = text.lower()
        
        # People names (common in prediction markets)
        people = [
            "trump", "biden", "obama", "harris", "desantis", "pence", "musk", "elon",
            "bezos", "zuckerberg", "cook", "altman", "putin", "zelensky",
            "xi jinping", "xi", "netanyahu", "modi", "pope", "francis",
            "vance", "pelosi", "schumer", "mcconnell"
        ]
        
        # Countries
        countries = [
            "united states", "usa", "us", "america", "china", "russia", 
            "ukraine", "israel", "iran", "north korea", "taiwan", "india",
            "germany", "france", "uk", "britain", "japan", "italy", "brazil",
            "mexico", "canada", "gaza", "palestine"
        ]
        
        # Companies/Organizations
        companies = [
            "tesla", "spacex", "openai", "google", "apple", "microsoft",
            "meta", "amazon", "nvidia", "twitter", "x.com", "doge"
        ]
        
        # Sports teams/leagues
        sports = [
            "nfl", "nba", "mlb", "nhl", "fifa", "uefa", "olympics",
            "world cup", "super bowl"
        ]
        
        # Events/Topics
        events = [
            "mars", "climate", "warming", "inflation", "recession",
            "deportation", "immigration", "tariff", "bitcoin", "ethereum"
        ]
        
        for entity_list in [people, countries, companies, sports, events]:
            for entity in entity_list:
                if entity in text_lower:
                    entities.add(entity)
        
        return entities
    
    def calculate_similarity(
        self,
        poly_market: PolymarketMarket,
        kalshi_market: KalshiMarket
    ) -> Tuple[float, str]:
        """
        Calculate similarity score between two markets.
        
        Returns:
            Tuple of (similarity_score, match_method)
            
        Uses STRICT matching rules:
        1. Markets must share at least one topic category
        2. If both have named entities, they must share at least one
        3. Fuzzy score must be above threshold
        """
        poly_text = self.normalize_text(poly_market.question)
        kalshi_text = self.normalize_text(kalshi_market.question)
        
        # VALIDATION 1: Topic category alignment
        poly_categories = self.get_topic_categories(poly_market.question)
        kalshi_categories = self.get_topic_categories(kalshi_market.question)
        
        # If both have categories, they must share at least one
        if poly_categories and kalshi_categories:
            shared_categories = poly_categories & kalshi_categories
            if not shared_categories:
                logger.debug(
                    f"Topic mismatch: '{poly_market.question[:50]}' ({poly_categories}) "
                    f"vs '{kalshi_market.question[:50]}' ({kalshi_categories})"
                )
                return 0.0, "topic_mismatch"
        
        # VALIDATION 2: Entity alignment
        poly_entities = self.extract_entities(poly_market.question)
        kalshi_entities = self.extract_entities(kalshi_market.question)
        
        # If both have named entities, they must share at least one
        if poly_entities and kalshi_entities:
            shared_entities = poly_entities & kalshi_entities
            if not shared_entities:
                logger.debug(
                    f"Entity mismatch: '{poly_market.question[:50]}' ({poly_entities}) "
                    f"vs '{kalshi_market.question[:50]}' ({kalshi_entities})"
                )
                return 0.0, "entity_mismatch"
        
        # Strategy 1: High-value multi-word keyword match
        poly_keywords = self.extract_keywords(poly_market.question)
        kalshi_keywords = self.extract_keywords(kalshi_market.question)
        
        # Find shared high-value keywords (multi-word phrases)
        high_value_shared = set()
        for kw in self.HIGH_VALUE_KEYWORDS:
            if kw in poly_market.question.lower() and kw in kalshi_market.question.lower():
                high_value_shared.add(kw)
        
        if high_value_shared:
            # Very strong match - shared specific phrases
            keyword_score = min(1.0, len(high_value_shared) * 0.5)
        else:
            keyword_score = 0
        
        # Strategy 2: Fuzzy string matching
        # Use multiple fuzzy matching algorithms
        
        # Token sort ratio - good for reordered words
        token_sort = fuzz.token_sort_ratio(poly_text, kalshi_text) / 100
        
        # Token set ratio - handles partial matches
        token_set = fuzz.token_set_ratio(poly_text, kalshi_text) / 100
        
        # Standard ratio - exact string comparison
        standard = fuzz.ratio(poly_text, kalshi_text) / 100
        
        # Use STRICT scoring - prefer standard ratio to avoid false positives
        fuzzy_score = (standard * 0.5 + token_sort * 0.3 + token_set * 0.2)
        
        # Strategy 3: Significant keyword overlap (excluding stop words)
        if poly_keywords and kalshi_keywords:
            # Only count keywords that are 4+ characters (more meaningful)
            sig_poly = {k for k in poly_keywords if len(k) >= 4}
            sig_kalshi = {k for k in kalshi_keywords if len(k) >= 4}
            
            if sig_poly and sig_kalshi:
                common_keywords = sig_poly & sig_kalshi
                keyword_overlap = len(common_keywords) / max(len(sig_poly), len(sig_kalshi))
            else:
                keyword_overlap = 0
        else:
            keyword_overlap = 0
        
        # Combine scores - weight fuzzy match most heavily
        combined_score = (
            0.50 * fuzzy_score +
            0.25 * keyword_overlap +
            0.25 * keyword_score
        )
        
        # BONUS: If they share entities AND categories, boost score
        if poly_entities and kalshi_entities:
            entity_overlap = len(poly_entities & kalshi_entities) / max(len(poly_entities), len(kalshi_entities))
            if entity_overlap > 0.5:
                combined_score = min(1.0, combined_score * 1.2)
        
        # Determine match method
        if keyword_score > 0.4:
            method = "high_value_keyword"
        elif fuzzy_score > 0.7:
            method = "fuzzy_match"
        elif keyword_overlap > 0.5:
            method = "keyword_overlap"
        else:
            method = "combined"
        
        return combined_score, method
    
    def match_markets(
        self,
        polymarket_markets: List[PolymarketMarket],
        kalshi_markets: List[KalshiMarket],
        top_n: int = None
    ) -> List[MatchedMarket]:
        """
        Match markets between Polymarket and Kalshi.
        
        Args:
            polymarket_markets: List of Polymarket markets
            kalshi_markets: List of Kalshi markets
            top_n: Return only top N matches per Polymarket market
            
        Returns:
            List of matched market pairs
        """
        matches: List[MatchedMarket] = []
        
        # Track which Kalshi markets have been matched to avoid duplicates
        used_kalshi_tickers = set()
        
        for poly_market in polymarket_markets:
            best_match: Optional[MatchedMarket] = None
            best_score = 0
            
            for kalshi_market in kalshi_markets:
                # Skip if this Kalshi market is already matched
                if kalshi_market.ticker in used_kalshi_tickers:
                    continue
                
                score, method = self.calculate_similarity(poly_market, kalshi_market)
                
                if score >= self.match_threshold and score > best_score:
                    best_score = score
                    best_match = MatchedMarket(
                        polymarket=poly_market,
                        kalshi=kalshi_market,
                        similarity_score=score,
                        match_method=method
                    )
            
            if best_match:
                matches.append(best_match)
                used_kalshi_tickers.add(best_match.kalshi.ticker)
        
        # Sort by similarity score
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        
        if top_n:
            matches = matches[:top_n]
        
        logger.info(
            f"Matched {len(matches)} markets out of "
            f"{len(polymarket_markets)} Polymarket and "
            f"{len(kalshi_markets)} Kalshi markets"
        )
        
        return matches
    
    def find_best_kalshi_match(
        self,
        poly_market: PolymarketMarket,
        kalshi_markets: List[KalshiMarket]
    ) -> Optional[MatchedMarket]:
        """
        Find the best Kalshi match for a single Polymarket market.
        
        Args:
            poly_market: The Polymarket market to match
            kalshi_markets: List of Kalshi markets to search
            
        Returns:
            Best matching pair or None
        """
        best_match = None
        best_score = 0
        
        for kalshi_market in kalshi_markets:
            score, method = self.calculate_similarity(poly_market, kalshi_market)
            
            if score >= self.match_threshold and score > best_score:
                best_score = score
                best_match = MatchedMarket(
                    polymarket=poly_market,
                    kalshi=kalshi_market,
                    similarity_score=score,
                    match_method=method
                )
        
        return best_match
    
    def find_best_poly_match(
        self,
        kalshi_market: KalshiMarket,
        poly_markets: List[PolymarketMarket]
    ) -> Optional[MatchedMarket]:
        """
        Find the best Polymarket match for a single Kalshi market.
        
        Args:
            kalshi_market: The Kalshi market to match
            poly_markets: List of Polymarket markets to search
            
        Returns:
            Best matching pair or None
        """
        best_match = None
        best_score = 0
        
        for poly_market in poly_markets:
            score, method = self.calculate_similarity(poly_market, kalshi_market)
            
            if score >= self.match_threshold and score > best_score:
                best_score = score
                best_match = MatchedMarket(
                    polymarket=poly_market,
                    kalshi=kalshi_market,
                    similarity_score=score,
                    match_method=method
                )
        
        return best_match

