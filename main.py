"""Main application entry point for Product Research Agent MVP."""

import asyncio
import logging
import sys
import time
from typing import Optional
import argparse

from src.core.config import settings
from src.core.tracing import (
    TracingConfig,
    initialize_tracing_from_config,
    trace_product_research,
    log_research_metrics
)
from src.agents.orchestrator import ProductResearchOrchestrator
from src.core.models import ResearchResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProductResearchCLI:
    """Command-line interface for the Product Research Agent."""

    def __init__(self):
        """Initialize the CLI application."""
        self.orchestrator = None
        self._setup_tracing()

    def _setup_tracing(self):
        """Set up Phoenix tracing."""
        try:
            config = TracingConfig().from_settings(settings)
            if initialize_tracing_from_config(config):
                logger.info("✅ Tracing enabled with Phoenix")
            else:
                logger.info("ℹ️  Tracing disabled (Phoenix not configured)")
        except Exception as e:
            logger.warning(f"Tracing setup failed: {e}")

    def _check_api_keys(self) -> bool:
        """Check if required API keys are configured."""
        missing_keys = []

        if not settings.openai_api_key:
            missing_keys.append("OPENAI_API_KEY")

        if not settings.tavily_api_key:
            missing_keys.append("TAVILY_API_KEY")

        if missing_keys:
            logger.warning("⚠️  Missing API keys:")
            for key in missing_keys:
                logger.warning(f"   - {key}")
            logger.warning("The agent will have limited functionality without these keys.")
            logger.warning("Set them in your .env file or as environment variables.")
            return False

        return True

    async def research_product(self, query: str) -> ResearchResult:
        """
        Research a product using the orchestrator agent.

        Args:
            query: Product search query

        Returns:
            Research result
        """
        if not self.orchestrator:
            self.orchestrator = ProductResearchOrchestrator()

        start_time = time.time()

        with trace_product_research(query) as span:
            try:
                logger.info(f"🔍 Starting research for: {query}")

                result = await self.orchestrator.research_product(query)

                # Log metrics
                end_time = time.time()
                research_time = end_time - start_time

                log_research_metrics(
                    span,
                    query=query,
                    num_products=len(result.products),
                    num_reviews=len(result.reviews),
                    total_time=research_time,
                    success=bool(result.products)
                )

                logger.info(f"✅ Research completed in {research_time:.2f} seconds")
                logger.info(f"📊 Found {len(result.products)} products, {len(result.reviews)} reviews")

                return result

            except Exception as e:
                logger.error(f"❌ Research failed: {e}")
                log_research_metrics(
                    span,
                    query=query,
                    total_time=time.time() - start_time,
                    success=False,
                    error=str(e)
                )
                raise

    def format_result(self, result: ResearchResult) -> str:
        """Format research result for display."""
        try:
            output = []
            output.append("=" * 80)
            output.append(f"📋 PRODUCT RESEARCH RESULTS")
            output.append("=" * 80)
            output.append(f"Query: {result.query.query}")
            output.append(f"Research Time: {result.total_research_time:.2f}s" if result.total_research_time else "")
            output.append("")

            # Summary
            if result.summary:
                output.append("📝 EXECUTIVE SUMMARY")
                output.append("-" * 40)
                output.append(result.summary)
                output.append("")

            # Recommendation
            if result.recommendation:
                output.append("🏆 RECOMMENDATION")
                output.append("-" * 40)
                output.append(result.recommendation)
                output.append("")

            # Products found
            if result.products:
                output.append(f"🛍️  PRODUCTS FOUND ({len(result.products)})")
                output.append("-" * 40)

                for i, product in enumerate(result.products[:5], 1):  # Show top 5
                    output.append(f"{i}. {product.name}")
                    if product.price:
                        output.append(f"   💰 Price: ${product.price:.2f}")
                    if product.brand:
                        output.append(f"   🏷️  Brand: {product.brand}")
                    if product.rating:
                        output.append(f"   ⭐ Rating: {product.rating}/5 ({product.review_count} reviews)")
                    if product.url:
                        output.append(f"   🔗 URL: {product.url}")

                    # Show key specifications
                    if product.specifications:
                        output.append("   📋 Key Specs:")
                        for key, value in list(product.specifications.items())[:3]:
                            output.append(f"      - {key}: {value}")

                    output.append("")

            # Alternatives
            if result.alternatives:
                output.append(f"🔄 ALTERNATIVES ({len(result.alternatives)})")
                output.append("-" * 40)
                for i, alt in enumerate(result.alternatives[:3], 1):
                    output.append(f"{i}. {alt.name}")
                    if alt.price:
                        output.append(f"   💰 ${alt.price:.2f}")
                    output.append("")

            # Review insights
            if result.reviews:
                output.append(f"💬 REVIEW INSIGHTS ({len(result.reviews)} reviews analyzed)")
                output.append("-" * 40)
                for review in result.reviews[:2]:  # Show first 2 review summaries
                    output.append(f"• Sentiment: {review.sentiment.title()}")
                    if review.text:
                        output.append(f"  {review.text[:150]}...")
                    output.append("")

            output.append("=" * 80)
            return "\n".join(output)

        except Exception as e:
            logger.error(f"Error formatting result: {e}")
            return f"Error displaying results: {str(e)}"

    async def demo_scenario(self):
        """Run the MVP demo scenario."""
        demo_query = "Best laptop under $2000 for programming and development work"

        logger.info("🚀 Running MVP Demo Scenario")
        logger.info(f"📝 Demo Query: {demo_query}")
        logger.info("")

        try:
            result = await self.research_product(demo_query)
            print(self.format_result(result))

            # Performance check
            if result.total_research_time and result.total_research_time < 30:
                logger.info("✅ Performance target met: < 30 seconds")
            elif result.total_research_time:
                logger.warning(f"⚠️  Performance target missed: {result.total_research_time:.2f}s > 30s")

            return result

        except Exception as e:
            logger.error(f"❌ Demo scenario failed: {e}")
            raise

    async def interactive_mode(self):
        """Run in interactive mode."""
        logger.info("🎯 Interactive Product Research Mode")
        logger.info("Type 'quit' or 'exit' to stop")
        logger.info("")

        while True:
            try:
                query = input("Enter product search query: ").strip()

                if query.lower() in ['quit', 'exit', 'q']:
                    logger.info("👋 Goodbye!")
                    break

                if not query:
                    continue

                print("\n" + "⏳ Researching..." + "\n")
                result = await self.research_product(query)
                print(self.format_result(result))
                print("\n" + "-" * 80 + "\n")

            except KeyboardInterrupt:
                logger.info("\n👋 Goodbye!")
                break
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                print(f"Error: {e}\n")


async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="Product Research Agent MVP")
    parser.add_argument(
        "query",
        nargs="?",
        help="Product search query (if not provided, runs in interactive mode)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the MVP demo scenario"
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check configuration and exit"
    )

    args = parser.parse_args()

    # Initialize CLI
    cli = ProductResearchCLI()

    # Check configuration
    if args.check_config:
        logger.info("🔧 Configuration Check")
        logger.info(f"GPT-5 Model: {settings.model_name}")
        logger.info(f"Reasoning Effort: {settings.reasoning_effort}")
        logger.info(f"Max Tokens: {settings.max_tokens}")

        has_keys = cli._check_api_keys()
        if has_keys:
            logger.info("✅ All required API keys configured")
        else:
            logger.warning("⚠️  Some API keys missing")

        sys.exit(0)

    try:
        # Check API keys
        cli._check_api_keys()

        if args.demo:
            # Run demo scenario
            await cli.demo_scenario()
        elif args.query:
            # Single query mode
            result = await cli.research_product(args.query)
            print(cli.format_result(result))
        else:
            # Interactive mode
            await cli.interactive_mode()

    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        # Run the application
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)