"""Comprehensive tests for the review analyzer agent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, PropertyMock
from datetime import datetime
from collections import Counter
from typing import Dict, Any, List

from src.agents.review_analyzer import ReviewAnalyzer
from src.core.models import Review, SearchResult


class TestReviewAnalyzer:
    """Test ReviewAnalyzer functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_openai_key = "test-openai-key"

    def test_review_analyzer_initialization_without_api_key(self):
        """Test review analyzer initialization without OpenAI API key."""
        with patch('src.agents.review_analyzer.settings') as mock_settings:
            mock_settings.openai_api_key = None

            analyzer = ReviewAnalyzer()

            assert analyzer.llm is None

    def test_review_analyzer_initialization_with_api_key(self):
        """Test review analyzer initialization with OpenAI API key."""
        with patch('src.agents.review_analyzer.settings') as mock_settings:
            mock_settings.openai_api_key = self.mock_openai_key
            mock_settings.model_name = "gpt-5"
            mock_settings.max_tokens = 4000
            mock_settings.reasoning_effort = "high"
            mock_settings.service_tier = "default"

            with patch('src.agents.review_analyzer.ChatOpenAI') as mock_chat_openai:
                analyzer = ReviewAnalyzer()

                assert analyzer.llm is not None
                mock_chat_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_reviews_no_content(self):
        """Test review analysis with no review content found."""
        analyzer = ReviewAnalyzer()

        # Search results with no review indicators
        search_results = [
            SearchResult(title="Product Specs", url="", content="Technical specifications only"),
            SearchResult(title="Price Info", url="", content="Pricing and availability information")
        ]

        reviews = await analyzer.analyze_reviews(search_results, "Test Product")

        assert reviews == []

    @pytest.mark.asyncio
    async def test_analyze_reviews_with_content(self):
        """Test review analysis with review content found."""
        analyzer = ReviewAnalyzer()
        analyzer.llm = None  # Use basic analysis

        # Search results with review indicators
        search_results = [
            SearchResult(
                title="Customer Reviews",
                url="",
                content="Customer review: This product is amazing! I highly recommend it to everyone. The quality is excellent and performance is outstanding."
            ),
            SearchResult(
                title="User Ratings",
                url="",
                content="User experience: Great product with some minor issues. Overall satisfied with the purchase. Would buy again."
            )
        ]

        reviews = await analyzer.analyze_reviews(search_results, "Test Product")

        assert len(reviews) > 0
        assert all(isinstance(review, Review) for review in reviews)

    @pytest.mark.asyncio
    async def test_analyze_reviews_with_llm(self):
        """Test review analysis with LLM available."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "positive sentiment analysis result"
        mock_llm.ainvoke.return_value = mock_response

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        search_results = [
            SearchResult(
                title="Reviews",
                url="",
                content="Customer review: Excellent product, highly recommended!"
            )
        ]

        # Mock other methods
        with patch.object(analyzer, '_assess_authenticity', return_value=0.8):
            reviews = await analyzer.analyze_reviews(search_results, "Test Product")

        assert len(reviews) > 0
        assert reviews[0].sentiment == "positive"
        assert reviews[0].verified is True  # authenticity score > 0.7

    @pytest.mark.asyncio
    async def test_analyze_reviews_with_exception(self):
        """Test review analysis with exception during processing."""
        analyzer = ReviewAnalyzer()

        # Mock _extract_review_content to raise exception
        with patch.object(analyzer, '_extract_review_content', side_effect=Exception("Extraction failed")):
            reviews = await analyzer.analyze_reviews([], "Test Product")

        assert reviews == []

    @pytest.mark.asyncio
    async def test_analyze_reviews_with_focus_areas(self):
        """Test review analysis with specific focus areas."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "positive sentiment with focus on battery life"
        mock_llm.ainvoke.return_value = mock_response

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        search_results = [
            SearchResult(
                title="Reviews",
                url="",
                content="Customer review: Great battery life and excellent performance!"
            )
        ]

        focus_areas = ["battery life", "performance"]

        with patch.object(analyzer, '_assess_authenticity', return_value=0.9):
            reviews = await analyzer.analyze_reviews(search_results, "Test Product", focus_areas)

        assert len(reviews) > 0
        # LLM should have been called with focus areas
        mock_llm.ainvoke.assert_called()

    def test_extract_review_content(self):
        """Test extracting review content from search results."""
        analyzer = ReviewAnalyzer()

        search_results = [
            SearchResult(
                title="Product Specs",
                url="",
                content="Technical specifications and features"  # No review indicators
            ),
            SearchResult(
                title="Customer Reviews",
                url="",
                content="Customer review: This product is amazing! I love the quality and performance. Highly recommend to others."
            ),
            SearchResult(
                title="User Experience",
                url="",
                content="User rating: 5 stars. Excellent product with great customer service. Very satisfied with my purchase."
            ),
            SearchResult(
                title="Price Comparison",
                url="",
                content="Price analysis across different retailers"  # No review indicators
            )
        ]

        review_texts = analyzer._extract_review_content(search_results)

        assert len(review_texts) > 0
        assert any("amazing" in text for text in review_texts)
        assert any("5 stars" in text for text in review_texts)
        # Should not include technical specs or price analysis
        assert not any("Technical specifications" in text for text in review_texts)

    def test_extract_review_content_with_short_content(self):
        """Test extracting review content that filters out short content."""
        analyzer = ReviewAnalyzer()

        search_results = [
            SearchResult(
                title="Short Review",
                url="",
                content="Customer review: Good."  # Too short (< 10 words)
            ),
            SearchResult(
                title="Long Review",
                url="",
                content="Customer review: This is a comprehensive review with more than ten words describing the excellent product quality."
            )
        ]

        review_texts = analyzer._extract_review_content(search_results)

        # Should only include the long review
        assert len(review_texts) == 1
        assert "comprehensive review" in review_texts[0]

    def test_extract_review_content_with_exception(self):
        """Test extracting review content with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('src.agents.review_analyzer.re.split', side_effect=Exception("Regex error")):
            result = analyzer._extract_review_content([])

        assert result == []

    def test_extract_review_sentences(self):
        """Test extracting review-like sentences from content."""
        analyzer = ReviewAnalyzer()

        content = """
        This product is excellent! I love the quality and performance.
        Technical specifications include 16GB RAM.
        The battery life is amazing and I highly recommend this product.
        Price: $999.99.
        Very satisfied with my purchase and would buy again.
        """

        sentences = analyzer._extract_review_sentences(content)

        # Should extract sentences with review language
        assert len(sentences) > 0
        assert any("excellent" in sentence for sentence in sentences)
        assert any("recommend" in sentence for sentence in sentences)
        assert any("satisfied" in sentence for sentence in sentences)
        # Should not include technical specs or price
        assert not any("16GB RAM" in sentence for sentence in sentences)
        assert not any("$999.99" in sentence for sentence in sentences)

    def test_extract_review_sentences_filters_short_sentences(self):
        """Test that short sentences are filtered out."""
        analyzer = ReviewAnalyzer()

        content = "Good. Bad. This is a longer sentence with review language that recommends the product."

        sentences = analyzer._extract_review_sentences(content)

        # Should only include the longer sentence
        assert len(sentences) == 1
        assert "longer sentence" in sentences[0]

    def test_extract_review_sentences_with_exception(self):
        """Test extracting review sentences with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('re.split', side_effect=Exception("Regex error")):
            sentences = analyzer._extract_review_sentences("test content")

        assert sentences == []

    @pytest.mark.asyncio
    async def test_analyze_single_review_without_llm(self):
        """Test analyzing single review without LLM."""
        analyzer = ReviewAnalyzer()
        analyzer.llm = None

        review_text = "This product is excellent! I highly recommend it to everyone."

        review = await analyzer._analyze_single_review(review_text, "Test Product")

        assert review is not None
        assert review.text == review_text
        assert review.sentiment in ["positive", "negative", "mixed", "neutral"]
        assert review.verified is False

    @pytest.mark.asyncio
    async def test_analyze_single_review_with_llm(self):
        """Test analyzing single review with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "positive sentiment - customer loves the product"
        mock_llm.ainvoke.return_value = mock_response

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        review_text = "This product is excellent! I highly recommend it."

        with patch.object(analyzer, '_assess_authenticity', return_value=0.8):
            with patch.object(analyzer, '_extract_rating_from_text', return_value=5.0):
                with patch.object(analyzer, '_extract_date_from_text', return_value="2024-01-01"):
                    with patch.object(analyzer, '_extract_helpful_count', return_value=10):
                        review = await analyzer._analyze_single_review(review_text, "Test Product")

        assert review is not None
        assert review.sentiment == "positive"
        assert review.verified is True  # authenticity > 0.7
        assert review.rating == 5.0
        assert review.date == "2024-01-01"
        assert review.helpful_count == 10

    @pytest.mark.asyncio
    async def test_analyze_single_review_with_exception(self):
        """Test analyzing single review with exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM failed")

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        review = await analyzer._analyze_single_review("test text", "Test Product")

        assert review is None

    @pytest.mark.asyncio
    async def test_analyze_sentiment_with_llm(self):
        """Test sentiment analysis with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "The sentiment is positive - customer recommends the product"
        mock_llm.ainvoke.return_value = mock_response

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        sentiment = await analyzer._analyze_sentiment("Great product!", ["quality"])

        assert sentiment == "positive"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_sentiment_different_sentiments(self):
        """Test sentiment analysis with different sentiment responses."""
        analyzer = ReviewAnalyzer()

        test_cases = [
            ("The product is negative in many ways", "negative"),
            ("This has mixed feelings - good and bad", "mixed"),
            ("The analysis shows neutral response", "neutral"),
            ("Unknown sentiment response", "neutral")  # Default fallback
        ]

        for response_text, expected_sentiment in test_cases:
            mock_llm = AsyncMock()
            mock_response = Mock()
            mock_response.content = response_text
            mock_llm.ainvoke.return_value = mock_response

            analyzer.llm = mock_llm

            sentiment = await analyzer._analyze_sentiment("test text")

            assert sentiment == expected_sentiment

    @pytest.mark.asyncio
    async def test_analyze_sentiment_with_exception(self):
        """Test sentiment analysis with exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM failed")

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        sentiment = await analyzer._analyze_sentiment("Great product!")

        # Should fall back to basic analysis
        assert sentiment == "positive"  # Based on "Great" keyword

    @pytest.mark.asyncio
    async def test_assess_authenticity_without_llm(self):
        """Test authenticity assessment without LLM."""
        analyzer = ReviewAnalyzer()
        analyzer.llm = None

        score = await analyzer._assess_authenticity("This is a detailed review about my purchase experience.")

        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_assess_authenticity_with_llm_score(self):
        """Test authenticity assessment with LLM returning numeric score."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Authenticity score: 0.85 - this review appears genuine"
        mock_llm.ainvoke.return_value = mock_response

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        score = await analyzer._assess_authenticity("Detailed authentic review text")

        assert score == 0.85

    @pytest.mark.asyncio
    async def test_assess_authenticity_with_llm_keywords(self):
        """Test authenticity assessment with LLM returning keywords."""
        analyzer = ReviewAnalyzer()

        test_cases = [
            ("This review appears genuine and authentic", 0.8),
            ("The review seems suspicious and potentially fake", 0.3),
            ("The review is of average quality", 0.6)  # Default fallback
        ]

        for response_text, expected_score in test_cases:
            mock_llm = AsyncMock()
            mock_response = Mock()
            mock_response.content = response_text
            mock_llm.ainvoke.return_value = mock_response

            analyzer.llm = mock_llm

            score = await analyzer._assess_authenticity("test review")

            assert score == expected_score

    @pytest.mark.asyncio
    async def test_assess_authenticity_with_exception(self):
        """Test authenticity assessment with exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM failed")

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        score = await analyzer._assess_authenticity("test review")

        assert score == 0.5  # Neutral score on error

    def test_basic_sentiment_analysis(self):
        """Test basic sentiment analysis using keywords."""
        analyzer = ReviewAnalyzer()

        test_cases = [
            ("This product is excellent and amazing!", "positive"),
            ("Terrible quality and awful experience", "negative"),
            ("Good points but also bad aspects", "mixed"),
            ("The product specifications are standard", "neutral")
        ]

        for text, expected_sentiment in test_cases:
            sentiment = analyzer._basic_sentiment_analysis(text)
            assert sentiment == expected_sentiment

    def test_basic_sentiment_analysis_with_exception(self):
        """Test basic sentiment analysis with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('builtins.sum', side_effect=Exception("Sum error")):
            sentiment = analyzer._basic_sentiment_analysis("test text")

        assert sentiment == "neutral"

    def test_basic_authenticity_check(self):
        """Test basic authenticity check using heuristics."""
        analyzer = ReviewAnalyzer()

        # Detailed review with personal experience
        detailed_text = "I purchased this product last month and have been using it daily. The quality is excellent and I highly recommend it to others."
        score = analyzer._basic_authenticity_check(detailed_text)
        assert score > 0.5  # Should be considered more authentic

        # Short, generic review
        generic_text = "Good product!!!!!!"  # Excessive exclamation marks
        score = analyzer._basic_authenticity_check(generic_text)
        assert score < 0.5  # Should be considered less authentic

        # Review with time references
        time_ref_text = "After using this for three months, I can say it's reliable."
        score = analyzer._basic_authenticity_check(time_ref_text)
        assert score > 0.5

    def test_basic_authenticity_check_with_exception(self):
        """Test basic authenticity check with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('builtins.len', side_effect=Exception("Length error")):
            score = analyzer._basic_authenticity_check("test review")

        assert score == 0.5  # Neutral score on error

    def test_extract_rating_from_text(self):
        """Test extracting rating from review text."""
        analyzer = ReviewAnalyzer()

        test_cases = [
            ("I give this 5 out of 5 stars", 5.0),
            ("Rating: 4.5 stars", 4.5),
            ("4/5 overall rating", 4.0),
            ("My rating: 3", 3.0),
            ("No rating mentioned", None),
            ("Rating: 6 stars", None),  # Invalid rating > 5
            ("Rating: -1", None)  # Invalid negative rating
        ]

        for text, expected_rating in test_cases:
            rating = analyzer._extract_rating_from_text(text)

            if expected_rating is None:
                assert rating is None
            else:
                assert rating == expected_rating

    def test_extract_rating_from_text_with_exception(self):
        """Test extracting rating with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('re.search', side_effect=Exception("Regex error")):
            rating = analyzer._extract_rating_from_text("5 stars")

        assert rating is None

    def test_extract_date_from_text(self):
        """Test extracting date from review text."""
        analyzer = ReviewAnalyzer()

        test_cases = [
            ("Reviewed on 12/25/2023", "12/25/2023"),
            ("Posted January 15, 2024", "January 15, 2024"),
            ("Date: 2024-03-20", "2024-03-20"),
            ("No date mentioned", None)
        ]

        for text, expected_date in test_cases:
            date = analyzer._extract_date_from_text(text)

            if expected_date is None:
                assert date is None
            else:
                assert date == expected_date

    def test_extract_date_from_text_with_exception(self):
        """Test extracting date with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('re.search', side_effect=Exception("Regex error")):
            date = analyzer._extract_date_from_text("2024-01-01")

        assert date is None

    def test_extract_helpful_count(self):
        """Test extracting helpful count from review text."""
        analyzer = ReviewAnalyzer()

        test_cases = [
            ("25 people found this helpful", 25),
            ("Helpful (100)", 100),
            ("1,234 helpful votes", 1234),
            ("No helpful count", 0)
        ]

        for text, expected_count in test_cases:
            count = analyzer._extract_helpful_count(text)
            assert count == expected_count

    def test_extract_helpful_count_with_exception(self):
        """Test extracting helpful count with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('re.search', side_effect=Exception("Regex error")):
            count = analyzer._extract_helpful_count("25 helpful")

        assert count == 0

    @pytest.mark.asyncio
    async def test_summarize_reviews_empty_list(self):
        """Test summarizing empty review list."""
        analyzer = ReviewAnalyzer()

        result = await analyzer.summarize_reviews([])

        assert "error" in result
        assert "No reviews to summarize" in result["error"]

    @pytest.mark.asyncio
    async def test_summarize_reviews_with_data(self):
        """Test summarizing reviews with actual data."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Overall positive sentiment with customers praising quality"
        mock_llm.ainvoke.return_value = mock_response

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        reviews = [
            Review(text="Great product", sentiment="positive", rating=5.0, verified=True),
            Review(text="Good quality", sentiment="positive", rating=4.0, verified=True),
            Review(text="Average product", sentiment="neutral", rating=3.0, verified=False),
            Review(text="Poor quality", sentiment="negative", rating=2.0, verified=False)
        ]

        result = await analyzer.summarize_reviews(reviews, ["quality", "performance"])

        assert result["total_reviews"] == 4
        assert result["sentiment_distribution"]["positive"] == 2
        assert result["sentiment_distribution"]["neutral"] == 1
        assert result["sentiment_distribution"]["negative"] == 1
        assert result["average_rating"] == 3.5  # (5+4+3+2)/4
        assert result["authenticity_rate"] == 0.5  # 2 verified out of 4
        assert result["verified_reviews"] == 2
        assert result["focus_areas"] == ["quality", "performance"]
        assert "positive sentiment" in result["summary"]

    @pytest.mark.asyncio
    async def test_summarize_reviews_without_ratings(self):
        """Test summarizing reviews without ratings."""
        analyzer = ReviewAnalyzer()
        analyzer.llm = None

        reviews = [
            Review(text="Great product", sentiment="positive"),
            Review(text="Poor quality", sentiment="negative")
        ]

        result = await analyzer.summarize_reviews(reviews)

        assert result["total_reviews"] == 2
        assert result["average_rating"] is None
        assert result["authenticity_rate"] == 0.0  # No verified reviews

    @pytest.mark.asyncio
    async def test_summarize_reviews_with_exception(self):
        """Test summarizing reviews with exception."""
        analyzer = ReviewAnalyzer()

        # Mock Counter's most_common method to cause exception
        with patch.object(Counter, 'most_common', side_effect=Exception("Counter error")):
            result = await analyzer.summarize_reviews([Review(text="test")])

        assert "error" in result
        assert "Summary generation failed" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_review_summary_without_llm(self):
        """Test generating review summary without LLM."""
        analyzer = ReviewAnalyzer()
        analyzer.llm = None

        reviews = [
            Review(text="Great", sentiment="positive"),
            Review(text="Bad", sentiment="negative")
        ]

        summary = await analyzer._generate_review_summary(reviews)

        assert "Analysis of 2 reviews" in summary
        assert "Positive:" in summary
        assert "Negative:" in summary

    @pytest.mark.asyncio
    async def test_generate_review_summary_with_llm(self):
        """Test generating review summary with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Comprehensive review analysis showing mixed sentiment"
        mock_llm.ainvoke.return_value = mock_response

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        reviews = [Review(text="Test review", sentiment="mixed")]

        summary = await analyzer._generate_review_summary(reviews, ["quality"])

        assert summary == "Comprehensive review analysis showing mixed sentiment"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_review_summary_with_exception(self):
        """Test generating review summary with exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM failed")

        analyzer = ReviewAnalyzer()
        analyzer.llm = mock_llm

        reviews = [Review(text="Test", sentiment="positive")]

        summary = await analyzer._generate_review_summary(reviews)

        # Should fall back to basic summary
        assert "Analysis of 1 reviews" in summary
        assert "Positive:" in summary

    def test_basic_review_summary(self):
        """Test basic review summary generation."""
        analyzer = ReviewAnalyzer()

        reviews = [
            Review(text="Great", sentiment="positive"),
            Review(text="Good", sentiment="positive"),
            Review(text="Bad", sentiment="negative"),
            Review(text="Okay", sentiment="neutral")
        ]

        summary = analyzer._basic_review_summary(reviews)

        assert "Analysis of 4 reviews" in summary
        assert "Positive: 2 reviews (50.0%)" in summary
        assert "Negative: 1 reviews (25.0%)" in summary
        assert "Neutral: 1 reviews (25.0%)" in summary
        assert "Overall sentiment appears positive" in summary

    def test_basic_review_summary_negative_majority(self):
        """Test basic review summary with negative majority."""
        analyzer = ReviewAnalyzer()

        reviews = [
            Review(text="Bad", sentiment="negative"),
            Review(text="Terrible", sentiment="negative"),
            Review(text="Good", sentiment="positive")
        ]

        summary = analyzer._basic_review_summary(reviews)

        assert "Overall sentiment appears negative" in summary

    def test_basic_review_summary_mixed(self):
        """Test basic review summary with mixed sentiment."""
        analyzer = ReviewAnalyzer()

        reviews = [
            Review(text="Good", sentiment="positive"),
            Review(text="Bad", sentiment="negative")
        ]

        summary = analyzer._basic_review_summary(reviews)

        assert "Sentiment appears mixed or neutral" in summary

    def test_basic_review_summary_with_exception(self):
        """Test basic review summary with exception."""
        analyzer = ReviewAnalyzer()

        # Mock Counter's most_common method to cause exception
        with patch.object(Counter, 'most_common', side_effect=Exception("Counter error")):
            summary = analyzer._basic_review_summary([Review(text="test")])

        assert summary == "Unable to generate review summary."

    def test_prepare_reviews_for_summary(self):
        """Test preparing reviews for LLM summary."""
        analyzer = ReviewAnalyzer()

        reviews = [
            Review(text="This is a great product with excellent quality", sentiment="positive", rating=5.0),
            Review(text="Poor quality and terrible customer service", sentiment="negative", rating=1.0),
            Review(text="Average product with some good and bad points", sentiment="mixed")
        ]

        formatted = analyzer._prepare_reviews_for_summary(reviews)

        assert "Review 1:" in formatted
        assert "Sentiment: positive" in formatted
        assert "Rating: 5.0/5" in formatted
        assert "This is a great product" in formatted

        assert "Review 2:" in formatted
        assert "Sentiment: negative" in formatted
        assert "Rating: 1.0/5" in formatted

        assert "Review 3:" in formatted
        assert "Sentiment: mixed" in formatted
        # Should not include rating line for review without rating

    def test_prepare_reviews_for_summary_large_list(self):
        """Test preparing large review list (should limit to 10)."""
        analyzer = ReviewAnalyzer()

        reviews = [Review(text=f"Review {i}", sentiment="positive") for i in range(15)]

        formatted = analyzer._prepare_reviews_for_summary(reviews)

        # Should only include first 10 reviews
        assert "Review 1:" in formatted
        assert "Review 10:" in formatted
        assert "Review 11:" not in formatted

    def test_prepare_reviews_for_summary_with_exception(self):
        """Test preparing reviews for summary with exception."""
        analyzer = ReviewAnalyzer()

        # Mock to cause exception
        with patch('builtins.enumerate', side_effect=Exception("Enumerate error")):
            formatted = analyzer._prepare_reviews_for_summary([])

        assert formatted == "Error formatting reviews for analysis."

    @pytest.mark.asyncio
    async def test_analyze_reviews_limit_to_10(self):
        """Test that review analysis limits to 10 reviews."""
        analyzer = ReviewAnalyzer()
        analyzer.llm = None

        # Create search results that would generate many reviews
        search_results = []
        for i in range(20):
            search_results.append(
                SearchResult(
                    title=f"Review {i}",
                    url="",
                    content=f"Customer review: This is review number {i} with great quality and excellent performance."
                )
            )

        reviews = await analyzer.analyze_reviews(search_results, "Test Product")

        # Should be limited to 10 reviews max
        assert len(reviews) <= 10

    def test_extract_review_content_removes_duplicates(self):
        """Test that duplicate review content is removed."""
        analyzer = ReviewAnalyzer()

        search_results = [
            SearchResult(
                title="Review 1",
                url="",
                content="Customer review: This is a great product with excellent quality."
            ),
            SearchResult(
                title="Review 2",
                url="",
                content="Customer review: This is a great product with excellent quality."  # Duplicate
            ),
            SearchResult(
                title="Review 3",
                url="",
                content="Customer review: This is a different review with good performance."
            )
        ]

        review_texts = analyzer._extract_review_content(search_results)

        # Should remove duplicates
        assert len(review_texts) == 2
        assert len(set(review_texts)) == len(review_texts)  # All unique