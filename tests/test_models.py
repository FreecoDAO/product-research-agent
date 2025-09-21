"""Tests for Pydantic data models."""

import pytest
from datetime import datetime
from src.core.models import (
    Product, Review, SearchResult, ResearchQuery, ResearchResult,
    ProductCategory, PriceRange
)


class TestProduct:
    """Test Product model."""

    def test_product_creation(self):
        """Test basic product creation."""
        product = Product(name="Test Laptop")

        assert product.name == "Test Laptop"
        assert product.price is None
        assert product.currency == "USD"
        assert product.specifications == {}
        assert product.availability is True
        assert product.review_count == 0

    def test_product_with_full_data(self):
        """Test product with complete data."""
        product = Product(
            name="MacBook Pro",
            price=1999.99,
            brand="Apple",
            category=ProductCategory.COMPUTERS,
            specifications={"RAM": "16GB", "Storage": "512GB SSD"},
            rating=4.5,
            review_count=150
        )

        assert product.name == "MacBook Pro"
        assert product.price == 1999.99
        assert product.brand == "Apple"
        assert product.category == ProductCategory.COMPUTERS
        assert product.specifications["RAM"] == "16GB"
        assert product.rating == 4.5
        assert product.review_count == 150

    def test_product_defaults(self):
        """Test product default values."""
        product = Product(name="Test Product")

        assert product.currency == "USD"
        assert product.availability is True
        assert product.specifications == {}
        assert product.review_count == 0


class TestReview:
    """Test Review model."""

    def test_review_creation(self):
        """Test basic review creation."""
        review = Review(text="Great product!")

        assert review.text == "Great product!"
        assert review.rating is None
        assert review.verified is False
        assert review.helpful_count == 0
        assert review.sentiment is None

    def test_review_with_sentiment(self):
        """Test review with sentiment analysis."""
        review = Review(
            text="Amazing laptop, highly recommend!",
            rating=5.0,
            sentiment="positive",
            verified=True,
            helpful_count=25
        )

        assert review.sentiment == "positive"
        assert review.rating == 5.0
        assert review.verified is True
        assert review.helpful_count == 25


class TestSearchResult:
    """Test SearchResult model."""

    def test_search_result_creation(self):
        """Test search result creation."""
        result = SearchResult(
            title="Test Product - Amazon",
            url="https://amazon.com/test",
            content="Product description here..."
        )

        assert result.title == "Test Product - Amazon"
        assert result.url == "https://amazon.com/test"
        assert result.content == "Product description here..."
        assert result.score is None


class TestResearchQuery:
    """Test ResearchQuery model."""

    def test_research_query_basic(self):
        """Test basic research query."""
        query = ResearchQuery(query="laptop for programming")

        assert query.query == "laptop for programming"
        assert query.category is None
        assert query.price_range is None
        assert query.features == []

    def test_research_query_with_filters(self):
        """Test research query with filters."""
        query = ResearchQuery(
            query="gaming laptop",
            category=ProductCategory.COMPUTERS,
            price_range=PriceRange.PREMIUM,
            max_price=3000.0,
            features=["gaming", "high-performance"]
        )

        assert query.category == ProductCategory.COMPUTERS
        assert query.price_range == PriceRange.PREMIUM
        assert query.max_price == 3000.0
        assert "gaming" in query.features


class TestResearchResult:
    """Test ResearchResult model."""

    def test_research_result_creation(self):
        """Test research result creation."""
        query = ResearchQuery(query="test query")
        result = ResearchResult(query=query)

        assert result.query.query == "test query"
        assert result.products == []
        assert result.reviews == []
        assert result.alternatives == []
        assert result.summary is None
        assert result.recommendation is None

    def test_research_result_with_data(self):
        """Test research result with complete data."""
        query = ResearchQuery(query="laptop")
        product = Product(name="Test Laptop", price=999.99)
        review = Review(text="Good laptop", sentiment="positive")

        result = ResearchResult(
            query=query,
            products=[product],
            reviews=[review],
            summary="Test summary",
            recommendation="Recommended laptop",
            timestamp="2024-01-01T00:00:00",
            total_research_time=25.5
        )

        assert len(result.products) == 1
        assert len(result.reviews) == 1
        assert result.summary == "Test summary"
        assert result.recommendation == "Recommended laptop"
        assert result.total_research_time == 25.5


class TestEnums:
    """Test enum classes."""

    def test_product_category_enum(self):
        """Test ProductCategory enum."""
        assert ProductCategory.ELECTRONICS == "electronics"
        assert ProductCategory.COMPUTERS == "computers"
        assert ProductCategory.HOME == "home"
        assert ProductCategory.CLOTHING == "clothing"
        assert ProductCategory.OTHER == "other"

    def test_price_range_enum(self):
        """Test PriceRange enum."""
        assert PriceRange.BUDGET == "budget"
        assert PriceRange.MID_RANGE == "mid_range"
        assert PriceRange.PREMIUM == "premium"