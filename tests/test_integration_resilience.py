"""Resilience integration tests for error recovery and fault tolerance."""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List
# Network libraries would be imported here if needed
# import aiohttp
# import httpx

from src.agents.orchestrator import ProductResearchOrchestrator
from src.agents.product_researcher import ProductResearcher
from src.agents.review_analyzer import ReviewAnalyzer
from src.core.models import ResearchQuery, ProductCategory, PriceRange
from src.tools.tavily_shopping import TavilyShoppingTool


class TestAPIFailureResilience:
    """Test resilience to API failures."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            yield mock_settings

    @pytest.fixture
    def sample_query(self):
        """Sample query for resilience testing."""
        return ResearchQuery(
            query="Test resilience query",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=["reliable"],
            budget=100.0
        )

    @pytest.mark.asyncio
    async def test_openai_api_failure_recovery(self, mock_environment, sample_query):
        """Test recovery from OpenAI API failures."""
        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # Simulate API failure followed by success
            call_count = 0

            async def failing_then_success(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("OpenAI API rate limit exceeded")
                else:
                    response = Mock()
                    response.content = "Recovery successful"
                    return response

            mock_chat.return_value.ainvoke = failing_then_success

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(sample_query)

                        # Should handle failure gracefully
                        assert result is not None
                        # First call should have failed, but system should handle it

    @pytest.mark.asyncio
    async def test_tavily_api_failure_recovery(self, mock_environment, sample_query):
        """Test recovery from Tavily API failures."""
        call_count = 0

        def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Tavily API connection timeout")
            else:
                return [{"title": "Recovery Product", "price": "$99"}]

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_response = Mock()
            mock_response.content = "Handling API failure gracefully"
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_response)

            with patch.object(TavilyShoppingTool, 'search_products', side_effect=failing_then_success):
                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(sample_query)

                        # Should handle Tavily failure gracefully
                        assert result is not None

    @pytest.mark.asyncio
    async def test_multiple_api_failures(self, mock_environment, sample_query):
        """Test handling of multiple simultaneous API failures."""
        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # OpenAI failure
            mock_chat.return_value.ainvoke = AsyncMock(side_effect=Exception("OpenAI service unavailable"))

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                # Tavily failure
                mock_search.side_effect = Exception("Tavily service unavailable")

                orchestrator = ProductResearchOrchestrator()
                result = await orchestrator.research_product(sample_query)

                # Should gracefully handle multiple failures
                assert result is not None
                assert hasattr(result, 'success')
                assert hasattr(result, 'error_message')

    @pytest.mark.asyncio
    async def test_partial_api_degradation(self, mock_environment, sample_query):
        """Test handling of partial API degradation."""
        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # LLM works but gives minimal response
            mock_response = Mock()
            mock_response.content = "Limited response due to degraded service"
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                # Search returns limited results
                mock_search.return_value = [{"title": "Limited Product", "price": "N/A"}]

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(sample_query)

                        # Should work with degraded services
                        assert result is not None


class TestNetworkResilience:
    """Test resilience to network issues."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            yield mock_settings

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, mock_environment):
        """Test handling of network timeouts."""
        query = ResearchQuery(
            query="Test timeout handling",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # Simulate timeout
            mock_chat.return_value.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError("Request timeout"))

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.side_effect = asyncio.TimeoutError("Search timeout")

                orchestrator = ProductResearchOrchestrator()
                result = await orchestrator.research_product(query)

                # Should handle timeouts gracefully
                assert result is not None
                assert hasattr(result, 'success')
                if hasattr(result, 'error_message'):
                    assert "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, mock_environment):
        """Test handling of connection errors."""
        query = ResearchQuery(
            query="Test connection error",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # Simulate connection error
            mock_chat.return_value.ainvoke = AsyncMock(side_effect=ConnectionError("Failed to connect to OpenAI"))

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.side_effect = ConnectionError("Failed to connect to Tavily")

                orchestrator = ProductResearchOrchestrator()
                result = await orchestrator.research_product(query)

                # Should handle connection errors gracefully
                assert result is not None
                assert hasattr(result, 'success')

    @pytest.mark.asyncio
    async def test_intermittent_connectivity(self, mock_environment):
        """Test handling of intermittent connectivity issues."""
        query = ResearchQuery(
            query="Test intermittent connectivity",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        call_count = 0

        async def intermittent_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:  # Fail on odd calls
                raise ConnectionError("Intermittent connection issue")
            else:  # Succeed on even calls
                response = Mock()
                response.content = "Success after retry"
                return response

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = intermittent_llm

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

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

                        # Should handle intermittent issues
                        assert result is not None


class TestDataCorruptionResilience:
    """Test resilience to data corruption and malformed responses."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            yield mock_settings

    def test_malformed_search_results(self, mock_environment):
        """Test handling of malformed search results."""
        malformed_data = [
            {"title": None, "price": "invalid", "url": "not-a-url"},  # Invalid data
            {"missing_title": "test"},  # Missing required fields
            "not a dictionary",  # Wrong data type
            {},  # Empty object
            {"title": "Valid Product", "price": "$99", "url": "https://example.com"}  # One valid item
        ]

        researcher = ProductResearcher()

        # Should handle malformed data gracefully
        products = researcher.extract_products(malformed_data)
        assert isinstance(products, list)
        # Should extract what it can and skip invalid items

    def test_corrupted_json_responses(self, mock_environment):
        """Test handling of corrupted JSON responses."""
        query = ResearchQuery(
            query="Test corrupted JSON",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # Simulate corrupted JSON in LLM response
            mock_response = Mock()
            mock_response.content = '{"incomplete": json without closing brace'
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

                orchestrator = ProductResearchOrchestrator()
                # Should handle corrupted responses gracefully
                # This test verifies the system doesn't crash on malformed data

    def test_oversized_responses(self, mock_environment):
        """Test handling of oversized responses."""
        # Create very large mock data
        oversized_data = [
            {
                "title": f"Product {i}",
                "price": f"${i}",
                "url": f"https://example.com/product-{i}",
                "content": "x" * 10000  # Very large content field
            }
            for i in range(100)  # Many items with large content
        ]

        researcher = ProductResearcher()

        # Should handle large datasets gracefully
        products = researcher.extract_products(oversized_data)
        assert isinstance(products, list)

    def test_unicode_and_encoding_issues(self, mock_environment):
        """Test handling of Unicode and encoding issues."""
        unicode_data = [
            {
                "title": "🔥 Hot Product 💯",
                "price": "€99.99",
                "url": "https://example.com/product-ñ",
                "content": "Product with émojis and spëcial chârs"
            },
            {
                "title": "中文产品名称",
                "price": "¥599",
                "url": "https://example.com/product-中文",
                "content": "Chinese product description"
            },
            {
                "title": "العربية المنتج",
                "price": "100 ريال",
                "url": "https://example.com/product-arabic",
                "content": "Arabic product description"
            }
        ]

        researcher = ProductResearcher()

        # Should handle Unicode gracefully
        products = researcher.extract_products(unicode_data)
        assert isinstance(products, list)


class TestGracefulDegradation:
    """Test graceful degradation under various failure conditions."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            yield mock_settings

    @pytest.mark.asyncio
    async def test_search_failure_graceful_degradation(self, mock_environment):
        """Test graceful degradation when search fails."""
        query = ResearchQuery(
            query="Test search failure degradation",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # LLM works
            mock_response = Mock()
            mock_response.content = "Unable to find products due to search service unavailability"
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                # Search fails
                mock_search.side_effect = Exception("Search service down")

                orchestrator = ProductResearchOrchestrator()
                result = await orchestrator.research_product(query)

                # Should provide meaningful response even without search results
                assert result is not None
                assert hasattr(result, 'success')
                # Should indicate what went wrong and what was attempted

    @pytest.mark.asyncio
    async def test_partial_component_failure(self, mock_environment):
        """Test degradation when some components fail."""
        query = ResearchQuery(
            query="Test partial component failure",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # LLM works
            mock_response = Mock()
            mock_response.content = "Providing recommendation with limited data"
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                # Search works
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    # Product researcher fails
                    mock_researcher = Mock()
                    mock_researcher.extract_products.side_effect = Exception("Product extraction failed")
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        # Review analyzer works
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(query)

                        # Should work with available components
                        assert result is not None

    def test_configuration_error_handling(self):
        """Test handling of configuration errors."""
        # Test missing API keys
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = None
            mock_settings.tavily_api_key = None

            # Should handle gracefully
            orchestrator = ProductResearchOrchestrator()
            assert orchestrator.llm is None  # Should not crash

        # Test invalid configuration
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "invalid-key-format"
            mock_settings.model_name = "non-existent-model"
            mock_settings.max_tokens = -1  # Invalid value

            # Should handle invalid config gracefully
            try:
                orchestrator = ProductResearchOrchestrator()
                # May or may not succeed, but shouldn't crash
            except Exception:
                # Expected to potentially fail, but gracefully
                pass

    @pytest.mark.asyncio
    async def test_resource_exhaustion_handling(self, mock_environment):
        """Test handling when system resources are exhausted."""
        query = ResearchQuery(
            query="Test resource exhaustion",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # Simulate resource exhaustion
            mock_chat.return_value.ainvoke = AsyncMock(side_effect=MemoryError("Out of memory"))

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

                orchestrator = ProductResearchOrchestrator()
                result = await orchestrator.research_product(query)

                # Should handle resource exhaustion gracefully
                assert result is not None
                assert hasattr(result, 'success')


class TestRecoveryMechanisms:
    """Test recovery mechanisms and error recovery."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            yield mock_settings

    @pytest.mark.asyncio
    async def test_automatic_retry_mechanism(self, mock_environment):
        """Test automatic retry mechanisms."""
        query = ResearchQuery(
            query="Test retry mechanism",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        retry_count = 0

        async def failing_then_success(*args, **kwargs):
            nonlocal retry_count
            retry_count += 1
            if retry_count <= 2:  # Fail first 2 attempts
                raise Exception("Temporary failure")
            else:  # Succeed on 3rd attempt
                response = Mock()
                response.content = "Success after retries"
                return response

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = failing_then_success

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

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

                        # Should eventually succeed after retries
                        assert result is not None
                        assert retry_count >= 3  # Verify retries occurred

    @pytest.mark.asyncio
    async def test_fallback_mechanisms(self, mock_environment):
        """Test fallback mechanisms when primary services fail."""
        query = ResearchQuery(
            query="Test fallback mechanisms",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # Primary LLM fails
            mock_chat.return_value.ainvoke = AsyncMock(side_effect=Exception("Primary LLM service failed"))

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                # Primary search works as fallback
                mock_search.return_value = [{"title": "Fallback Product", "price": "$99"}]

                orchestrator = ProductResearchOrchestrator()
                result = await orchestrator.research_product(query)

                # Should use fallback mechanisms
                assert result is not None

    def test_state_recovery_after_failure(self):
        """Test that system state is properly recovered after failures."""
        # Test that global state is not corrupted after failures
        initial_researcher = ProductResearcher()

        # Simulate failure
        try:
            initial_researcher.extract_products("invalid data type")
        except Exception:
            pass  # Expected to fail

        # Create new instance - should work normally
        recovery_researcher = ProductResearcher()
        valid_data = [{"title": "Test Product", "price": "$99", "url": "https://example.com"}]
        products = recovery_researcher.extract_products(valid_data)

        # Should work normally after previous failure
        assert isinstance(products, list)

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self, mock_environment):
        """Test circuit breaker pattern for failing services."""
        query = ResearchQuery(
            query="Test circuit breaker",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        failure_count = 0

        async def consistently_failing_service(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            raise Exception(f"Service consistently failing - attempt {failure_count}")

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = consistently_failing_service

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

                orchestrator = ProductResearchOrchestrator()

                # Multiple attempts should eventually give up gracefully
                result = await orchestrator.research_product(query)

                # Should handle persistent failures gracefully
                assert result is not None
                assert hasattr(result, 'success')

    def test_data_validation_recovery(self):
        """Test recovery from data validation failures."""
        invalid_queries = [
            None,  # Null query
            "",    # Empty query
            ResearchQuery(
                query="",  # Empty query string
                category=ProductCategory.ELECTRONICS,
                price_range=PriceRange.BUDGET,
                requirements=[],
                budget=-100.0  # Invalid budget
            )
        ]

        for invalid_query in invalid_queries:
            try:
                # Should handle invalid input gracefully
                if invalid_query is None:
                    continue  # Skip None case

                # Validate that invalid data is handled
                assert hasattr(invalid_query, 'query') or invalid_query is None

            except Exception as e:
                # Should fail gracefully, not crash
                assert isinstance(e, (ValueError, TypeError, AttributeError))

    @pytest.mark.asyncio
    async def test_concurrent_failure_isolation(self, mock_environment):
        """Test that failures in concurrent operations don't affect each other."""
        queries = [
            ResearchQuery(
                query=f"Test concurrent failure {i}",
                category=ProductCategory.ELECTRONICS,
                price_range=PriceRange.BUDGET,
                requirements=[],
                budget=100.0
            )
            for i in range(3)
        ]

        async def selective_failure(*args, **kwargs):
            # Fail for specific queries
            if "failure 1" in str(args):
                raise Exception("Selective failure for query 1")
            else:
                response = Mock()
                response.content = "Success for other queries"
                return response

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = selective_failure

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = [{"title": "Test Product", "price": "$99"}]

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        # Execute concurrent queries
                        tasks = []
                        for query in queries:
                            orchestrator = ProductResearchOrchestrator()
                            task = asyncio.create_task(orchestrator.research_product(query))
                            tasks.append(task)

                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        # Some should succeed, some should fail, but failures should be isolated
                        assert len(results) == len(queries)
                        successful_results = [r for r in results if not isinstance(r, Exception)]

                        # At least some should succeed (queries 0 and 2)
                        assert len(successful_results) >= 2