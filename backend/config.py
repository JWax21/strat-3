"""Configuration management for the trading platform."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Polymarket Configuration
    polymarket_gamma_api_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_api_url: str = "https://clob.polymarket.com"
    polymarket_data_api_url: str = "https://data-api.polymarket.com"
    
    # Kalshi Configuration
    kalshi_api_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    
    # Rate Limiting (requests per minute)
    polymarket_rate_limit: int = 60
    kalshi_rate_limit: int = 10  # Very conservative for Kalshi
    
    # Arbitrage Settings
    min_price_difference_percent: float = 0.0  # Show all matches for testing
    match_threshold: float = 0.01  # Very low threshold for testing market pulls
    
    # Server Config
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

