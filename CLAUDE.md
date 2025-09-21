Product Research Agent with GPT-5 and DeepAgents
🔴 NON-NEGOTIABLES: Development Principles

1. Environment & Git Repository Setup (FIRST STEP)
# Set up virtual environment first
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip

# Initialize repository
git init product-research-agent
cd product-research-agent
git add README.md .gitignore requirements.txt
git commit -m "Initial commit: Product Research Agent"

# Create feature branches for each phase
git checkout -b phase-1-mvp

2. Evaluation-Driven Development (EDD)
* BEFORE writing code: Define evaluation metrics for each component
* Use the Amazon ESCI dataset for evaluation: https://github.com/amazon-science/esci-data/tree/main
* Create benchmark datasets for product queries and expected outputs
* Set up automated evaluation pipeline using Arize Phoenix metrics
* Every feature must have measurable success criteria

3. Test-Driven Development (TDD)
* Write tests FIRST for every function, tool, and agent
* Minimum 80% test coverage requirement
* Use pytest for unit tests, integration tests for agent chains
* Mock external API calls during testing

4. Continuous Integration
* Commit early and often with meaningful messages
* Run tests on every commit
* Monitor traces in Arize Phoenix for performance regression

Project Overview
Build a Product Research Agent that automates the tedious parts of online shopping research using LangChain's DeepAgents framework ([repo](https://github.com/langchain-ai/open_deep_research)) and OpenAI's GPT-5 model ([docs](https://platform.openai.com/docs/guides/latest-model), [prompting guide](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide)).

Core Functionality
The agent solves the "15-20 mins across 8+ tabs" problem by:
* Comparing product specs and prices across multiple sources
* Analyzing and summarizing reviews (filtering for authenticity)
* Translating technical jargon into plain language
* Answering specific questions (e.g., "Is this quiet?", "Will it fit?")
* Providing side-by-side comparisons with alternatives

Technical Architecture

Main Components (Simplified - KISS Principle)
1. Orchestrator Agent (GPT-5)
    * Coordinates research workflow
    * Plans single-source strategy
    * Synthesizes final recommendations
    * Reference: [GPT-5 docs](https://platform.openai.com/docs/guides/latest-model)
2. Essential Sub-Agents:
    * Product Researcher: Combined spec extraction and price discovery via Google Shopping
    * Review Analyzer: Analyzes reviews from search results
3. Single Tool:
    * Google Shopping via Tavily API (prices, specs, and reviews in one source)

Key Dependencies (Simplified)
# Core
deepagents  # LangChain's agent orchestration (see [repo](https://github.com/langchain-ai/open_deep_research))
langchain-openai  # GPT-5 integration
arize-phoenix  # Observability and tracing (see [docs](https://arize.com/docs/ax/integrations/frameworks-and-platforms/langgraph/langgraph-tracing?utm_source=chatgpt.com))

# Tools (MVP)
tavily-python  # Google Shopping search
pytest  # Testing framework
pydantic  # Data validation

Implementation Plan

Phase 1: Simplified MVP (KISS Approach)
Tasks:
1. Set up virtual environment and install core dependencies
2. Create basic orchestrator using DeepAgents
3. Implement Google Shopping tool via Tavily API
4. Add product researcher agent (combined spec + price extraction)
5. Add basic review analyzer
6. Set up Arize Phoenix for tracing (using LangChain instrumentor, [docs](https://arize.com/docs/ax/integrations/frameworks-and-platforms/langgraph/langgraph-tracing?utm_source=chatgpt.com))

Success Criteria:
* ✅ Agent responds to queries in < 30 seconds using single source
* ✅ Successfully extracts product names and prices from Google Shopping
* ✅ Provides basic review sentiment analysis
* ✅ Traces visible in Arize Phoenix with span hierarchy
* ✅ 80% unit test coverage for 3 core functions
* ✅ Can handle electronics category (starting simple)

Phase 2: Expansion (After MVP Validation)
Tasks:
1. Add direct retailer scraping (Amazon first, then others)
2. Enhance review analysis with authenticity filtering
3. Add alternative product suggestions
4. Implement price comparison across multiple sources

Success Criteria:
* ✅ Review sentiment accuracy > 85% (validated against labeled dataset, [Amazon ESCI](https://github.com/amazon-science/esci-data/tree/main))
* ✅ Finds competitive prices across 2+ additional sources
* ✅ Suggests 3+ relevant alternatives for each query
* ✅ Response time remains < 45 seconds with expanded features

Phase 3: Demo Polish
Tasks:
1. Create interactive UI (Streamlit or Gradio)
2. Add example queries and use cases
3. Implement caching for faster demos
4. Add visualization of research process

Success Criteria:
* ✅ UI loads in < 3 seconds
* ✅ Cached responses return in < 2 seconds
* ✅ Visual trace of agent decision-making displayed in UI
* ✅ Successfully demos 5 different scenarios without errors
* ✅ User can see cost breakdown per query in Arize dashboard

Demo Scenario (MVP Focus)
Scenario 1: Laptop for Programming (Single Focus)
Query: "Best laptop under $2000 for programming and development work?" 

Agent Actions (Simplified):
* Search Google Shopping for laptops under $2000
* Extract top 3-5 options with prices and specs
* Analyze available review data for programming use
* Provide simple comparison table with recommendation

(Additional scenarios will be added in Phase 2 after MVP validation)

Arize AI Tracing Setup
Since DeepAgents is built on LangChain/LangGraph, use the LangChain instrumentor ([docs](https://arize.com/docs/ax/integrations/frameworks-and-platforms/langgraph/langgraph-tracing?utm_source=chatgpt.com)):
```python
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor

# Configure Phoenix tracer
tracer_provider = register(
    project_name="product-research-agent",
    api_key=os.getenv("ARIZE_API_KEY"),
    space_id=os.getenv("ARIZE_SPACE_ID")
)

# Instrument LangChain (covers DeepAgents and LangGraph)
LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

# Log custom spans for sub-agent activities
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("product_research") as span:
    span.set_attribute("product_query", query)
    span.set_attribute("num_products_analyzed", len(products))
    span.set_attribute("total_cost", cost)
