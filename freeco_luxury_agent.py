#!/usr/bin/env python3
"""
Freeco AI — Luxury Tier Product Research Agent
Paperclip-Surfers process adapter wrapper.

This script is invoked by Paperclip as a `process` adapter.
It reads the task prompt from stdin (or PAPERCLIP_TASK env var),
runs the full LangGraph research pipeline, and writes structured
Markdown output to stdout for Paperclip to capture.

Usage (standalone):
    python freeco_luxury_agent.py "best organic vegan protein powder"

Usage (Paperclip process adapter):
    Set adapter_type = "process" and command = "python freeco_luxury_agent.py"
    Paperclip will inject the task as the first argument.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Ensure the agent src is on the path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env from the agent directory
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.WARNING)  # Suppress verbose logs in Paperclip mode

from src.core.config import settings
from src.core.models import ResearchQuery
from src.agents.orchestrator import ProductResearchOrchestrator


FREECO_LUXURY_SYSTEM_PROMPT = """
You are the Freeco AI Luxury Shopping Concierge — the world's most discerning
sustainable product advisor. Your role is to identify the absolute best-of-the-best
products for customers who demand excellence without compromise.

For every research task:
1. BEST PRICE tier — The most affordable option that meets minimum quality standards
2. BEST CHOICE tier — The optimal price-to-value ratio (the smart pick)
3. LUXURY tier — The finest available, regardless of cost, for the most demanding customer

All recommendations must prioritise:
- Certified organic, vegan, or sustainably sourced products
- Ethical supply chains and fair trade certification where applicable
- Minimal environmental impact (packaging, carbon footprint)
- Swiss-quality standards of reliability and craftsmanship

Format your final output as clean Markdown with clear tier headers.
"""


async def run_luxury_research(query: str) -> str:
    """Run the full LangGraph research pipeline and return formatted Markdown."""
    print(f"\n🔍 **Freeco AI Luxury Research Agent**\n")
    print(f"**Query:** {query}\n")
    print("---\n")

    orchestrator = ProductResearchOrchestrator()

    # Inject Freeco luxury context into the query
    enhanced_query = f"{query}\n\nContext: {FREECO_LUXURY_SYSTEM_PROMPT}"

    research_query = ResearchQuery(
        query=query,
        max_results=10,
        include_reviews=True
    )

    try:
        result = await orchestrator.research_product(query)

        output = []
        output.append("## 🌿 Freeco AI — Luxury Tier Research Results\n")
        output.append(f"**Query:** {query}\n")

        if result.recommendation:
            output.append("### ✅ Top Recommendation\n")
            output.append(result.recommendation)
            output.append("")

        if result.products:
            output.append(f"\n### 📦 Products Analysed ({len(result.products)} found)\n")
            for i, product in enumerate(result.products[:6], 1):
                tier = "🥇 LUXURY" if i == 1 else ("🥈 BEST CHOICE" if i == 2 else "🥉 BEST PRICE" if i == 3 else f"#{i}")
                output.append(f"**{tier}: {product.name}**")
                if product.price:
                    output.append(f"- 💰 Price: ${product.price:.2f}")
                if product.url:
                    output.append(f"- 🔗 [View Product]({product.url})")
                if product.specifications:
                    for k, v in list(product.specifications.items())[:4]:
                        output.append(f"- {k}: {v}")
                output.append("")

        if result.reviews:
            output.append(f"\n### 💬 Review Intelligence ({len(result.reviews)} reviews analysed)\n")
            for review in result.reviews[:2]:
                output.append(f"- **Sentiment:** {review.sentiment.title()}")
                if review.text:
                    output.append(f"  > {review.text[:200]}...")
                output.append("")

        if result.alternatives:
            output.append(f"\n### 🔄 Alternatives\n")
            for alt in result.alternatives[:3]:
                price_str = f" — ${alt.price:.2f}" if alt.price else ""
                output.append(f"- **{alt.name}**{price_str}")

        if result.summary:
            output.append(f"\n### 📊 Research Summary\n")
            output.append(result.summary)

        output.append(f"\n---\n*Powered by Freeco AI Luxury Concierge · DeepSeek V4 Flash via Novita AI*")
        return "\n".join(output)

    except Exception as e:
        return f"## ❌ Research Error\n\nThe Luxury Research Agent encountered an error:\n\n```\n{e}\n```\n\nPlease check your API keys and try again."


def main():
    if len(sys.argv) < 2:
        # Read from stdin (Paperclip process adapter mode)
        query = sys.stdin.read().strip()
    else:
        query = " ".join(sys.argv[1:])

    if not query:
        print("## ❌ No query provided\n\nPlease provide a product search query.")
        sys.exit(1)

    result = asyncio.run(run_luxury_research(query))
    print(result)


if __name__ == "__main__":
    main()
