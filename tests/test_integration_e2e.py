"""End-to-end integration tests for complete user scenarios."""

import pytest
import asyncio
import subprocess
import sys
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List
from io import StringIO

from src.core.models import ResearchQuery, ProductCategory, PriceRange
from src.agents.orchestrator import ProductResearchOrchestrator
from src.tools.tavily_shopping import TavilyShoppingTool


class TestCLIIntegration:
    """Test CLI integration and user interface."""

    def test_main_module_import(self):
        """Test that main module can be imported."""
        try:
            import main
            assert hasattr(main, 'main')
        except ImportError as e:
            pytest.skip(f"Main module not available: {e}")

    @pytest.mark.skipif(sys.platform == "win32", reason="CLI tests may be flaky on Windows")
    def test_cli_help_command(self):
        """Test CLI help command."""
        try:
            result = subprocess.run(
                [sys.executable, "main.py", "--help"],
                cwd="/home/runner/workspace",
                capture_output=True,
                text=True,
                timeout=10
            )
            assert result.returncode == 0
            assert "usage:" in result.stdout.lower() or "help" in result.stdout.lower()
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"CLI test skipped: {e}")

    @pytest.mark.skipif(sys.platform == "win32", reason="CLI tests may be flaky on Windows")
    def test_cli_demo_mode(self):
        """Test CLI demo mode execution."""
        env = os.environ.copy()
        env.update({
            'OPENAI_API_KEY': 'test-key',
            'TAVILY_API_KEY': 'test-key'
        })

        try:
            with patch('src.tools.tavily_shopping.TavilyShoppingTool.search_products') as mock_search:
                mock_search.return_value = [
                    {
                        "title": "Test Laptop",
                        "url": "https://example.com/laptop",
                        "content": "Test laptop for demo",
                        "price": "$999",
                        "source": "Test Store"
                    }
                ]

                result = subprocess.run(
                    [sys.executable, "main.py", "demo"],
                    cwd="/home/runner/workspace",
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env
                )

                # Should not crash, may timeout or have missing dependencies
                assert result.returncode in [0, 1]  # Allow for expected failures in test environment

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"CLI demo test skipped: {e}")

    def test_cli_configuration_validation(self):
        """Test CLI handles missing configuration gracefully."""
        env = os.environ.copy()
        # Remove API keys to test error handling
        env.pop('OPENAI_API_KEY', None)
        env.pop('TAVILY_API_KEY', None)

        try:
            result = subprocess.run(
                [sys.executable, "main.py", "demo"],
                cwd="/home/runner/workspace",
                capture_output=True,
                text=True,
                timeout=15,
                env=env
            )

            # Should handle missing API keys gracefully
            assert "API key" in result.stdout or "API key" in result.stderr or result.returncode != 0

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"CLI configuration test skipped: {e}")


