"""Comprehensive tests for the orchestrator agent."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List

from src.agents.orchestrator import ProductResearchOrchestrator, ResearchState
from src.core.models import ResearchQuery, ResearchResult, Product, Review, ProductCategory
from src.tools.tavily_shopping import TavilyShoppingTool


class TestProductResearchOrchestrator:
    """Test ProductResearchOrchestrator functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_openai_key = "test-openai-key"
        self.mock_tavily_key = "test-tavily-key"

    def test_orchestrator_initialization_without_api_key(self):
        """Test orchestrator initialization without OpenAI API key."""
        with patch('src.agents.orchestrator.settings') as mock_settings:
            mock_settings.openai_api_key = None

            orchestrator = ProductResearchOrchestrator()

            assert orchestrator.llm is None
            assert orchestrator.tavily_tool is not None
            assert orchestrator.workflow is not None

    def test_orchestrator_initialization_with_api_key(self):
        """Test orchestrator initialization with OpenAI API key."""
        with patch('src.agents.orchestrator.settings') as mock_settings:
            mock_settings.openai_api_key = self.mock_openai_key
            mock_settings.model_name = "gpt-5"
            mock_settings.max_tokens = 4000
            mock_settings.reasoning_effort = "high"
            mock_settings.service_tier = "default"

            with patch('src.agents.orchestrator.ChatOpenAI') as mock_chat_openai:
                orchestrator = ProductResearchOrchestrator()

                assert orchestrator.llm is not None
                mock_chat_openai.assert_called_once()

    def test_workflow_building(self):
        """Test workflow graph construction."""
        with patch('src.agents.orchestrator.settings') as mock_settings:
            mock_settings.openai_api_key = None

            orchestrator = ProductResearchOrchestrator()
            workflow = orchestrator._build_workflow()

            assert workflow is not None
            # Test that the workflow was compiled successfully
            assert hasattr(workflow, 'invoke')

    @pytest.mark.asyncio
    async def test_parse_query_without_llm(self):
        """Test query parsing without LLM available."""
        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = None

        initial_state = ResearchState(
            query=ResearchQuery(query="test laptop"),
            raw_search_results=[],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="start",
            error=None
        )

        result_state = await orchestrator._parse_query(initial_state)

        assert result_state["error"] == "LLM not initialized - missing OpenAI API key"

    @pytest.mark.asyncio
    async def test_parse_query_with_llm(self):
        """Test query parsing with LLM available."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Enhanced query: best laptop for programming under $2000"
        mock_llm.ainvoke.return_value = mock_response

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop for programming"),
            raw_search_results=[],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="start",
            error=None
        )

        result_state = await orchestrator._parse_query(initial_state)

        assert result_state["current_step"] == "parse_query"
        assert "Enhanced query:" in result_state["query"].query
        assert result_state["error"] is None
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_query_with_exception(self):
        """Test query parsing with exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("API Error")

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        initial_state = ResearchState(
            query=ResearchQuery(query="test query"),
            raw_search_results=[],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="start",
            error=None
        )

        result_state = await orchestrator._parse_query(initial_state)

        assert "Query parsing failed: API Error" in result_state["error"]

    @pytest.mark.asyncio
    async def test_search_products_success(self):
        """Test successful product search."""
        mock_tavily_tool = AsyncMock()
        mock_search_results = {
            "raw_results": [{"title": "Test Product", "content": "Description"}],
            "products": [Product(name="Test Laptop", price=999.99)]
        }
        mock_tavily_tool.get_shopping_results.return_value = mock_search_results

        orchestrator = ProductResearchOrchestrator()
        orchestrator.tavily_tool = mock_tavily_tool

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="start",
            error=None
        )

        result_state = await orchestrator._search_products(initial_state)

        assert result_state["current_step"] == "search_products"
        assert len(result_state["products"]) == 1
        assert len(result_state["raw_search_results"]) == 1
        assert result_state["error"] is None

    @pytest.mark.asyncio
    async def test_search_products_with_exception(self):
        """Test product search with exception."""
        mock_tavily_tool = AsyncMock()
        mock_tavily_tool.get_shopping_results.side_effect = Exception("Search failed")

        orchestrator = ProductResearchOrchestrator()
        orchestrator.tavily_tool = mock_tavily_tool

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="start",
            error=None
        )

        result_state = await orchestrator._search_products(initial_state)

        assert "Product search failed: Search failed" in result_state["error"]

    @pytest.mark.asyncio
    async def test_analyze_products_without_llm(self):
        """Test product analysis without LLM."""
        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = None

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[Product(name="Test Laptop")],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="search_products",
            error=None
        )

        result_state = await orchestrator._analyze_products(initial_state)

        # Should return state unchanged when no LLM
        assert result_state["current_step"] == "search_products"

    @pytest.mark.asyncio
    async def test_analyze_products_with_llm(self):
        """Test product analysis with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Product analysis: Test laptop is good value for money"
        mock_llm.ainvoke.return_value = mock_response

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        products = [
            Product(name="Test Laptop", price=999.99, brand="TestBrand"),
            Product(name="Another Laptop", price=1299.99, brand="AnotherBrand")
        ]

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=products,
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="search_products",
            error=None
        )

        result_state = await orchestrator._analyze_products(initial_state)

        assert result_state["current_step"] == "analyze_products"
        assert result_state["error"] is None
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_products_with_exception(self):
        """Test product analysis with exception."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("Analysis failed")

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[Product(name="Test Laptop")],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="search_products",
            error=None
        )

        result_state = await orchestrator._analyze_products(initial_state)

        assert "Product analysis failed: Analysis failed" in result_state["error"]

    @pytest.mark.asyncio
    async def test_analyze_reviews_without_llm(self):
        """Test review analysis without LLM."""
        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = None

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[{"content": "Great laptop, highly recommended"}],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="analyze_products",
            error=None
        )

        result_state = await orchestrator._analyze_reviews(initial_state)

        # Should return state unchanged when no LLM
        assert result_state["current_step"] == "analyze_products"

    @pytest.mark.asyncio
    async def test_analyze_reviews_with_no_review_content(self):
        """Test review analysis with no review content found."""
        mock_llm = AsyncMock()

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[{"content": "Product specifications only"}],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="analyze_products",
            error=None
        )

        result_state = await orchestrator._analyze_reviews(initial_state)

        assert result_state["reviews"] == []

    @pytest.mark.asyncio
    async def test_analyze_reviews_with_content(self):
        """Test review analysis with review content."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Reviews show mostly positive sentiment with good performance ratings"
        mock_llm.ainvoke.return_value = mock_response

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        raw_results = [
            {"content": "This laptop has great reviews from customers who purchased it"},
            {"content": "Customer review: Excellent performance and battery life"}
        ]

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=raw_results,
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="analyze_products",
            error=None
        )

        result_state = await orchestrator._analyze_reviews(initial_state)

        assert result_state["current_step"] == "analyze_reviews"
        assert len(result_state["reviews"]) == 1
        assert result_state["reviews"][0].sentiment == "analyzed"

    @pytest.mark.asyncio
    async def test_generate_recommendation_without_llm(self):
        """Test recommendation generation without LLM."""
        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = None

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[Product(name="Test Laptop")],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="analyze_reviews",
            error=None
        )

        result_state = await orchestrator._generate_recommendation(initial_state)

        # Should return state unchanged when no LLM
        assert result_state["current_step"] == "analyze_reviews"

    @pytest.mark.asyncio
    async def test_generate_recommendation_with_llm(self):
        """Test recommendation generation with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "I recommend the Test Laptop for its excellent value and performance"
        mock_llm.ainvoke.return_value = mock_response

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[Product(name="Test Laptop", price=999.99)],
            reviews=[Review(text="Great laptop", sentiment="positive")],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="analyze_reviews",
            error=None
        )

        result_state = await orchestrator._generate_recommendation(initial_state)

        assert result_state["current_step"] == "generate_recommendation"
        assert "Test Laptop" in result_state["recommendation"]
        assert result_state["error"] is None

    @pytest.mark.asyncio
    async def test_find_alternatives(self):
        """Test finding alternative products."""
        orchestrator = ProductResearchOrchestrator()

        products = [
            Product(name="Primary Laptop", price=999.99),
            Product(name="Alternative 1", price=1299.99),
            Product(name="Alternative 2", price=799.99),
            Product(name="Alternative 3", price=1599.99),
            Product(name="Alternative 4", price=699.99)
        ]

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=products,
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="generate_recommendation",
            error=None
        )

        result_state = await orchestrator._find_alternatives(initial_state)

        assert result_state["current_step"] == "find_alternatives"
        assert len(result_state["alternatives"]) == 3  # Should take products 1-3 as alternatives
        assert result_state["alternatives"][0].name == "Alternative 1"

    @pytest.mark.asyncio
    async def test_find_alternatives_with_single_product(self):
        """Test finding alternatives with only one product."""
        orchestrator = ProductResearchOrchestrator()

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[Product(name="Only Laptop", price=999.99)],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="generate_recommendation",
            error=None
        )

        result_state = await orchestrator._find_alternatives(initial_state)

        assert result_state["alternatives"] == []

    @pytest.mark.asyncio
    async def test_synthesize_results_without_llm(self):
        """Test result synthesis without LLM."""
        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = None

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[Product(name="Test Laptop")],
            reviews=[],
            summary=None,
            recommendation="Recommended laptop",
            alternatives=[],
            messages=[],
            current_step="find_alternatives",
            error=None
        )

        result_state = await orchestrator._synthesize_results(initial_state)

        # When no LLM, current_step is not updated (returns early)
        assert result_state["current_step"] == "find_alternatives"
        assert "limited analysis due to missing API key" in result_state["summary"]

    @pytest.mark.asyncio
    async def test_synthesize_results_with_llm(self):
        """Test result synthesis with LLM."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Executive summary: Research found 2 laptops with Test Laptop being the best choice"
        mock_llm.ainvoke.return_value = mock_response

        orchestrator = ProductResearchOrchestrator()
        orchestrator.llm = mock_llm

        initial_state = ResearchState(
            query=ResearchQuery(query="laptop"),
            raw_search_results=[],
            products=[Product(name="Test Laptop"), Product(name="Another Laptop")],
            reviews=[],
            summary=None,
            recommendation="Test Laptop recommended",
            alternatives=[Product(name="Alternative Laptop")],
            messages=[],
            current_step="find_alternatives",
            error=None
        )

        result_state = await orchestrator._synthesize_results(initial_state)

        assert result_state["current_step"] == "synthesize_results"
        assert "Executive summary:" in result_state["summary"]
        assert result_state["error"] is None

    def test_format_products_for_analysis(self):
        """Test product formatting for LLM analysis."""
        orchestrator = ProductResearchOrchestrator()

        products = [
            Product(
                name="Test Laptop",
                price=999.99,
                brand="TestBrand",
                url="https://example.com/laptop",
                description="A great laptop for testing purposes with excellent performance"
            ),
            Product(
                name="Another Laptop",
                price=1299.99,
                brand="AnotherBrand"
            )
        ]

        formatted = orchestrator._format_products_for_analysis(products)

        assert "1. Test Laptop" in formatted
        assert "Price: $999.99" in formatted
        assert "Brand: TestBrand" in formatted
        assert "2. Another Laptop" in formatted
        assert "Price: $1299.99" in formatted

    def test_extract_review_content(self):
        """Test review content extraction from search results."""
        orchestrator = ProductResearchOrchestrator()

        search_results = [
            {"content": "Product specifications and technical details"},
            {"content": "Customer review: This laptop is amazing, highly recommend it"},
            {"content": "Great rating from buyers who purchased this product"},
            {"content": "Price comparison across different retailers"}
        ]

        review_content = orchestrator._extract_review_content(search_results)

        assert "Customer review:" in review_content
        assert "rating from buyers" in review_content
        assert "Product specifications" not in review_content

    def test_build_recommendation_context(self):
        """Test building context for recommendation generation."""
        orchestrator = ProductResearchOrchestrator()

        products = [Product(name="Test Laptop", price=999.99, brand="TestBrand")]
        reviews = [Review(text="Great laptop with excellent performance", sentiment="positive")]

        state = ResearchState(
            query=ResearchQuery(query="laptop for programming"),
            raw_search_results=[],
            products=products,
            reviews=reviews,
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="generate_recommendation",
            error=None
        )

        context = orchestrator._build_recommendation_context(state)

        assert "laptop for programming" in context
        assert "Test Laptop" in context
        assert "Great laptop with excellent performance" in context

    @pytest.mark.asyncio
    async def test_research_product_complete_flow(self):
        """Test complete product research flow."""
        with patch('src.agents.orchestrator.settings') as mock_settings:
            mock_settings.openai_api_key = None

            # Mock the tavily tool
            mock_tavily_tool = AsyncMock()
            mock_search_results = {
                "raw_results": [{"content": "Great product with customer reviews"}],
                "products": [Product(name="Test Laptop", price=999.99)]
            }
            mock_tavily_tool.get_shopping_results.return_value = mock_search_results

            orchestrator = ProductResearchOrchestrator()
            orchestrator.tavily_tool = mock_tavily_tool

            # Mock the workflow to return a simple state
            mock_workflow = AsyncMock()
            final_state = ResearchState(
                query=ResearchQuery(query="laptop for programming"),
                raw_search_results=[{"content": "test"}],
                products=[Product(name="Test Laptop", price=999.99)],
                reviews=[],
                summary="Research completed",
                recommendation="Test Laptop recommended",
                alternatives=[],
                messages=[],
                current_step="synthesize_results",
                error=None
            )
            mock_workflow.ainvoke.return_value = final_state
            orchestrator.workflow = mock_workflow

            result = await orchestrator.research_product("laptop for programming")

            assert isinstance(result, ResearchResult)
            assert result.query.query == "laptop for programming"
            assert len(result.products) == 1
            assert result.summary == "Research completed"
            assert result.recommendation == "Test Laptop recommended"
            assert result.total_research_time is not None

    @pytest.mark.asyncio
    async def test_research_product_with_workflow_exception(self):
        """Test product research with workflow exception."""
        with patch('src.agents.orchestrator.settings') as mock_settings:
            mock_settings.openai_api_key = None

            orchestrator = ProductResearchOrchestrator()

            # Mock workflow to raise exception
            mock_workflow = AsyncMock()
            mock_workflow.ainvoke.side_effect = Exception("Workflow failed")
            orchestrator.workflow = mock_workflow

            result = await orchestrator.research_product("test query")

            assert isinstance(result, ResearchResult)
            assert "Research failed: Workflow failed" in result.summary
            assert result.query.query == "test query"

    @pytest.mark.asyncio
    async def test_research_product_with_state_error(self):
        """Test product research with error in final state."""
        with patch('src.agents.orchestrator.settings') as mock_settings:
            mock_settings.openai_api_key = None

            orchestrator = ProductResearchOrchestrator()

            # Mock workflow to return state with error
            mock_workflow = AsyncMock()
            final_state = ResearchState(
                query=ResearchQuery(query="test query"),
                raw_search_results=[],
                products=[],
                reviews=[],
                summary=None,
                recommendation=None,
                alternatives=[],
                messages=[],
                current_step="error",
                error="Search API failed"
            )
            mock_workflow.ainvoke.return_value = final_state
            orchestrator.workflow = mock_workflow

            result = await orchestrator.research_product("test query")

            assert isinstance(result, ResearchResult)
            assert result.query.query == "test query"
            # The error should be logged but result should still be returned

    def test_extract_review_content_edge_cases(self):
        """Test review content extraction edge cases."""
        orchestrator = ProductResearchOrchestrator()

        # Test with empty search results
        empty_results = []
        content = orchestrator._extract_review_content(empty_results)
        assert content == ""

        # Test with results containing no review indicators
        no_review_results = [
            {"content": "Technical specifications only"},
            {"content": "Price information and availability"}
        ]
        content = orchestrator._extract_review_content(no_review_results)
        assert content == ""

        # Test with mixed content
        mixed_results = [
            {"content": "Product specs: 16GB RAM, 512GB SSD"},
            {"content": "Customer review: Amazing laptop, 5 stars!"},
            {"content": "Price comparison data"},
            {"content": "User rating: 4.5 out of 5 stars"}
        ]
        content = orchestrator._extract_review_content(mixed_results)
        assert "Customer review:" in content
        assert "User rating:" in content
        assert "Product specs:" not in content

    def test_format_products_edge_cases(self):
        """Test product formatting edge cases."""
        orchestrator = ProductResearchOrchestrator()

        # Test with empty product list
        formatted = orchestrator._format_products_for_analysis([])
        assert formatted == ""

        # Test with product having minimal data
        minimal_product = Product(name="Minimal Product")
        formatted = orchestrator._format_products_for_analysis([minimal_product])

        assert "1. Minimal Product" in formatted
        assert "Price: $N/A" in formatted
        assert "Brand: Unknown" in formatted
        assert "URL: N/A" in formatted

    def test_build_recommendation_context_edge_cases(self):
        """Test recommendation context building edge cases."""
        orchestrator = ProductResearchOrchestrator()

        # Test with minimal state
        minimal_state = ResearchState(
            query=ResearchQuery(query="test"),
            raw_search_results=[],
            products=[],
            reviews=[],
            summary=None,
            recommendation=None,
            alternatives=[],
            messages=[],
            current_step="test",
            error=None
        )

        context = orchestrator._build_recommendation_context(minimal_state)

        assert "test" in context
        assert "Products Found: 0" in context
        assert "No review analysis available" in context