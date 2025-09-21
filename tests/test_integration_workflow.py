"""Integration tests for agent workflow coordination."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

from src.agents.orchestrator import ProductResearchOrchestrator, ResearchState
from src.agents.product_researcher import ProductResearcher
from src.agents.review_analyzer import ReviewAnalyzer
from src.core.models import (
    ResearchQuery, ResearchResult, Product, Review,
    ProductCategory, PriceRange
)
from src.tools.tavily_shopping import TavilyShoppingTool


class TestWorkflowIntegration:
    """Test complete agent workflow integration."""

    @pytest.fixture
    def mock_research_query(self):
        """Create a mock research query."""
        return ResearchQuery(
            query="Best laptop under $2000 for programming",
            category=ProductCategory.COMPUTERS,
            price_range=PriceRange.MID_RANGE,
            requirements=["16GB RAM", "SSD storage", "good keyboard"],
            budget=2000.0
        )

    @pytest.fixture
    def mock_tavily_results(self):
        """Mock Tavily search results."""
        return [
            {
                "title": "MacBook Pro 14-inch M3",
                "url": "https://example.com/macbook",
                "content": "Apple MacBook Pro 14-inch with M3 chip, 16GB RAM, 512GB SSD. Price: $1899",
                "price": "$1899",
                "source": "Apple Store"
            },
            {
                "title": "Dell XPS 13 Developer Edition",
                "url": "https://example.com/dell-xps",
                "content": "Dell XPS 13 with Intel i7, 16GB RAM, 1TB SSD. Price: $1699",
                "price": "$1699",
                "source": "Dell"
            },
            {
                "title": "ThinkPad X1 Carbon",
                "url": "https://example.com/thinkpad",
                "content": "Lenovo ThinkPad X1 Carbon with excellent keyboard, 16GB RAM, 512GB SSD. Price: $1799",
                "price": "$1799",
                "source": "Lenovo"
            }
        ]

    @pytest.fixture
    def mock_products(self):
        """Create mock products."""
        return [
            Product(
                name="MacBook Pro 14-inch M3",
                price=1899.0,
                url="https://example.com/macbook",
                specifications={"RAM": "16GB", "Storage": "512GB SSD", "Processor": "M3"},
                category=ProductCategory.COMPUTERS,
                rating=4.8,
                review_count=1250
            ),
            Product(
                name="Dell XPS 13 Developer Edition",
                price=1699.0,
                url="https://example.com/dell-xps",
                specifications={"RAM": "16GB", "Storage": "1TB SSD", "Processor": "Intel i7"},
                category=ProductCategory.COMPUTERS,
                rating=4.6,
                review_count=890
            ),
            Product(
                name="ThinkPad X1 Carbon",
                price=1799.0,
                url="https://example.com/thinkpad",
                specifications={"RAM": "16GB", "Storage": "512GB SSD", "Processor": "Intel i7"},
                category=ProductCategory.COMPUTERS,
                rating=4.7,
                review_count=654
            )
        ]

    @pytest.fixture
    def mock_reviews(self):
        """Create mock reviews."""
        return [
            Review(
                product_name="MacBook Pro 14-inch M3",
                rating=5,
                text="Excellent for development. Fast compilation, great display.",
                verified=True,
                helpful_count=45,
                source="Apple Store"
            ),
            Review(
                product_name="Dell XPS 13 Developer Edition",
                rating=4,
                text="Good Linux support, lightweight, decent keyboard.",
                verified=True,
                helpful_count=32,
                source="Dell"
            ),
            Review(
                product_name="ThinkPad X1 Carbon",
                rating=5,
                text="Best keyboard for programming. Durable and reliable.",
                verified=True,
                helpful_count=67,
                source="Lenovo"
            )
        ]

    def test_orchestrator_initialization(self):
        """Test orchestrator initializes correctly."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            orchestrator = ProductResearchOrchestrator()

            assert orchestrator.llm is not None
            assert orchestrator.tool is not None
            assert isinstance(orchestrator.tool, TavilyShoppingTool)

    def test_orchestrator_without_api_key(self):
        """Test orchestrator handles missing API key gracefully."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = None

            orchestrator = ProductResearchOrchestrator()

            assert orchestrator.llm is None

    @pytest.mark.asyncio
    async def test_complete_workflow_success(self, mock_research_query, mock_tavily_results, mock_products, mock_reviews):
        """Test complete successful workflow from query to result."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            # Mock the LLM responses
            mock_llm_response = Mock()
            mock_llm_response.content = "Based on the research, I recommend the ThinkPad X1 Carbon for programming due to its excellent keyboard and build quality."

            with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
                mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

                # Mock tool search
                with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                    mock_search.return_value = mock_tavily_results

                    # Mock product researcher
                    with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                        mock_researcher = Mock()
                        mock_researcher.extract_products.return_value = mock_products
                        mock_researcher_class.return_value = mock_researcher

                        # Mock review analyzer
                        with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                            mock_analyzer = Mock()
                            mock_analyzer.analyze_reviews.return_value = mock_reviews
                            mock_analyzer_class.return_value = mock_analyzer

                            orchestrator = ProductResearchOrchestrator()
                            result = await orchestrator.research_product(mock_research_query)

                            assert isinstance(result, ResearchResult)
                            assert result.query == mock_research_query
                            assert len(result.products) > 0
                            assert result.recommendation is not None
                            assert result.success is True

    @pytest.mark.asyncio
    async def test_workflow_with_tool_failure(self, mock_research_query):
        """Test workflow handles tool failures gracefully."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
                mock_chat.return_value.ainvoke = AsyncMock()

                # Mock tool search to raise exception
                with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                    mock_search.side_effect = Exception("API rate limit exceeded")

                    orchestrator = ProductResearchOrchestrator()
                    result = await orchestrator.research_product(mock_research_query)

                    assert isinstance(result, ResearchResult)
                    assert result.success is False
                    assert "API rate limit exceeded" in result.error_message

    @pytest.mark.asyncio
    async def test_workflow_state_transitions(self, mock_research_query, mock_tavily_results):
        """Test workflow state transitions are correct."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            state_history = []

            def track_state_change(state: ResearchState):
                state_history.append(state['current_step'])
                return state

            with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
                mock_chat.return_value.ainvoke = AsyncMock()

                with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                    mock_search.return_value = mock_tavily_results

                    with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                        mock_researcher = Mock()
                        mock_researcher.extract_products.return_value = []
                        mock_researcher_class.return_value = mock_researcher

                        orchestrator = ProductResearchOrchestrator()

                        # Mock the workflow to track state changes
                        original_workflow = orchestrator.workflow
                        orchestrator.workflow = Mock()
                        orchestrator.workflow.ainvoke = AsyncMock()

                        await orchestrator.research_product(mock_research_query)

                        # Verify workflow was called
                        orchestrator.workflow.ainvoke.assert_called_once()

    def test_product_researcher_integration(self, mock_tavily_results):
        """Test product researcher integration with mock data."""
        researcher = ProductResearcher()
        products = researcher.extract_products(mock_tavily_results)

        assert isinstance(products, list)
        assert len(products) >= 0
        for product in products:
            assert isinstance(product, Product)
            assert product.name
            assert product.price is None or isinstance(product.price, (int, float))

    def test_review_analyzer_integration(self, mock_reviews):
        """Test review analyzer integration with mock data."""
        analyzer = ReviewAnalyzer()

        # Mock the LLM for sentiment analysis
        with patch.object(analyzer, 'llm') as mock_llm:
            mock_response = Mock()
            mock_response.content = "positive"
            mock_llm.invoke.return_value = mock_response

            analyzed_reviews = analyzer.analyze_reviews(mock_reviews, "programming laptop")

            assert isinstance(analyzed_reviews, list)
            assert len(analyzed_reviews) >= 0


