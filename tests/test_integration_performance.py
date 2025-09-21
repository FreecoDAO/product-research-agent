"""Performance integration tests for the Product Research Agent."""

import pytest
import asyncio
import time
import psutil
import gc
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.agents.orchestrator import ProductResearchOrchestrator
from src.agents.product_researcher import ProductResearcher
from src.agents.review_analyzer import ReviewAnalyzer
from src.core.models import ResearchQuery, ProductCategory, PriceRange, Product, Review
from src.tools.tavily_shopping import TavilyShoppingTool


class TestResponseTimePerformance:
    """Test response time performance requirements."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment for performance tests."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            yield mock_settings

    @pytest.fixture
    def sample_query(self):
        """Sample query for performance testing."""
        return ResearchQuery(
            query="Best laptop under $2000 for programming",
            category=ProductCategory.COMPUTERS,
            price_range=PriceRange.MID_RANGE,
            requirements=["16GB RAM", "SSD storage"],
            budget=2000.0
        )

    @pytest.fixture
    def mock_fast_responses(self):
        """Mock responses optimized for speed testing."""
        return {
            "search_results": [
                {
                    "title": f"Laptop {i}",
                    "url": f"https://example.com/laptop-{i}",
                    "content": f"Laptop {i} description with price ${1000 + i * 100}",
                    "price": f"${1000 + i * 100}",
                    "source": f"Store {i}"
                }
                for i in range(3)  # Small dataset for speed
            ],
            "llm_response": "Quick recommendation based on search results."
        }

    @pytest.mark.asyncio
    async def test_target_response_time_under_30_seconds(self, mock_environment, sample_query, mock_fast_responses):
        """Test that research completes within 30-second target."""
        mock_llm_response = Mock()
        mock_llm_response.content = mock_fast_responses["llm_response"]

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            # Fast LLM response
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                # Fast search response
                mock_search.return_value = mock_fast_responses["search_results"]

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        orchestrator = ProductResearchOrchestrator()

                        start_time = time.time()
                        result = await orchestrator.research_product(sample_query)
                        end_time = time.time()

                        elapsed_time = end_time - start_time

                        # Should complete within 30 seconds (target requirement)
                        assert elapsed_time < 30.0, f"Research took {elapsed_time:.2f}s, exceeds 30s target"
                        assert result is not None

    @pytest.mark.asyncio
    async def test_initialization_performance(self, mock_environment):
        """Test that component initialization is fast."""
        start_time = time.time()

        # Initialize all components
        orchestrator = ProductResearchOrchestrator()
        researcher = ProductResearcher()
        analyzer = ReviewAnalyzer()
        tool = TavilyShoppingTool()

        end_time = time.time()
        initialization_time = end_time - start_time

        # Initialization should be very fast (< 2 seconds)
        assert initialization_time < 2.0, f"Initialization took {initialization_time:.2f}s, should be < 2s"

        # Clean up
        del orchestrator, researcher, analyzer, tool

    @pytest.mark.asyncio
    async def test_concurrent_query_performance(self, mock_environment, mock_fast_responses):
        """Test performance with concurrent queries."""
        queries = [
            ResearchQuery(
                query=f"Best {product} under ${budget}",
                category=ProductCategory.ELECTRONICS,
                price_range=PriceRange.MID_RANGE,
                requirements=["high quality"],
                budget=float(budget)
            )
            for product, budget in [
                ("laptop", 2000),
                ("smartphone", 800),
                ("headphones", 300)
            ]
        ]

        mock_llm_response = Mock()
        mock_llm_response.content = mock_fast_responses["llm_response"]

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = mock_fast_responses["search_results"]

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        start_time = time.time()

                        # Execute queries concurrently
                        tasks = []
                        for query in queries:
                            orchestrator = ProductResearchOrchestrator()
                            task = asyncio.create_task(orchestrator.research_product(query))
                            tasks.append(task)

                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        end_time = time.time()

                        total_time = end_time - start_time

                        # Concurrent execution should be faster than sequential
                        # Should complete within reasonable time (< 45 seconds for 3 concurrent queries)
                        assert total_time < 45.0, f"Concurrent queries took {total_time:.2f}s, should be < 45s"
                        assert len(results) == len(queries)

                        # Check that most results are successful (not exceptions)
                        successful_results = [r for r in results if not isinstance(r, Exception)]
                        assert len(successful_results) >= len(queries) // 2  # At least half should succeed

    def test_component_performance_benchmarks(self):
        """Test individual component performance benchmarks."""
        # Test product extraction performance
        sample_data = [
            {
                "title": f"Product {i}",
                "url": f"https://example.com/product-{i}",
                "content": f"Product {i} description with price ${100 + i * 10}",
                "price": f"${100 + i * 10}",
                "source": f"Store {i}"
            }
            for i in range(10)  # Small dataset
        ]

        researcher = ProductResearcher()

        start_time = time.time()
        products = researcher.extract_products(sample_data)
        end_time = time.time()

        extraction_time = end_time - start_time

        # Product extraction should be fast (< 1 second for 10 items)
        assert extraction_time < 1.0, f"Product extraction took {extraction_time:.2f}s, should be < 1s"
        assert isinstance(products, list)

    @pytest.mark.asyncio
    async def test_memory_efficient_large_dataset(self, mock_environment):
        """Test memory efficiency with larger datasets."""
        # Create larger mock dataset
        large_dataset = [
            {
                "title": f"Product {i}",
                "url": f"https://example.com/product-{i}",
                "content": f"Product {i} description with detailed specs and price ${100 + i * 10}",
                "price": f"${100 + i * 10}",
                "source": f"Store {i % 5}"  # Simulate 5 different stores
            }
            for i in range(50)  # Larger dataset
        ]

        # Monitor memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        mock_llm_response = Mock()
        mock_llm_response.content = "Recommendation for large dataset processing."

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

            with patch.object(TavilyShoppingTool, 'search_products') as mock_search:
                mock_search.return_value = large_dataset

                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        query = ResearchQuery(
                            query="Test large dataset query",
                            category=ProductCategory.ELECTRONICS,
                            price_range=PriceRange.MID_RANGE,
                            requirements=[],
                            budget=1000.0
                        )

                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(query)

                        # Force garbage collection and check memory
                        gc.collect()
                        final_memory = process.memory_info().rss / 1024 / 1024  # MB
                        memory_increase = final_memory - initial_memory

                        # Memory increase should be reasonable (< 100 MB for this test)
                        assert memory_increase < 100, f"Memory increased by {memory_increase:.2f}MB, should be < 100MB"
                        assert result is not None


class TestThroughputPerformance:
    """Test throughput and concurrent request handling."""

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
    async def test_sequential_query_throughput(self, mock_environment):
        """Test throughput for sequential queries."""
        queries = [
            ResearchQuery(
                query=f"Query {i}",
                category=ProductCategory.ELECTRONICS,
                price_range=PriceRange.BUDGET,
                requirements=[],
                budget=100.0
            )
            for i in range(5)
        ]

        mock_results = [{"title": "Test Product", "price": "$99", "url": "https://example.com"}]
        mock_llm_response = Mock()
        mock_llm_response.content = "Quick response"

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

                        start_time = time.time()

                        results = []
                        for query in queries:
                            orchestrator = ProductResearchOrchestrator()
                            result = await orchestrator.research_product(query)
                            results.append(result)

                        end_time = time.time()
                        total_time = end_time - start_time

                        # Calculate throughput (queries per second)
                        throughput = len(queries) / total_time
                        assert throughput > 0.1, f"Throughput {throughput:.2f} queries/sec is too low"
                        assert len(results) == len(queries)

    def test_component_isolation_performance(self):
        """Test that components don't interfere with each other's performance."""
        # Test multiple instances don't slow each other down
        researchers = [ProductResearcher() for _ in range(3)]
        analyzers = [ReviewAnalyzer() for _ in range(3)]

        sample_data = [{"title": "Test", "price": "$100", "url": "https://example.com"}]

        start_time = time.time()

        # Process with multiple instances
        for researcher in researchers:
            products = researcher.extract_products(sample_data)

        end_time = time.time()
        multi_instance_time = end_time - start_time

        # Should not be significantly slower than single instance
        assert multi_instance_time < 3.0, f"Multi-instance processing took {multi_instance_time:.2f}s, too slow"

        # Clean up
        del researchers, analyzers

    @pytest.mark.asyncio
    async def test_rate_limiting_performance(self, mock_environment):
        """Test performance under simulated rate limiting."""
        query = ResearchQuery(
            query="Test rate limiting",
            category=ProductCategory.ELECTRONICS,
            price_range=PriceRange.BUDGET,
            requirements=[],
            budget=100.0
        )

        # Simulate rate limiting with delays
        async def delayed_llm_response(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate API delay
            response = Mock()
            response.content = "Delayed response"
            return response

        async def delayed_search(*args, **kwargs):
            await asyncio.sleep(0.2)  # Simulate search delay
            return [{"title": "Test", "price": "$100", "url": "https://example.com"}]

        with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat:
            mock_chat.return_value.ainvoke = delayed_llm_response

            with patch.object(TavilyShoppingTool, 'search_products', new=delayed_search):
                with patch('src.agents.product_researcher.ProductResearcher') as mock_researcher_class:
                    mock_researcher = Mock()
                    mock_researcher.extract_products.return_value = []
                    mock_researcher_class.return_value = mock_researcher

                    with patch('src.agents.review_analyzer.ReviewAnalyzer') as mock_analyzer_class:
                        mock_analyzer = Mock()
                        mock_analyzer.analyze_reviews.return_value = []
                        mock_analyzer_class.return_value = mock_analyzer

                        start_time = time.time()
                        orchestrator = ProductResearchOrchestrator()
                        result = await orchestrator.research_product(query)
                        end_time = time.time()

                        elapsed_time = end_time - start_time

                        # Should handle delays gracefully and still complete in reasonable time
                        assert elapsed_time > 0.3, "Should account for simulated delays"
                        assert elapsed_time < 10.0, f"Even with delays, should complete in < 10s, took {elapsed_time:.2f}s"
                        assert result is not None


class TestScalabilityPerformance:
    """Test scalability and resource usage."""

    @pytest.fixture
    def mock_environment(self):
        """Set up mock environment."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.tavily_api_key = "test-key"
            mock_settings.model_name = "gpt-4"
            mock_settings.max_tokens = 4000
            yield mock_settings

    def test_memory_usage_scaling(self):
        """Test memory usage scales appropriately."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create multiple instances
        orchestrators = []
        for i in range(5):
            with patch('src.core.config.settings') as mock_settings:
                mock_settings.openai_api_key = "test-key"
                orchestrator = ProductResearchOrchestrator()
                orchestrators.append(orchestrator)

        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_per_instance = (final_memory - initial_memory) / len(orchestrators)

        # Memory per instance should be reasonable (< 50 MB per instance)
        assert memory_per_instance < 50, f"Memory per instance {memory_per_instance:.2f}MB too high"

        # Clean up
        del orchestrators
        gc.collect()

    def test_cpu_usage_efficiency(self):
        """Test CPU usage efficiency during processing."""
        sample_data = [
            {
                "title": f"Product {i}",
                "url": f"https://example.com/product-{i}",
                "content": f"Product {i} description",
                "price": f"${100 + i}",
                "source": "Store"
            }
            for i in range(20)
        ]

        researcher = ProductResearcher()

        # Monitor CPU usage
        start_time = time.time()
        cpu_before = psutil.cpu_percent(interval=None)

        # Process data
        products = researcher.extract_products(sample_data)

        end_time = time.time()
        processing_time = end_time - start_time

        # Processing should be efficient
        assert processing_time < 2.0, f"Processing took {processing_time:.2f}s, should be < 2s"
        assert isinstance(products, list)

    @pytest.mark.asyncio
    async def test_concurrent_user_simulation(self, mock_environment):
        """Test performance with simulated concurrent users."""
        num_concurrent_users = 3
        queries_per_user = 2

        mock_results = [{"title": "Test Product", "price": "$99", "url": "https://example.com"}]
        mock_llm_response = Mock()
        mock_llm_response.content = "Quick response"

        async def simulate_user(user_id: int):
            """Simulate a single user making multiple queries."""
            results = []
            for query_num in range(queries_per_user):
                query = ResearchQuery(
                    query=f"User {user_id} Query {query_num}",
                    category=ProductCategory.ELECTRONICS,
                    price_range=PriceRange.BUDGET,
                    requirements=[],
                    budget=100.0
                )

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
                                results.append(result)

                # Small delay between queries from same user
                await asyncio.sleep(0.1)

            return results

        start_time = time.time()

        # Simulate concurrent users
        user_tasks = [simulate_user(i) for i in range(num_concurrent_users)]
        all_results = await asyncio.gather(*user_tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        # Verify results
        total_queries = num_concurrent_users * queries_per_user
        successful_users = [r for r in all_results if not isinstance(r, Exception)]

        assert len(successful_users) >= num_concurrent_users // 2, "At least half of users should succeed"
        assert total_time < 60.0, f"Concurrent users took {total_time:.2f}s, should be < 60s"

    def test_resource_cleanup_performance(self):
        """Test that resources are cleaned up properly."""
        import gc

        # Get initial counts
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Create and destroy many instances
        for i in range(10):
            with patch('src.core.config.settings') as mock_settings:
                mock_settings.openai_api_key = "test-key"
                orchestrator = ProductResearchOrchestrator()
                researcher = ProductResearcher()
                analyzer = ReviewAnalyzer()

                # Use them briefly
                assert orchestrator is not None
                assert researcher is not None
                assert analyzer is not None

                # Explicitly delete
                del orchestrator, researcher, analyzer

        # Force cleanup
        gc.collect()
        final_objects = len(gc.get_objects())

        # Object count should not grow excessively
        object_growth = final_objects - initial_objects
        assert object_growth < 1000, f"Object growth {object_growth} suggests memory leaks"


class TestPerformanceBaselines:
    """Establish and test performance baselines."""

    def test_baseline_component_initialization(self):
        """Establish baseline for component initialization."""
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"

            # Measure initialization times
            times = []
            for _ in range(5):
                start = time.time()
                orchestrator = ProductResearchOrchestrator()
                end = time.time()
                times.append(end - start)
                del orchestrator

            avg_time = sum(times) / len(times)
            max_time = max(times)

            # Baseline: average < 1s, max < 2s
            assert avg_time < 1.0, f"Average init time {avg_time:.3f}s exceeds 1s baseline"
            assert max_time < 2.0, f"Max init time {max_time:.3f}s exceeds 2s baseline"

    def test_baseline_data_processing(self):
        """Establish baseline for data processing."""
        sample_data = [
            {
                "title": f"Product {i}",
                "url": f"https://example.com/product-{i}",
                "content": f"Product {i} with detailed specifications and price ${100 + i * 10}",
                "price": f"${100 + i * 10}",
                "source": "Store"
            }
            for i in range(25)  # Standard dataset size
        ]

        researcher = ProductResearcher()

        times = []
        for _ in range(3):
            start = time.time()
            products = researcher.extract_products(sample_data)
            end = time.time()
            times.append(end - start)

        avg_time = sum(times) / len(times)
        items_per_second = len(sample_data) / avg_time

        # Baseline: should process at least 10 items per second
        assert items_per_second >= 10, f"Processing rate {items_per_second:.2f} items/s below 10 baseline"

    def test_baseline_memory_efficiency(self):
        """Establish baseline for memory efficiency."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create standard workload
        with patch('src.core.config.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"

            orchestrator = ProductResearchOrchestrator()
            researcher = ProductResearcher()

            # Process standard data
            sample_data = [{"title": f"Product {i}", "price": f"${i*10}"} for i in range(50)]
            products = researcher.extract_products(sample_data)

            gc.collect()
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_usage = peak_memory - initial_memory

            # Baseline: should use less than 100MB for standard workload
            assert memory_usage < 100, f"Memory usage {memory_usage:.2f}MB exceeds 100MB baseline"

            # Clean up
            del orchestrator, researcher, products