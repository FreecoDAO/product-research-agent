# Product Research Agent

A simplified Product Research Agent that automates product research using GPT-5 and Google Shopping via the Tavily API.

## Features

- Single-source price and spec discovery via Google Shopping
- Review analysis and synthesis
- GPT-5 powered orchestration using DeepAgents
- Arize Phoenix observability

## Setup

1. Activate virtual environment:
```bash
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
- Copy `.env` file with your API keys
- Ensure OPENAI_API_KEY, TAVILY_API_KEY, and PHOENIX_API_KEY are set

## Usage

```bash
python main.py
```

## Architecture

Following KISS (Keep It Simple, Stupid) principles:
- Single data source (Google Shopping via Tavily)
- Three core components: Orchestrator, Product Researcher, Review Analyzer
- Focus on proving value before expanding complexity