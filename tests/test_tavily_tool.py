"""Tests for Tavily shopping tool."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.tools.tavily_shopping import TavilyShoppingTool
from src.core.models import SearchResult, Product


class TestTavilyShoppingTool:
    """Test Tavily shopping tool functionality."""

    def test_tool_initialization_without_api_key(self):
        """Test tool initialization without API key."""
        with patch('src.tools.tavily_shopping.settings') as mock_settings:
            mock_settings.tavily_api_key = None

            tool = TavilyShoppingTool()

            assert tool.client is None
            assert tool.api_key is None

    def test_tool_initialization_with_api_key(self):
        """Test tool initialization with API key."""
        with patch('src.tools.tavily_shopping.TavilyClient') as mock_client:
            tool = TavilyShoppingTool(api_key="test-key")

            assert tool.api_key == "test-key"
            mock_client.assert_called_once_with(api_key="test-key")

    @pytest.mark.asyncio
    async def test_search_products_without_client(self):
        """Test search products without initialized client."""
        tool = TavilyShoppingTool()
        tool.client = None

        results = await tool.search_products("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_products_with_mock_client(self):
        """Test search products with mocked client."""
        mock_response = {
            "results": [
                {
                    "title": "Test Product",
                    "url": "https://example.com/product",
                    "content": "Product description",
                    "score": 0.95
                }
            ]
        }

        with patch('src.tools.tavily_shopping.TavilyClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock the async search call
            with patch('asyncio.to_thread', return_value=mock_response):
                tool = TavilyShoppingTool(api_key="test-key")
                results = await tool.search_products("test query")

                assert len(results) == 1
                assert isinstance(results[0], SearchResult)
                assert results[0].title == "Test Product"
                assert results[0].url == "https://example.com/product"

    def test_extract_product_from_result(self):
        """Test product extraction from search result."""
        search_result = SearchResult(
            title="Apple MacBook Pro 16-inch - $2,499.99",
            url="https://example.com/macbook",
            content="High-performance laptop with M1 chip. Price: $2,499.99"
        )

        tool = TavilyShoppingTool()
        product = tool.extract_product_from_result(search_result)

        assert product is not None
        assert isinstance(product, Product)
        assert product.name == search_result.title
        assert product.url == search_result.url
        assert product.price == 2499.99  # Should extract price

    def test_price_extraction_patterns(self):
        """Test various price extraction patterns."""
        tool = TavilyShoppingTool()

        # Test different price formats
        test_cases = [
            ("Product costs $99.99", 99.99),
            ("Price: $1,299.00", 1299.00),
            ("Sale price $599", 599.0),
            ("1500 USD", 1500.0),
            ("Now: $2,999.99", 2999.99),
            ("No price mentioned", None)
        ]

        for text, expected_price in test_cases:
            extracted_price = tool._extract_price(text)
            if expected_price is None:
                assert extracted_price is None
            else:
                assert extracted_price == expected_price

    def test_brand_extraction(self):
        """Test brand extraction from product titles."""
        tool = TavilyShoppingTool()

        test_cases = [
            ("Apple MacBook Pro", ("Apple", None)),
            ("Dell XPS 13 Laptop", ("Dell", None)),
            ("Sony WH-1000XM4 Headphones", ("Sony", None)),
            ("Unknown Brand Product", (None, "Unknown Brand Product"))
        ]

        for title, expected in test_cases:
            brand, model = tool._extract_brand_model(title)
            assert brand == expected[0]

    @pytest.mark.asyncio
    async def test_get_shopping_results_integration(self):
        """Test complete shopping results flow."""
        mock_search_response = {
            "results": [
                {
                    "title": "Gaming Laptop - $1,499.99",
                    "url": "https://example.com/gaming-laptop",
                    "content": "High-performance gaming laptop with RTX graphics. Price: $1,499.99"
                }
            ]
        }

        with patch('src.tools.tavily_shopping.TavilyClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            with patch('asyncio.to_thread', return_value=mock_search_response):
                tool = TavilyShoppingTool(api_key="test-key")
                results = await tool.get_shopping_results("gaming laptop")

                assert "products" in results
                assert "raw_results" in results
                assert "query" in results
                assert "total_found" in results

                assert results["query"] == "gaming laptop"
                assert results["total_found"] == 1
                assert len(results["products"]) == 1
                assert len(results["raw_results"]) == 1

    def test_price_extraction_edge_cases(self):
        """Test edge cases in price extraction."""
        tool = TavilyShoppingTool()

        # Test invalid prices that should return None
        invalid_cases = [
            "Price: $0.50",  # Too low
            "Price: $999,999.99",  # Too high
            "Price: abc",  # Non-numeric
            ""  # Empty string
        ]

        for text in invalid_cases:
            price = tool._extract_price(text)
            # Should return None for invalid prices
            assert price is None

    @pytest.mark.asyncio
    async def test_search_error_handling(self):
        """Test error handling in search operations."""
        with patch('src.tools.tavily_shopping.TavilyClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock an exception during search
            with patch('asyncio.to_thread', side_effect=Exception("API Error")):
                tool = TavilyShoppingTool(api_key="test-key")
                results = await tool.search_products("test query")

                # Should return empty list on error
                assert results == []