"""Tests for configuration management."""

import pytest
from unittest.mock import patch
from src.core.config import Settings


class TestSettings:
    """Test configuration settings."""

    def test_default_settings(self):
        """Test default configuration values."""
        settings = Settings()

        assert settings.model_name == "gpt-5"
        assert settings.reasoning_effort == "high"
        assert settings.verbosity == "medium"
        assert settings.service_tier == "priority"
        assert settings.max_tokens == 2000
        assert settings.max_search_results == 10
        assert settings.response_timeout == 30
        assert settings.phoenix_project_name == "product-research-agent"

    @patch.dict('os.environ', {}, clear=True)
    def test_graceful_handling_missing_keys(self):
        """Test that missing API keys don't crash the application."""
        # Create settings with no environment variables
        settings = Settings()

        # Should not raise an error and should handle None values gracefully
        assert hasattr(settings, 'openai_api_key')
        assert hasattr(settings, 'tavily_api_key')
        assert hasattr(settings, 'phoenix_api_key')
        assert hasattr(settings, 'anthropic_api_key')

    @patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-openai-key',
        'TAVILY_API_KEY': 'test-tavily-key',
        'PHOENIX_API_KEY': 'test-phoenix-key'
    })
    def test_env_variable_loading(self):
        """Test loading settings from environment variables."""
        settings = Settings()

        assert settings.openai_api_key == 'test-openai-key'
        assert settings.tavily_api_key == 'test-tavily-key'
        assert settings.phoenix_api_key == 'test-phoenix-key'

    def test_model_configuration(self):
        """Test GPT-5 model configuration."""
        settings = Settings()

        assert settings.model_name == "gpt-5"
        assert settings.reasoning_effort in ["minimal", "low", "medium", "high"]
        assert settings.verbosity in ["low", "medium", "high"]
        assert settings.service_tier == "priority"

    def test_application_settings(self):
        """Test application-specific settings."""
        settings = Settings()

        assert isinstance(settings.max_search_results, int)
        assert settings.max_search_results > 0
        assert isinstance(settings.response_timeout, int)
        assert settings.response_timeout > 0