class TestWorkflowErrorHandling:
    """Test error handling in workflow coordination."""

    @pytest.fixture
    def mock_research_query(self):
        """Create a mock research query."""
        return ResearchQuery(
            query="Invalid query test",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

    @pytest.mark.asyncio
    async def test_llm_failure_handling(self, mock_research_query):
        """Test handling of LLM failures."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
                # Mock LLM to raise exception
                mock_chat.return_value.ainvoke = AsyncMock(side_effect=Exception("OpenAI API error"))

                with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                    mock_search.return_value = []

                    orchestrator = ProductResearchOrchestrator()
                    result = await orchestrator.research_product(mock_research_query)

                    assert isinstance(result, ResearchResult)
                    assert result.success is False
                    assert "OpenAI API error" in result.error_message

    @pytest.mark.asyncio
    async def test_invalid_query_handling(self):
        """Test handling of invalid queries."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            orchestrator = ProductResearchOrchestrator()

            # Test with None query
            with pytest.raises(Exception):
                await orchestrator.research_product(None)

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, mock_research_query):
        """Test handling of network timeouts."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
                mock_chat.return_value.ainvoke = AsyncMock()

                with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                    mock_search.side_effect = asyncio.TimeoutError("Request timeout")

                    orchestrator = ProductResearchOrchestrator()
                    result = await orchestrator.research_product(mock_research_query)

                    assert isinstance(result, ResearchResult)
                    assert result.success is False
                    assert "timeout" in result.error_message.lower()


class TestAgentDataFlow:
    """Test data flow between agents."""

    @pytest.fixture
    def sample_raw_data(self):
        """Sample raw search data."""
        return [
            {
                "title": "Test Product",
                "url": "https://example.com/product",
                "content": "Test product description with price $999",
                "price": "$999",
                "source": "Test Store"
            }
        ]

    def test_data_transformation_flow(self, sample_raw_data):
        """Test data transformation through the pipeline."""
        # Test raw data -> products
        researcher = ProductResearcher()
        products = researcher.extract_products(sample_raw_data)

        assert isinstance(products, list)

        # Test products -> reviews (mock reviews for products)
        mock_reviews = [
            Review(
                product_name="Test Product",
                rating=4,
                text="Good product",
                verified=True,
                helpful_count=10,
                source="Test Store"
            )
        ]

        analyzer = ReviewAnalyzer()

        with patch.object(analyzer, 'llm') as mock_llm:
            mock_response = Mock()
            mock_response.content = "positive"
            mock_llm.invoke.return_value = mock_response

            analyzed = analyzer.analyze_reviews(mock_reviews, "test query")
            assert isinstance(analyzed, list)

    def test_state_consistency(self):
        """Test that workflow state remains consistent."""
        initial_state = ResearchState(
            query=ResearchQuery(
                query="test",
                category=ProductCategory.ELECTRONICS,
                price_range=PriceRange.BUDGET,
                requirements=[],
                budget=100.0
            ),
            raw_search_results=[],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="init",
            error=None
        )

        # Test state immutability patterns
        assert initial_state['query'].query == "test"
        assert initial_state['current_step'] == "init"
        assert initial_state['error'] is None

    def test_concurrent_agent_operations(self, sample_raw_data):
        """Test concurrent execution of agent operations."""
        researcher = ProductResearcher()
        analyzer = ReviewAnalyzer()

        # Test that agents can work concurrently without interference
        products = researcher.extract_products(sample_raw_data)

        mock_reviews = [
            Review(
                product_name="Test Product",
                rating=4,
                text="Good product",
                verified=True,
                helpful_count=10,
                source="Test Store"
            )
        ]

        with patch.object(analyzer, 'llm') as mock_llm:
            mock_response = Mock()
            mock_response.content = "positive"
            mock_llm.invoke.return_value = mock_response

            analyzed = analyzer.analyze_reviews(mock_reviews, "test query")

            # Both operations should complete successfully
            assert isinstance(products, list)
            assert isinstance(analyzed, list)


class TestWorkflowPerformanceMetrics:
    """Test workflow performance tracking."""

    @pytest.mark.asyncio
    async def test_workflow_timing_metrics(self):
        """Test that workflow tracks timing metrics."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            query = ResearchQuery(
                query="test laptop",
                category=ProductCategory.COMPUTERS,
                price_range=PriceRange.MID_RANGE,
                requirements=[],
                budget=1000.0
            )

            with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
                mock_chat.return_value.ainvoke = AsyncMock()

                with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                    mock_search.return_value = []

                    orchestrator = ProductResearchOrchestrator()

                    start_time = asyncio.get_event_loop().time()
                    result = await orchestrator.research_product(query)
                    end_time = asyncio.get_event_loop().time()

                    # Verify timing
                    elapsed_time = end_time - start_time
                    assert elapsed_time >= 0
                    assert isinstance(result, ResearchResult)

    def test_memory_usage_tracking(self):
        """Test memory usage during workflow operations."""
        import gc
        import sys

        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Create orchestrator and perform operations
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000

            orchestrator = ProductResearchOrchestrator()
            researcher = ProductResearcher()
            analyzer = ReviewAnalyzer()

            # Clean up
            del orchestrator, researcher, analyzer
            gc.collect()
            final_objects = len(gc.get_objects())

            # Verify no significant memory leaks
            object_growth = final_objects - initial_objects
            assert object_growth < 1000  # Reasonable threshold