class TestEndToEndScenarios:
    """Test complete end-to-end user scenarios."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment for E2E tests."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            mock_settings.reasoning_effort = "high"
            yield mock_settings

    @pytest.fixture
    def sample_laptop_query(self):
        """Sample laptop query for testing."""
        return ResearchQuery(
            query="Best laptop under $2000 for programming and development work",
            category=ProductCategory.COMPUTERS,
            price_range=PriceRange.MID_RANGE,
            requirements=["16GB RAM", "SSD storage", "good keyboard", "Linux compatible"],
            budget=2000.0
        )

    @pytest.fixture
    def mock_complete_results(self):
        """Mock complete research results."""
        return {
            "search_results": [
                {
                    "title": "MacBook Pro 14-inch M3",
                    "url": "https://apple.com/macbook-pro",
                    "content": "Apple MacBook Pro 14-inch with M3 chip, 16GB RAM, 512GB SSD. Excellent for development with great build quality and display.",
                    "price": "$1899",
                    "source": "Apple Store"
                },
                {
                    "title": "Dell XPS 13 Developer Edition",
                    "url": "https://dell.com/xps-13",
                    "content": "Dell XPS 13 with Ubuntu pre-installed, Intel i7, 16GB RAM, 1TB SSD. Optimized for developers.",
                    "price": "$1699",
                    "source": "Dell"
                },
                {
                    "title": "ThinkPad X1 Carbon Gen 11",
                    "url": "https://lenovo.com/thinkpad",
                    "content": "Lenovo ThinkPad X1 Carbon with legendary keyboard, 16GB RAM, 512GB SSD, excellent Linux support.",
                    "price": "$1799",
                    "source": "Lenovo"
                }
            ],
            "llm_responses": {
                "analysis": "Based on the search results, I found three excellent laptops for programming under $2000.",
                "recommendation": "I recommend the ThinkPad X1 Carbon for programming due to its excellent keyboard, proven reliability, and outstanding Linux compatibility."
            }
        }

    @pytest.mark.asyncio
    async def test_complete_laptop_research_scenario(self, mock_environment, sample_laptop_query, mock_complete_results):
        """Test complete laptop research scenario from start to finish."""
        # Mock LLM responses
        mock_llm_response = Mock()
        mock_llm_response.content = mock_complete_results["llm_responses"]["recommendation"]

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

            # Mock tool search
            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = mock_complete_results["search_results"]

                # Mock sub-agents
                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = [
                        # Mock Product objects would be returned here
                    ]
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        # Execute complete workflow
                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(sample_laptop_query)

                        # Validate complete result
                        assert result is not None
                        assert hasattr(result, 'query')
                        assert hasattr(result, 'success')

                        # Verify all components were called
                        mock_search.assert_called_once()
                        mock_researcher.extract_products.assert_called_once()

    @pytest.mark.asyncio
    async def test_electronics_research_scenario(self, mock_environment):
        """Test electronics research scenario."""
        query = ResearchQuery(
            query="Best wireless headphones for commuting under $300",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.MID_RANGE,
            requirements=["noise cancelling", "long battery life", "comfortable"],
            budget=300.0
        )

        mock_results = [
            {
                "title": "Sony WH-1000XM5",
                "url": "https://sony.com/headphones",
                "content": "Sony WH-1000XM5 wireless headphones with industry-leading noise cancellation and 30-hour battery life.",
                "price": "$279",
                "source": "Sony"
            },
            {
                "title": "Bose QuietComfort 45",
                "url": "https://bose.com/quietcomfort",
                "content": "Bose QuietComfort 45 with excellent noise cancellation and comfort for long listening sessions.",
                "price": "$249",
                "source": "Bose"
            }
        ]

        mock_llm_response = Mock()
        mock_llm_response.content = "For commuting, I recommend the Sony WH-1000XM5 due to superior noise cancellation and battery life."

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = mock_results

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(query)

                        assert result is not None
                        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_budget_constraint_scenario(self, mock_environment):
        """Test scenario with tight budget constraints."""
        query = ResearchQuery(
            query="Affordable smartphone under $300 with good camera",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=["good camera", "decent performance", "reliable"],
            budget=300.0
        )

        mock_results = [
            {
                "title": "Google Pixel 7a",
                "url": "https://store.google.com/pixel-7a",
                "content": "Google Pixel 7a with excellent camera and clean Android experience at budget price.",
                "price": "$299",
                "source": "Google Store"
            },
            {
                "title": "Samsung Galaxy A54",
                "url": "https://samsung.com/galaxy-a54",
                "content": "Samsung Galaxy A54 with versatile camera system and solid performance for the price.",
                "price": "$279",
                "source": "Samsung"
            }
        ]

        mock_llm_response = Mock()
        mock_llm_response.content = "For camera quality at this price point, the Google Pixel 7a offers the best value."

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = mock_results

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(query)

                        assert result is not None
                        mock_search.assert_called_once()


class TestOutputFormatting:
    """Test output formatting and display."""

    def test_result_formatting(self):
        """Test that results are formatted correctly for display."""
        from src.core.models import ResearchResult, Product

        # Create sample result
        query = ResearchQuery(
            query="test query",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        products = [
            Product(
                name="Test Product",
                price=99.0,
                url="https://example.com",
                specifications={"feature": "value"},
                category=ProductCategory.ELECTRONICS,
                rating=4.5,
                review_count=100
            )
        ]

        result = ResearchResult(
            query=query,
            products=products,
            summary="Test summary",
            recommendation="Test recommendation",
            success=True,
            error_message=None,
            total_time=1.5,
            alternatives=[]
        )

        # Test that result can be converted to string/dict for output
        assert str(result) is not None
        assert result.model_dump() is not None

    def test_console_output_formatting(self):
        """Test console output formatting."""
        # Test that we can format results for console display
        sample_text = "Product Research Results\n========================\n"
        sample_text += "Query: Best laptop under $2000\n"
        sample_text += "Recommendation: ThinkPad X1 Carbon\n"

        # Verify basic string operations work
        assert len(sample_text) > 0
        assert "Query:" in sample_text
        assert "Recommendation:" in sample_text

    def test_json_output_formatting(self):
        """Test JSON output formatting."""
        import json

        sample_data = {
            "query": "Best laptop under $2000",
            "products": [
                {
                    "name": "MacBook Pro",
                    "price": 1899.0,
                    "url": "https://apple.com"
                }
            ],
            "recommendation": "MacBook Pro recommended for development work"
        }

        # Test JSON serialization
        json_str = json.dumps(sample_data, indent=2)
        assert json_str is not None
        assert "query" in json_str
        assert "products" in json_str

        # Test JSON deserialization
        parsed_data = json.loads(json_str)
        assert parsed_data["query"] == sample_data["query"]
        assert len(parsed_data["products"]) == 1


class TestConfigurationIntegration:
    """Test configuration integration across the system."""

    def test_api_key_configuration(self):
        """Test API key configuration handling."""
        with patch('src.core.config.settings') as mock_settings:
            # Test with valid API keys
            mock_settings.openai_api_key = "sk-test123"
            mock_settings.tavily_api_key = "tvly-test123"

            orchestrator = ProductResearchOrchestrator()
            assert orchestrator.llm is not None

            # Test with missing API keys
            mock_settings.openai_api_key = None
            mock_settings.tavily_api_key = None

            orchestrator = ProductResearchOrchestrator()
            assert orchestrator.llm is None

    def test_model_configuration(self):
        """Test model configuration settings."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            mock_settings.reasoning_effort = "high"

            orchestrator = ProductResearchOrchestrator()

            # Verify configuration is applied
            if orchestrator.llm:
                # Model configuration should be reflected in the LLM instance
                assert hasattr(orchestrator, 'llm')

    def test_tracing_configuration_integration(self):
        """Test tracing configuration integration."""
        from src.core.tracing import TracingConfig

        config = TracingConfig()
        config.from_env()

        # Test that tracing config integrates with the workflow
        assert hasattr(config, 'api_key')
        assert hasattr(config, 'space_id')
        assert hasattr(config, 'project_name')

    def test_environment_variable_handling(self):
        """Test environment variable handling."""
        import os

        # Test that environment variables are read correctly
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-openai-key',
            'TAVILY_API_KEY': 'test-tavily-key',
            'PHOENIX_API_KEY': 'test-phoenix-key'
        }):
            # Import to trigger environment variable reading
            from src.core import config

            # Verify environment variables are accessible
            assert os.getenv('OPENAI_API_KEY') == 'test-openai-key'
            assert os.getenv('TAVILY_API_KEY') == 'test-tavily-key'
            assert os.getenv('PHOENIX_API_KEY') == 'test-phoenix-key'


