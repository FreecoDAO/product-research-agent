"""Comprehensive tests for the product researcher agent."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from datetime import datetime
from typing import Dict, Any, List

from src.agents.product_researcher import ProductResearcher
from src.core.models import Product, ProductCategory, SearchResult
from src.tools.tavily_shopping import TavilyShoppingTool


class TestProductResearcher:
    """Test ProductResearcher functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_openai_key = "test-openai-key"
        self.mock_tavily_key = "test-tavily-key"

    def test_product_researcher_initialization_without_api_key(self):
        """Test product researcher initialization without OpenAI API key."""
        with patch('src.agents.product_researcher.settings') as mock_settings:
            mock_settings.openai_api_key = None

            researcher = ProductResearcher()

            assert researcher.llm is None
            assert researcher.tavily_tool is not None

    def test_product_researcher_initialization_with_api_key(self):
        """Test product researcher initialization with OpenAI API key."""
        with patch('src.agents.product_researcher.settings') as mock_settings:
            mock_settings.openai_api_key = self.mock_openai_key
            mock_settings.model_name = "gpt-5"
            mock_settings.max_tokens = 4000
            mock_settings.reasoning_effort = "high"
            mock_settings.service_tier = "default"

            with patch('src.agents.product_researcher.ChatOpenAI') as mock_chat_openai:
                researcher = ProductResearcher()

                assert researcher.llm is not None
                mock_chat_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_products_no_results(self):
        """Test product research with no search results."""
        mock_tavily_tool = AsyncMock()
        mock_tavily_tool.get_shopping_results.return_value = {
            "products": [],
            "raw_results": []
        }

        researcher = ProductResearcher()
        researcher.tavily_tool = mock_tavily_tool

        results = await researcher.research_products("nonexistent product")

        assert results == []
        mock_tavily_tool.get_shopping_results.assert_called_once_with("nonexistent product")

    @pytest.mark.asyncio
    async def test_research_products_with_results(self):
        """Test product research with search results."""
        mock_tavily_tool = AsyncMock()

        # Mock search results
        test_products = [
            Product(name="Test Laptop", price=999.99, brand="TestBrand"),
            Product(name="Another Laptop", price=1299.99, brand="AnotherBrand")
        ]

        test_raw_results = [
            SearchResult(title="Test Laptop", url="https://example.com/1", content="Great laptop"),
            SearchResult(title="Another Laptop", url="https://example.com/2", content="Excellent performance")
        ]

        mock_tavily_tool.get_shopping_results.return_value = {
            "products": test_products,
            "raw_results": test_raw_results
        }

        researcher = ProductResearcher()
        researcher.tavily_tool = mock_tavily_tool
        researcher.llm = None  # Test without LLM enhancement

        results = await researcher.research_products("laptop", max_products=5)

        assert len(results) == 2
        assert results[0].name == "Test Laptop"
        assert results[1].name == "Another Laptop"

    @pytest.mark.asyncio
    async def test_research_products_with_enhancement_error(self):
        """Test product research with enhancement error."""
        mock_tavily_tool = AsyncMock()
        mock_llm = AsyncMock()

        test_products = [Product(name="Test Laptop", price=999.99)]
        test_raw_results = [SearchResult(title="Test Laptop", url="https://example.com", content="Description")]

        mock_tavily_tool.get_shopping_results.return_value = {
            "products": test_products,
            "raw_results": test_raw_results
        }

        researcher = ProductResearcher()
        researcher.tavily_tool = mock_tavily_tool
        researcher.llm = mock_llm

        # Mock enhancement to raise exception
        with patch.object(researcher, '_enhance_product', side_effect=Exception("Enhancement failed")):
            results = await researcher.research_products("laptop")

        # Should still return original product despite enhancement failure
        assert len(results) == 1
        assert results[0].name == "Test Laptop"

    @pytest.mark.asyncio
    async def test_research_products_with_search_exception(self):
        """Test product research with search exception."""
        mock_tavily_tool = AsyncMock()
        mock_tavily_tool.get_shopping_results.side_effect = Exception("Search API failed")

        researcher = ProductResearcher()
        researcher.tavily_tool = mock_tavily_tool

        results = await researcher.research_products("laptop")

        assert results == []

    @pytest.mark.asyncio
    async def test_enhance_product_without_llm(self):
        """Test product enhancement without LLM."""
        researcher = ProductResearcher()
        researcher.llm = None

        original_product = Product(name="Test Laptop", price=999.99)
        search_result = SearchResult(title="Test Laptop", url="https://example.com", content="Great laptop")

        enhanced = await researcher._enhance_product(original_product, search_result, "laptop")

        assert enhanced == original_product  # Should return original when no LLM

    @pytest.mark.asyncio
    async def test_enhance_product_without_search_result(self):
        """Test product enhancement without search result."""
        mock_llm = AsyncMock()
        researcher = ProductResearcher()
        researcher.llm = mock_llm

        original_product = Product(name="Test Laptop", price=999.99)

        enhanced = await researcher._enhance_product(original_product, None, "laptop")

        assert enhanced == original_product  # Should return original when no search result

    @pytest.mark.asyncio
    async def test_enhance_product_with_llm(self):
        """Test product enhancement with LLM."""
        mock_llm = AsyncMock()
        researcher = ProductResearcher()
        researcher.llm = mock_llm

        original_product = Product(name="Test Laptop", price=999.99)
        search_result = SearchResult(
            title="Test Laptop - $999.99",
            url="https://example.com",
            content="Excellent laptop with 16GB RAM, 512GB SSD, Intel i7 processor"
        )

        # Mock all the async methods
        with patch.object(researcher, '_extract_specifications', return_value={"RAM": "16GB", "Storage": "512GB SSD"}):
            with patch.object(researcher, '_extract_price_advanced', return_value=999.99):
                with patch.object(researcher, '_categorize_product', return_value=ProductCategory.COMPUTERS):
                    with patch.object(researcher, '_extract_brand_advanced', return_value="TestBrand"):
                        with patch.object(researcher, '_extract_rating', return_value=4.5):
                            with patch.object(researcher, '_extract_review_count', return_value=150):
                                enhanced = await researcher._enhance_product(original_product, search_result, "laptop")

        assert enhanced.name == "Test Laptop"
        assert enhanced.price == 999.99
        assert enhanced.category == ProductCategory.COMPUTERS
        assert enhanced.brand == "TestBrand"
        assert enhanced.rating == 4.5
        assert enhanced.review_count == 150
        assert enhanced.specifications["RAM"] == "16GB"

    @pytest.mark.asyncio
    async def test_enhance_product_with_exception(self):
        """Test product enhancement with exception."""
        mock_llm = AsyncMock()
        researcher = ProductResearcher()
        researcher.llm = mock_llm

        original_product = Product(name="Test Laptop", price=999.99)
        search_result = SearchResult(title="Test Laptop", url="https://example.com", content="Description")

        # Mock specification extraction to raise exception
        with patch.object(researcher, '_extract_specifications', side_effect=Exception("LLM failed")):
            enhanced = await researcher._enhance_product(original_product, search_result, "laptop")

        assert enhanced == original_product  # Should return original on exception

    @pytest.mark.asyncio
    async def test_extract_specifications_without_llm(self):
        """Test specification extraction without LLM."""
        researcher = ProductResearcher()
        researcher.llm = None

        search_result = SearchResult(title="Test", url="", content="Test content")
        specs = await researcher._extract_specifications(search_result, "test query")

        assert specs == {}

    @pytest.mark.asyncio
    async def test_extract_specifications_with_llm(self):
        """Test specification extraction with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = '{"RAM": "16GB", "Storage": "512GB SSD", "Processor": "Intel i7"}'
        mock_llm.ainvoke.return_value = mock_response

        researcher = ProductResearcher()
        researcher.llm = mock_llm

        search_result = SearchResult(
            title="Gaming Laptop",
            url="",
            content="High-performance laptop with 16GB RAM and 512GB SSD"
        )

        specs = await researcher._extract_specifications(search_result, "gaming laptop")

        assert specs["RAM"] == "16GB"
        assert specs["Storage"] == "512GB SSD"
        assert specs["Processor"] == "Intel i7"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_specifications_with_llm_exception(self):
        """Test specification extraction with LLM exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM API failed")

        researcher = ProductResearcher()
        researcher.llm = mock_llm

        search_result = SearchResult(title="Test", url="", content="Test content")
        specs = await researcher._extract_specifications(search_result, "test")

        assert specs == {}

    @pytest.mark.asyncio
    async def test_extract_price_advanced_from_title(self):
        """Test advanced price extraction from title."""
        researcher = ProductResearcher()

        search_result = SearchResult(
            title="Gaming Laptop - $1,499.99",
            url="",
            content="High-performance gaming laptop"
        )

        price = await researcher._extract_price_advanced(search_result)

        assert price == 1499.99

    @pytest.mark.asyncio
    async def test_extract_price_advanced_from_content(self):
        """Test advanced price extraction from content."""
        researcher = ProductResearcher()

        search_result = SearchResult(
            title="Gaming Laptop",
            url="",
            content="High-performance gaming laptop. Price: $2,299.99 with free shipping"
        )

        price = await researcher._extract_price_advanced(search_result)

        assert price == 2299.99

    @pytest.mark.asyncio
    async def test_extract_price_advanced_various_patterns(self):
        """Test advanced price extraction with various patterns."""
        researcher = ProductResearcher()

        test_cases = [
            ("Product costs USD 999.99", 999.99),
            ("Sale: $1,299.00", 1299.00),
            ("Now: $799.50", 799.50),
            ("1,500 dollars", 1500.0),  # Needs comma for the pattern to match correctly
            ("Price not mentioned", None),
            ("Price: $5.00", None),  # Too low (< $10)
            ("Price: $99,999.99", None)  # Too high (> $50,000)
        ]

        for content, expected_price in test_cases:
            search_result = SearchResult(title="Test", url="", content=content)
            extracted_price = await researcher._extract_price_advanced(search_result)

            if expected_price is None:
                assert extracted_price is None
            else:
                assert extracted_price == expected_price

    @pytest.mark.asyncio
    async def test_extract_price_advanced_with_exception(self):
        """Test advanced price extraction with exception."""
        researcher = ProductResearcher()

        # Mock search result to cause exception
        search_result = Mock()
        search_result.content = "test"
        search_result.title = "test"
        # Make content property raise exception
        type(search_result).content = PropertyMock(side_effect=Exception("Error"))

        price = await researcher._extract_price_advanced(search_result)

        assert price is None

    @pytest.mark.asyncio
    async def test_categorize_product_computers(self):
        """Test product categorization for computers."""
        researcher = ProductResearcher()

        category = await researcher._categorize_product(
            "MacBook Pro",
            "High-performance laptop with M1 processor and 16GB RAM"
        )

        assert category == ProductCategory.COMPUTERS

    @pytest.mark.asyncio
    async def test_categorize_product_electronics(self):
        """Test product categorization for electronics."""
        researcher = ProductResearcher()

        category = await researcher._categorize_product(
            "iPhone 15",
            "Latest smartphone with advanced camera and 5G connectivity"
        )

        assert category == ProductCategory.ELECTRONICS

    @pytest.mark.asyncio
    async def test_categorize_product_home(self):
        """Test product categorization for home products."""
        researcher = ProductResearcher()

        category = await researcher._categorize_product(
            "Office Chair",
            "Ergonomic desk chair for home office furniture"
        )

        assert category == ProductCategory.HOME

    @pytest.mark.asyncio
    async def test_categorize_product_other(self):
        """Test product categorization for other products."""
        researcher = ProductResearcher()

        category = await researcher._categorize_product(
            "Mystery Product",
            "Unknown product with no clear category indicators"
        )

        assert category == ProductCategory.OTHER

    @pytest.mark.asyncio
    async def test_categorize_product_with_exception(self):
        """Test product categorization with exception."""
        researcher = ProductResearcher()

        # Mock the category scoring to cause exception
        with patch('builtins.sum', side_effect=Exception("Error")):
            category = await researcher._categorize_product("Test", "Test content")

        assert category == ProductCategory.OTHER

    @pytest.mark.asyncio
    async def test_extract_brand_advanced(self):
        """Test advanced brand extraction."""
        researcher = ProductResearcher()

        test_cases = [
            ("Apple MacBook Pro with M1 chip", "Apple"),
            ("Dell XPS 13 laptop computer", "Dell"),
            ("Sony WH-1000XM4 wireless headphones", "Sony"),
            ("Bose QuietComfort 35 II", "Bose"),
            ("Gaming laptop with Intel processor", "Intel"),
            ("Unknown brand product", None)
        ]

        for text, expected_brand in test_cases:
            search_result = SearchResult(title=text, url="", content=text)
            brand = await researcher._extract_brand_advanced(search_result)

            if expected_brand is None:
                assert brand is None
            else:
                assert brand == expected_brand

    @pytest.mark.asyncio
    async def test_extract_brand_advanced_with_exception(self):
        """Test advanced brand extraction with exception."""
        researcher = ProductResearcher()

        # Mock search result to cause exception
        search_result = Mock()
        type(search_result).title = PropertyMock(side_effect=Exception("Error"))
        type(search_result).content = PropertyMock(side_effect=Exception("Error"))

        brand = await researcher._extract_brand_advanced(search_result)

        assert brand is None

    @pytest.mark.asyncio
    async def test_extract_rating(self):
        """Test rating extraction from search result."""
        researcher = ProductResearcher()

        test_cases = [
            ("Product rated 4.5 out of 5 stars", 4.5),
            ("Rating: 3.8 stars", 3.8),
            ("4.2/5 customer rating", 4.2),
            ("User rating: 5.0", 5.0),
            ("No rating available", None),
            ("Rating: 6.0", None),  # Invalid rating > 5
            ("Rating: -1.0", None)  # Invalid negative rating
        ]

        for content, expected_rating in test_cases:
            search_result = SearchResult(title="Test", url="", content=content)
            rating = await researcher._extract_rating(search_result)

            if expected_rating is None:
                assert rating is None
            else:
                assert rating == expected_rating

    @pytest.mark.asyncio
    async def test_extract_rating_with_exception(self):
        """Test rating extraction with exception."""
        researcher = ProductResearcher()

        # Mock search result to cause exception
        search_result = Mock()
        type(search_result).content = PropertyMock(side_effect=Exception("Error"))

        rating = await researcher._extract_rating(search_result)

        assert rating is None

    @pytest.mark.asyncio
    async def test_extract_review_count(self):
        """Test review count extraction from search result."""
        researcher = ProductResearcher()

        test_cases = [
            ("Based on 1,234 reviews", 1234),
            ("500 customer reviews", 500),
            ("2,500 ratings from buyers", 2500),
            ("25 reviews by customers", 25),
            ("No reviews available", 0)
        ]

        for content, expected_count in test_cases:
            search_result = SearchResult(title="Test", url="", content=content)
            count = await researcher._extract_review_count(search_result)

            assert count == expected_count

    @pytest.mark.asyncio
    async def test_extract_review_count_with_exception(self):
        """Test review count extraction with exception."""
        researcher = ProductResearcher()

        # Mock search result to cause exception
        search_result = Mock()
        type(search_result).content = PropertyMock(side_effect=Exception("Error"))

        count = await researcher._extract_review_count(search_result)

        assert count == 0

    def test_parse_specs_from_text_valid_json(self):
        """Test parsing specifications from valid JSON text."""
        researcher = ProductResearcher()

        json_text = '''
        Here are the specifications:
        {"RAM": "16GB", "Storage": "512GB SSD", "Processor": "Intel i7"}
        These are the key features.
        '''

        specs = researcher._parse_specs_from_text(json_text)

        assert specs["RAM"] == "16GB"
        assert specs["Storage"] == "512GB SSD"
        assert specs["Processor"] == "Intel i7"

    def test_parse_specs_from_text_key_value_pairs(self):
        """Test parsing specifications from key-value pair text."""
        researcher = ProductResearcher()

        text = '''
        RAM: 16GB DDR4
        Storage: 1TB SSD
        Graphics: NVIDIA RTX 3080
        Weight: 2.1 kg
        Battery: unknown
        '''

        specs = researcher._parse_specs_from_text(text)

        assert specs["RAM"] == "16GB DDR4"
        assert specs["Storage"] == "1TB SSD"
        assert specs["Graphics"] == "NVIDIA RTX 3080"
        assert specs["Weight"] == "2.1 kg"
        assert "Battery" not in specs  # Should filter out "unknown" values

    def test_parse_specs_from_text_malformed_json(self):
        """Test parsing specifications from malformed JSON."""
        researcher = ProductResearcher()

        malformed_text = '''
        {RAM: "16GB", Storage: "512GB SSD"  # Missing quotes and closing brace
        '''

        specs = researcher._parse_specs_from_text(malformed_text)

        # Should fall back to key-value parsing and find one key-value pair
        assert len(specs) == 1  # The comment part has one key-value pair

    def test_parse_specs_from_text_with_exception(self):
        """Test parsing specifications with exception."""
        researcher = ProductResearcher()

        # Mock json.loads to raise exception
        with patch('json.loads', side_effect=Exception("JSON error")):
            specs = researcher._parse_specs_from_text('{"test": "value"}')

        assert specs == {}

    def test_clean_description(self):
        """Test description cleaning."""
        researcher = ProductResearcher()

        # Test normal description
        description = "   This is a   great   laptop   with   excellent   performance.   "
        cleaned = researcher._clean_description(description)
        assert cleaned == "This is a great laptop with excellent performance."

        # Test long description (should be truncated)
        long_description = "This is a very long description. " * 50  # Make it > 500 chars
        cleaned = researcher._clean_description(long_description)
        assert len(cleaned) <= 503  # 500 chars + "..."
        assert cleaned.endswith("...")

    def test_clean_description_with_exception(self):
        """Test description cleaning with exception."""
        researcher = ProductResearcher()

        # Mock string.split to cause exception in the try block
        with patch('str.split', side_effect=Exception("Error")):
            cleaned = researcher._clean_description("test description")

        # Should return truncated version as fallback (500 chars + ...)
        assert cleaned == "test description"

    @pytest.mark.asyncio
    async def test_compare_products_without_llm(self):
        """Test product comparison without LLM."""
        researcher = ProductResearcher()
        researcher.llm = None

        products = [Product(name="Laptop 1"), Product(name="Laptop 2")]
        result = await researcher.compare_products(products)

        assert "error" in result
        assert "No products to compare or LLM not available" in result["error"]

    @pytest.mark.asyncio
    async def test_compare_products_empty_list(self):
        """Test product comparison with empty product list."""
        researcher = ProductResearcher()

        result = await researcher.compare_products([])

        assert "error" in result
        assert "No products to compare or LLM not available" in result["error"]

    @pytest.mark.asyncio
    async def test_compare_products_with_llm(self):
        """Test product comparison with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Comparison shows Laptop 1 has better value while Laptop 2 has higher performance"
        mock_llm.ainvoke.return_value = mock_response

        researcher = ProductResearcher()
        researcher.llm = mock_llm

        products = [
            Product(name="Laptop 1", price=999.99, brand="Brand1", specifications={"RAM": "8GB"}),
            Product(name="Laptop 2", price=1499.99, brand="Brand2", specifications={"RAM": "16GB"})
        ]

        result = await researcher.compare_products(products, ["price", "performance"])

        assert "comparison" in result
        assert "products_compared" in result
        assert "criteria" in result
        assert "timestamp" in result

        assert result["products_compared"] == 2
        assert result["criteria"] == ["price", "performance"]
        assert "better value" in result["comparison"]

    @pytest.mark.asyncio
    async def test_compare_products_with_default_criteria(self):
        """Test product comparison with default criteria."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Default comparison analysis"
        mock_llm.ainvoke.return_value = mock_response

        researcher = ProductResearcher()
        researcher.llm = mock_llm

        products = [Product(name="Test Product")]

        result = await researcher.compare_products(products)  # No criteria specified

        assert result["criteria"] == ["price", "specifications", "ratings", "value"]

    @pytest.mark.asyncio
    async def test_compare_products_with_exception(self):
        """Test product comparison with exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM comparison failed")

        researcher = ProductResearcher()
        researcher.llm = mock_llm

        products = [Product(name="Test Product")]

        result = await researcher.compare_products(products)

        assert "error" in result
        assert "Comparison failed: LLM comparison failed" in result["error"]

    def test_format_products_for_comparison(self):
        """Test formatting products for comparison."""
        researcher = ProductResearcher()

        products = [
            Product(
                name="Gaming Laptop",
                price=1599.99,
                brand="TechBrand",
                category=ProductCategory.COMPUTERS,
                rating=4.5,
                review_count=250,
                specifications={"RAM": "16GB", "Storage": "1TB SSD"},
                description="High-performance gaming laptop with RTX graphics"
            ),
            Product(
                name="Business Laptop",
                price=1199.99,
                brand="OfficeBrand",
                specifications={"RAM": "8GB", "Storage": "512GB SSD"}
            )
        ]

        formatted = researcher._format_products_for_comparison(products)

        assert "Product 1: Gaming Laptop" in formatted
        assert "Price: $1599.99" in formatted
        assert "Brand: TechBrand" in formatted
        assert "Rating: 4.5 (250 reviews)" in formatted
        assert "- RAM: 16GB" in formatted
        assert "- Storage: 1TB SSD" in formatted

        assert "Product 2: Business Laptop" in formatted
        assert "Price: $1199.99" in formatted
        assert "Brand: OfficeBrand" in formatted

    def test_format_products_for_comparison_minimal_data(self):
        """Test formatting products with minimal data for comparison."""
        researcher = ProductResearcher()

        products = [Product(name="Minimal Product")]

        formatted = researcher._format_products_for_comparison(products)

        assert "Product 1: Minimal Product" in formatted
        assert "Price: $N/A" in formatted
        assert "Brand: Unknown" in formatted
        assert "Category: Unknown" in formatted
        assert "Rating: N/A (0 reviews)" in formatted

    @pytest.mark.asyncio
    async def test_research_products_max_products_limit(self):
        """Test product research with max_products limit."""
        mock_tavily_tool = AsyncMock()

        # Create more products than the limit
        test_products = [
            Product(name=f"Laptop {i}", price=999.99 + i*100) for i in range(10)
        ]
        test_raw_results = [
            SearchResult(title=f"Laptop {i}", url=f"https://example.com/{i}", content=f"Description {i}")
            for i in range(10)
        ]

        mock_tavily_tool.get_shopping_results.return_value = {
            "products": test_products,
            "raw_results": test_raw_results
        }

        researcher = ProductResearcher()
        researcher.tavily_tool = mock_tavily_tool
        researcher.llm = None

        # Test with max_products=5
        results = await researcher.research_products("laptop", max_products=5)

        assert len(results) == 5  # Should be limited to 5
        assert all(result.name.startswith("Laptop") for result in results)

    @pytest.mark.asyncio
    async def test_research_products_with_category_filter(self):
        """Test product research with category filter."""
        mock_tavily_tool = AsyncMock()
        test_products = [Product(name="Test Laptop", category=ProductCategory.COMPUTERS)]
        test_raw_results = [SearchResult(title="Test Laptop", url="https://example.com", content="Description")]

        mock_tavily_tool.get_shopping_results.return_value = {
            "products": test_products,
            "raw_results": test_raw_results
        }

        researcher = ProductResearcher()
        researcher.tavily_tool = mock_tavily_tool
        researcher.llm = None

        results = await researcher.research_products("laptop", category=ProductCategory.COMPUTERS)

        assert len(results) == 1
        assert results[0].category == ProductCategory.COMPUTERS