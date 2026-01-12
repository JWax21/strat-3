"""
Arbitrage Detection Service

Identifies price discrepancies between matched markets
that could represent arbitrage opportunities.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from services.market_matcher import MatchedMarket
from config import get_settings

logger = logging.getLogger(__name__)


class ArbitrageType(str, Enum):
    """Types of arbitrage opportunities."""
    SIMPLE = "simple"  # Direct price difference
    SPREAD = "spread"  # Bid/ask spread opportunity
    MULTI_LEG = "multi_leg"  # Requires multiple trades


@dataclass
class ArbitrageOpportunity:
    """
    Represents an arbitrage opportunity between two platforms.
    
    An arbitrage exists when:
    - Platform A's YES price + Platform B's NO price < 1.0 (profit on YES)
    - Platform A's NO price + Platform B's YES price < 1.0 (profit on NO)
    - Or simply when prices differ significantly
    """
    matched_market: MatchedMarket
    
    # Price data
    poly_yes_price: float
    poly_no_price: float
    kalshi_yes_price: float
    kalshi_no_price: float
    
    # Calculated fields
    price_difference: float  # Absolute difference
    price_difference_percent: float  # Percentage difference
    potential_profit_bps: float  # Basis points profit
    
    # Direction
    buy_yes_on: str  # "polymarket" or "kalshi"
    buy_no_on: str
    
    # Arbitrage type
    arb_type: ArbitrageType
    
    # Metadata
    detected_at: datetime
    
    @property
    def profitable(self) -> bool:
        """Check if this is a potentially profitable opportunity."""
        return self.potential_profit_bps > 0
    
    @property
    def description(self) -> str:
        """Human-readable description of the opportunity."""
        return (
            f"Buy YES on {self.buy_yes_on} @ {self.poly_yes_price if self.buy_yes_on == 'polymarket' else self.kalshi_yes_price:.2%}, "
            f"Buy NO on {self.buy_no_on} @ {self.poly_no_price if self.buy_no_on == 'polymarket' else self.kalshi_no_price:.2%}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "matched_market": self.matched_market.to_dict(),
            "poly_yes_price": self.poly_yes_price,
            "poly_no_price": self.poly_no_price,
            "kalshi_yes_price": self.kalshi_yes_price,
            "kalshi_no_price": self.kalshi_no_price,
            "price_difference": self.price_difference,
            "price_difference_percent": self.price_difference_percent,
            "potential_profit_bps": self.potential_profit_bps,
            "buy_yes_on": self.buy_yes_on,
            "buy_no_on": self.buy_no_on,
            "arb_type": self.arb_type.value,
            "profitable": self.profitable,
            "description": self.description,
            "detected_at": self.detected_at.isoformat()
        }


class ArbitrageDetector:
    """
    Detects arbitrage opportunities between matched markets.
    
    Key concepts:
    - In a binary market, YES + NO should equal ~1.0 (100%)
    - If Platform A's YES (40%) + Platform B's NO (50%) = 90%, there's 10% arbitrage
    - We account for fees and spreads when calculating real profit
    """
    
    # Estimated fees per platform (can be configured)
    POLYMARKET_FEE = 0.02  # 2% fee
    KALSHI_FEE = 0.01  # 1% fee (Kalshi has lower fees)
    
    def __init__(self, min_difference_percent: float = None):
        """
        Initialize the arbitrage detector.
        
        Args:
            min_difference_percent: Minimum price difference to flag as opportunity
        """
        settings = get_settings()
        self.min_difference = min_difference_percent or settings.min_price_difference_percent
    
    def detect_opportunities(
        self,
        matched_markets: List[MatchedMarket]
    ) -> List[ArbitrageOpportunity]:
        """
        Analyze matched markets for arbitrage opportunities.
        
        Args:
            matched_markets: List of matched market pairs
            
        Returns:
            List of arbitrage opportunities, sorted by potential profit
        """
        opportunities = []
        
        for match in matched_markets:
            opportunity = self.analyze_match(match)
            if opportunity and opportunity.price_difference_percent >= self.min_difference:
                opportunities.append(opportunity)
        
        # Sort by profit potential (highest first)
        opportunities.sort(key=lambda o: o.potential_profit_bps, reverse=True)
        
        logger.info(
            f"Found {len(opportunities)} arbitrage opportunities "
            f"with >= {self.min_difference}% price difference"
        )
        
        return opportunities
    
    def analyze_match(self, match: MatchedMarket) -> Optional[ArbitrageOpportunity]:
        """
        Analyze a single matched market pair for arbitrage.
        
        Args:
            match: Matched market pair
            
        Returns:
            Arbitrage opportunity if found, None otherwise
        """
        poly = match.polymarket
        kalshi = match.kalshi
        
        # Get prices
        poly_yes = poly.yes_price
        poly_no = poly.no_price
        kalshi_yes = kalshi.yes_price
        kalshi_no = kalshi.no_price
        
        # Validate prices
        if not all([
            0 <= poly_yes <= 1,
            0 <= poly_no <= 1,
            0 <= kalshi_yes <= 1,
            0 <= kalshi_no <= 1
        ]):
            logger.warning(f"Invalid prices for match: {match}")
            return None
        
        # Calculate price difference (absolute)
        yes_diff = abs(poly_yes - kalshi_yes)
        
        # Calculate percentage difference based on midpoint
        midpoint = (poly_yes + kalshi_yes) / 2
        if midpoint > 0:
            price_diff_percent = (yes_diff / midpoint) * 100
        else:
            price_diff_percent = 0
        
        # Determine arbitrage direction
        # If Polymarket YES is cheaper, buy YES there and NO on Kalshi
        if poly_yes < kalshi_yes:
            buy_yes_on = "polymarket"
            buy_no_on = "kalshi"
            combined_cost = poly_yes + kalshi_no
        else:
            buy_yes_on = "kalshi"
            buy_no_on = "polymarket"
            combined_cost = kalshi_yes + poly_no
        
        # Calculate potential profit
        # If combined cost < 1.0, there's arbitrage profit
        # Profit = 1.0 - combined_cost - fees
        gross_profit = 1.0 - combined_cost
        
        # Account for fees on both sides
        total_fees = self.POLYMARKET_FEE + self.KALSHI_FEE
        net_profit = gross_profit - total_fees
        
        # Convert to basis points (1 bp = 0.01%)
        profit_bps = net_profit * 10000
        
        # Determine arbitrage type
        if net_profit > 0:
            arb_type = ArbitrageType.SIMPLE
        elif gross_profit > 0:
            arb_type = ArbitrageType.SPREAD  # Profitable before fees
        else:
            arb_type = ArbitrageType.SIMPLE
        
        return ArbitrageOpportunity(
            matched_market=match,
            poly_yes_price=poly_yes,
            poly_no_price=poly_no,
            kalshi_yes_price=kalshi_yes,
            kalshi_no_price=kalshi_no,
            price_difference=yes_diff,
            price_difference_percent=price_diff_percent,
            potential_profit_bps=profit_bps,
            buy_yes_on=buy_yes_on,
            buy_no_on=buy_no_on,
            arb_type=arb_type,
            detected_at=datetime.utcnow()
        )
    
    def get_summary_stats(
        self,
        opportunities: List[ArbitrageOpportunity]
    ) -> Dict[str, Any]:
        """
        Generate summary statistics for arbitrage opportunities.
        
        Args:
            opportunities: List of opportunities
            
        Returns:
            Summary statistics dictionary
        """
        if not opportunities:
            return {
                "total_opportunities": 0,
                "profitable_count": 0,
                "avg_price_difference_percent": 0,
                "max_price_difference_percent": 0,
                "avg_profit_bps": 0,
                "max_profit_bps": 0,
                "by_type": {}
            }
        
        profitable = [o for o in opportunities if o.profitable]
        
        return {
            "total_opportunities": len(opportunities),
            "profitable_count": len(profitable),
            "avg_price_difference_percent": sum(
                o.price_difference_percent for o in opportunities
            ) / len(opportunities),
            "max_price_difference_percent": max(
                o.price_difference_percent for o in opportunities
            ),
            "avg_profit_bps": sum(
                o.potential_profit_bps for o in opportunities
            ) / len(opportunities),
            "max_profit_bps": max(
                o.potential_profit_bps for o in opportunities
            ),
            "by_type": {
                arb_type.value: len([
                    o for o in opportunities if o.arb_type == arb_type
                ])
                for arb_type in ArbitrageType
            }
        }