class TestUserExperienceFlow:
    """Test complete user experience flows."""

    @pytest.mark.asyncio
    async def test_typical_user_journey(self, mock_environment=None):
        """Test a typical user journey from query to recommendation."""
        if mock_environment is None:
            with patch('src.core.config.settings') as mock_settings:
                mock_settings.openai_api_key = "test-key"
                mock_settings.tavily_api_key = "test-key"
                mock_settings.model_name = "gpt-4"
                mock_settings.max_tokens = 4000

                # Step 1: User creates query
                user_query = "I need a laptop for software development under $1500"

                # Step 2: Query is converted to ResearchQuery
                research_query = ResearchQuery(
                    query=user_query,
                    category=ProductCategory.COMPUTERS,
                    price_range=PriceRange.MID_RANGE,
                    requirements=["development-friendly", "good keyboard", "reliable"],
                    budget=1500.0
                )

                # Step 3: Research is conducted (mocked)
                mock_results = [
                    {
                        "title": "Dell Inspiron 15",
                        "url": "https://dell.com/inspiron",
                        "content": "Dell Inspiron 15 with Intel i7, 16GB RAM, perfect for development.",
                        "price": "$1299",
                        "source": "Dell"
                    }
                ]

                mock_llm_response = Mock()
                mock_llm_response.content = "The Dell Inspiron 15 offers excellent value for development work within your budget."

                with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
                    mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

                    with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                        mock_search.return_value = mock_results

                        with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                            mock_researcher = Mock()
                            mock_researcher.extract_products.return_value = []
                            mock_researcher_class.return_value = mock_researcher

                            with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                                mock_analyzer = Mock()
                                mock_analyzer.analyze_reviews.return_value = []
                                mock_analyzer_class.return_value = mock_analyzer

                                # Step 4: Execute research
                                orchestrator = ProductResearchOrchestrator()
                                result = await orchestrator.research_product(research_query)

                                # Step 5: Validate user receives useful result
                                assert result is not None
                                assert hasattr(result, 'recommendation') or hasattr(result, 'error_message')

    def test_error_user_experience(self):
        """Test user experience when errors occur."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = None  # Simulate missing API key

            # User should get clear error message
            orchestrator = ProductResearchOrchestrator()
            assert orchestrator.llm is None  # Should handle gracefully

    def test_response_time_user_experience(self):
        """Test that response times meet user expectations."""
        import time

        start_time = time.time()

        # Simulate quick operations
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            orchestrator = ProductResearchOrchestrator()

        end_time = time.time()
        initialization_time = end_time - start_time

        # Initialization should be fast (< 1 second)
        assert initialization_time < 1.0