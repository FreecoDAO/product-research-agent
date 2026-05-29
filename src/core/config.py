"""Configuration management for the Product Research Agent."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Keys
    openai_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    tavily_mcp_url: Optional[str] = None
    phoenix_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # LLM Model Settings — defaults to Novita AI DeepSeek V4 Flash
    openai_base_url: Optional[str] = "https://api.novita.ai/openai"
    model_name: str = "deepseek/deepseek-v4-flash"
    reasoning_effort: str = "high"  # minimal, low, medium, high
    verbosity: str = "medium"  # low, medium, high
    service_tier: str = "default"  # for faster responses
    max_tokens: int = 4096
    
    # Application Settings
    max_search_results: int = 10
    response_timeout: int = 30
    
    # Phoenix Observability
    phoenix_project_name: str = "product-research-agent"
    phoenix_space_id: Optional[str] = None
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }


# Global settings instance
settings = Settings()