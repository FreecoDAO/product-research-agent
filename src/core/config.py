"""Configuration management for the Product Research Agent."""

import os
from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Keys
    openai_api_key: str
    tavily_api_key: str
    phoenix_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # GPT-5 Model Settings
    model_name: str = "gpt-5"
    reasoning_effort: str = "high"  # minimal, low, medium, high
    verbosity: str = "medium"  # low, medium, high
    service_tier: str = "priority"  # for faster responses
    max_tokens: int = 2000
    
    # Application Settings
    max_search_results: int = 10
    response_timeout: int = 30
    
    # Phoenix Observability
    phoenix_project_name: str = "product-research-agent"
    phoenix_space_id: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()