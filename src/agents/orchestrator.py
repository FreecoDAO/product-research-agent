"""Orchestrator agent using DeepAgents framework with GPT-5."""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from .freeco_prompts import FREECO_SHOPPING_PROMPT
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.core.config import settings
from src.core.models import ResearchQuery, ResearchResult, Product, Review
from src.tools.tavily_shopping import TavilyShoppingTool

logger = logging.getLogger(__name__)


class ResearchState(TypedDict):
    """State for the research workflow."""
    query: ResearchQuery
    raw_search_results: List[Dict[str, Any]]
    products: List[Product]
    reviews: List[Review]
    summary: Optional[str]
    recommendation: Optional[str]
    alternatives: List[Product]
    messages: List[Dict[str, Any]]
    current_step: str
    error: Optional[str]


class ProductResearchOrchestrator:
    """Orchestrator agent that coordinates the research workflow using DeepAgents pattern."""

    def __init__(self):
        """Initialize the orchestrator with GPT-5 and tools."""
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not provided - orchestrator will not function")
            self.llm = None
        else:
            # Build kwargs — base_url enables Novita AI / any OpenAI-compatible provider
            llm_kwargs = dict(
                model=settings.model_name,
                api_key=settings.openai_api_key,
                temperature=0.1,
                max_tokens=settings.max_tokens,
            )
            if settings.openai_base_url:
                llm_kwargs["base_url"] = settings.openai_base_url
            self.llm = ChatOpenAI(**llm_kwargs)

        self.tavily_tool = TavilyShoppingTool()
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the research workflow graph using LangGraph."""
        workflow = StateGraph(ResearchState)

        # Define workflow nodes
        workflow.add_node("parse_query", self._parse_query)
        workflow.add_node("search_products", self._search_products)
        workflow.add_node("analyze_products", self._analyze_products)
        workflow.add_node("analyze_reviews", self._analyze_reviews)
        workflow.add_node("generate_recommendation", self._generate_recommendation)
        workflow.add_node("find_alternatives", self._find_alternatives)
        workflow.add_node("synthesize_results", self._synthesize_results)

        # Define workflow edges
        workflow.set_entry_point("parse_query")
        workflow.add_edge("parse_query", "search_products")
        workflow.add_edge("search_products", "analyze_products")
        workflow.add_edge("analyze_products", "analyze_reviews")
        workflow.add_edge("analyze_reviews", "generate_recommendation")
        workflow.add_edge("generate_recommendation", "find_alternatives")
        workflow.add_edge("find_alternatives", "synthesize_results")
        workflow.add_edge("synthesize_results", END)

        return workflow.compile()

    async def _parse_query(self, state: ResearchState) -> ResearchState:
        """Parse and enhance the user query."""
        try:
            logger.info(f"Parsing query: {state['query'].query}")

            if not self.llm:
                state["error"] = "LLM not initialized - missing OpenAI API key"
                return state

            system_prompt = """You are a product research assistant. Analyze the user's query and extract key information:
            - Product category
            - Price range (if mentioned)
            - Key features or requirements
            - Use case or purpose

            Enhance the query for better search results while preserving the original intent."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Original query: {state['query'].query}")
            ]

            response = await self.llm.ainvoke(messages)
            enhanced_query = response.content

            # Update query with enhanced version for search
            state["query"].query = enhanced_query
            state["current_step"] = "parse_query"
            state["messages"] = add_messages(state.get("messages", []),
                                           [{"role": "assistant", "content": f"Enhanced query: {enhanced_query}"}])

            logger.info(f"Enhanced query: {enhanced_query}")
            return state

        except Exception as e:
            logger.error(f"Error in parse_query: {e}")
            state["error"] = f"Query parsing failed: {str(e)}"
            return state

    async def _search_products(self, state: ResearchState) -> ResearchState:
        """Search for products using Tavily tool."""
        try:
            logger.info(f"Searching products for: {state['query'].query}")

            search_results = await self.tavily_tool.get_shopping_results(state["query"].query)

            state["raw_search_results"] = search_results.get("raw_results", [])
            state["products"] = search_results.get("products", [])
            state["current_step"] = "search_products"

            logger.info(f"Found {len(state['products'])} products")
            return state

        except Exception as e:
            logger.error(f"Error in search_products: {e}")
            state["error"] = f"Product search failed: {str(e)}"
            return state

    async def _analyze_products(self, state: ResearchState) -> ResearchState:
        """Analyze and rank products using GPT-5."""
        try:
            logger.info("Analyzing products")

            if not self.llm or not state["products"]:
                return state

            products_summary = self._format_products_for_analysis(state["products"][:5])  # Top 5

            system_prompt = """You are a product analyst. Analyze these products and:
            1. Rank them by relevance to the user's query
            2. Identify key differences in specifications
            3. Note any standout features or concerns
            4. Assess value for money

            Focus on factual analysis based on available data."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Query: {state['query'].query}\n\nProducts:\n{products_summary}")
            ]

            response = await self.llm.ainvoke(messages)
            analysis = response.content

            state["current_step"] = "analyze_products"
            state["messages"] = add_messages(state.get("messages", []),
                                           [{"role": "assistant", "content": f"Product analysis: {analysis}"}])

            return state

        except Exception as e:
            logger.error(f"Error in analyze_products: {e}")
            state["error"] = f"Product analysis failed: {str(e)}"
            return state

    async def _analyze_reviews(self, state: ResearchState) -> ResearchState:
        """Analyze reviews from search results."""
        try:
            logger.info("Analyzing reviews")

            if not self.llm:
                return state

            # Extract review-like content from search results
            review_content = self._extract_review_content(state["raw_search_results"])

            if not review_content:
                state["reviews"] = []
                return state

            system_prompt = """You are a review analyst. Analyze customer feedback and:
            1. Identify common themes (positive and negative)
            2. Assess sentiment distribution
            3. Flag any potential authenticity concerns
            4. Summarize key insights about product quality and user experience

            Focus on actionable insights for purchase decisions."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Review content to analyze:\n{review_content}")
            ]

            response = await self.llm.ainvoke(messages)
            review_analysis = response.content

            # Create review objects (simplified for MVP)
            state["reviews"] = [
                Review(
                    text=review_analysis,
                    sentiment="analyzed",
                    verified=False
                )
            ]

            state["current_step"] = "analyze_reviews"
            state["messages"] = add_messages(state.get("messages", []),
                                           [{"role": "assistant", "content": f"Review analysis: {review_analysis}"}])

            return state

        except Exception as e:
            logger.error(f"Error in analyze_reviews: {e}")
            state["error"] = f"Review analysis failed: {str(e)}"
            return state

    async def _generate_recommendation(self, state: ResearchState) -> ResearchState:
        """Generate product recommendation based on analysis."""
        try:
            logger.info("Generating recommendation")

            if not self.llm:
                return state

            context = self._build_recommendation_context(state)

            system_prompt = """You are a product recommendation expert. Based on the research and analysis:
            1. Recommend the best product for the user's needs
            2. Explain why it's the best choice
            3. Mention any important considerations or trade-offs
            4. Be specific about how it meets their requirements

            Keep recommendations practical and evidence-based."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ]

            response = await self.llm.ainvoke(messages)
            recommendation = response.content

            state["recommendation"] = recommendation
            state["current_step"] = "generate_recommendation"

            return state

        except Exception as e:
            logger.error(f"Error in generate_recommendation: {e}")
            state["error"] = f"Recommendation generation failed: {str(e)}"
            return state

    async def _find_alternatives(self, state: ResearchState) -> ResearchState:
        """Find alternative products."""
        try:
            logger.info("Finding alternatives")

            # For MVP, use remaining products as alternatives
            if len(state["products"]) > 1:
                state["alternatives"] = state["products"][1:4]  # Take 2-3 alternatives
            else:
                state["alternatives"] = []

            state["current_step"] = "find_alternatives"
            return state

        except Exception as e:
            logger.error(f"Error in find_alternatives: {e}")
            state["error"] = f"Alternative finding failed: {str(e)}"
            return state

    async def _synthesize_results(self, state: ResearchState) -> ResearchState:
        """Synthesize final results."""
        try:
            logger.info("Synthesizing results")

            if not self.llm:
                state["summary"] = "Research completed with limited analysis due to missing API key"
                return state

            # Create comprehensive summary
            system_prompt = """Create a concise executive summary of the product research including:
            1. Key findings
            2. Top recommendation with reasoning
            3. Alternative options
            4. Important considerations for the buyer

            Keep it clear and actionable."""

            context = f"""
            Query: {state['query'].query}
            Products found: {len(state['products'])}
            Recommendation: {state.get('recommendation', 'None generated')}
            Alternatives: {len(state['alternatives'])}
            """

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context)
            ]

            response = await self.llm.ainvoke(messages)
            summary = response.content

            state["summary"] = summary
            state["current_step"] = "synthesize_results"

            return state

        except Exception as e:
            logger.error(f"Error in synthesize_results: {e}")
            state["error"] = f"Result synthesis failed: {str(e)}"
            return state

    def _format_products_for_analysis(self, products: List[Product]) -> str:
        """Format products for LLM analysis."""
        formatted = []
        for i, product in enumerate(products, 1):
            formatted.append(f"""
            {i}. {product.name}
               Price: ${product.price or 'N/A'}
               Brand: {product.brand or 'Unknown'}
               URL: {product.url or 'N/A'}
               Description: {product.description[:200] if product.description else 'N/A'}...
            """)
        return "\n".join(formatted)

    def _extract_review_content(self, search_results) -> str:
        """Extract review-like content from search results."""
        review_content = []
        for result in search_results[:5]:  # Check first 5 results
            # Handle both dict and SearchResult objects
            if hasattr(result, 'content'):
                content = result.content
            else:
                content = result.get("content", "")

            if any(keyword in content.lower() for keyword in ["review", "rating", "stars", "customer", "buyer"]):
                review_content.append(content[:300])  # Truncate long content

        return "\n---\n".join(review_content) if review_content else ""

    def _build_recommendation_context(self, state: ResearchState) -> str:
        """Build context for recommendation generation."""
        return f"""
        User Query: {state['query'].query}

        Products Found: {len(state['products'])}
        Top Products: {self._format_products_for_analysis(state['products'][:3])}

        Review Insights: {state['reviews'][0].text if state['reviews'] else 'No review analysis available'}

        Please provide a specific recommendation with clear reasoning.
        """

    async def research_product(self, query: str) -> ResearchResult:
        """Main entry point for product research."""
        try:
            start_time = datetime.now()

            # Create initial state
            initial_state = ResearchState(
                query=ResearchQuery(query=query),
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

            # Run the workflow
            config = RunnableConfig()
            final_state = await self.workflow.ainvoke(initial_state, config)

            # Calculate research time
            end_time = datetime.now()
            research_time = (end_time - start_time).total_seconds()

            # Create result
            result = ResearchResult(
                query=final_state["query"],
                products=final_state["products"],
                reviews=final_state["reviews"],
                summary=final_state["summary"],
                recommendation=final_state["recommendation"],
                alternatives=final_state["alternatives"],
                timestamp=start_time.isoformat(),
                total_research_time=research_time
            )

            if final_state.get("error"):
                logger.error(f"Research completed with errors: {final_state['error']}")
            else:
                logger.info(f"Research completed successfully in {research_time:.2f} seconds")

            return result

        except Exception as e:
            logger.error(f"Error in research_product: {e}")
            return ResearchResult(
                query=ResearchQuery(query=query),
                summary=f"Research failed: {str(e)}",
                timestamp=datetime.now().isoformat()
            )