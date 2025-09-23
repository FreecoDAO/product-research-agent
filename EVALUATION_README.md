# Product Research Agent - Evaluation Setup

## 🚀 Quick Start

The Product Research Agent evaluation notebook is now ready to run! This comprehensive evaluation framework allows you to test and analyze the performance of the Product Research Agent using Arize Phoenix tracing.

## 📋 Prerequisites

### Required API Keys
Set these in your `.env` file:
```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Optional (for Phoenix Cloud tracing)
PHOENIX_API_KEY=your_phoenix_api_key_here
PHOENIX_SPACE_ID=your_phoenix_space_id_here
```

### Dependencies
All Jupyter dependencies are installed:
- ✅ jupyter==1.1.1
- ✅ notebook==7.4.5
- ✅ ipykernel==6.30.1
- ✅ ipywidgets==8.1.7
- ✅ matplotlib==3.10.6
- ✅ seaborn==0.13.2
- ✅ plotly==6.3.0
- ✅ python-dotenv==1.1.1

## 🎯 Running the Evaluation

### Option 1: Jupyter Notebook
```bash
python -m jupyter notebook Product_Research_Agent_Evaluations.ipynb
```

### Option 2: JupyterLab (Recommended)
```bash
python -m jupyterlab Product_Research_Agent_Evaluations.ipynb
```

### Option 3: For headless/remote environments
```bash
python -m jupyter notebook --no-browser --port=8888 --ip=0.0.0.0 --allow-root
```

### Option 4: VS Code
Open the `.ipynb` file directly in VS Code with the Jupyter extension.

## 📊 What the Evaluation Tests

### Test Dataset
5 diverse product research queries across categories:
- **Computers**: "Best laptop under $2000 for programming and development work"
- **Gaming**: "Wireless gaming headset with good microphone under $150"
- **Mobile**: "Smartphone with excellent camera for photography under $800"
- **Furniture**: "Ergonomic office chair for long work hours under $500"
- **Appliances**: "Best air fryer for family of 4 with easy cleanup"

### Evaluation Metrics
1. **Search Quality Score** (0-1): Product relevance, price accuracy, feature matching
2. **Response Time Score** (0-1): Performance vs complexity-based targets
3. **Workflow Completion** (0-1): End-to-end research pipeline success
4. **Overall Score**: Weighted average (50% quality + 30% speed + 20% completion)

### Key Features
- **Phoenix Tracing Integration**: Full observability with custom spans
- **Automated Evaluation**: Async execution with detailed metrics
- **Performance Analysis**: Category and complexity breakdowns
- **Error Handling**: Graceful failures with detailed tracking
- **Export Capabilities**: CSV and JSON results for further analysis
- **Insights Generation**: Automated recommendations based on performance

## 🔬 Phoenix Tracing

### Local Development (Console Tracing)
If no Phoenix API keys are provided, the notebook will use console tracing for development.

### Cloud Tracing (Recommended)
With Phoenix API keys set, you'll get:
- Web-based trace visualization
- Performance metrics dashboard
- Cost and token usage tracking
- Workflow step analysis
- Comparison across test cases

## 📈 Expected Results

### Performance Targets
- **Response Time**: < 15 seconds average
- **Search Quality**: > 0.7 score
- **Workflow Completion**: > 0.8 success rate
- **Overall Score**: > 0.75 average

### Success Indicators
- ✅ 10+ products found per query
- ✅ Accurate price extraction within target ranges
- ✅ Comprehensive recommendations generated
- ✅ Alternative products suggested
- ✅ Complete 7-step workflow execution

## 🛠️ Troubleshooting

### Common Issues

**Phoenix Import Error**:
```
⚠️ Phoenix not available: cannot import name 'LoopSetupType' from 'uvicorn.config'
```
- This is expected - the notebook will fall back to console tracing
- All evaluation functionality will still work perfectly

**API Key Issues**:
- Check `.env` file exists and has correct keys
- Ensure no extra spaces or quotes around keys
- Verify OpenAI and Tavily API keys are valid

**Import Errors**:
- Run `pip install -r requirements.txt` to ensure all dependencies
- Check that you're in the correct virtual environment

## 📝 Understanding Results

### Evaluation Output
The notebook generates:
- **Real-time Progress**: Live updates during evaluation
- **Summary Metrics**: Overall performance statistics
- **Detailed Results Table**: Per-query breakdown
- **Sample Research Results**: Best performing example
- **Phoenix Trace Links**: Direct links to detailed traces
- **Insights & Recommendations**: Automated performance analysis

### File Outputs
- `evaluation_results_YYYYMMDD_HHMMSS.csv`: Summary metrics
- `detailed_evaluation_YYYYMMDD_HHMMSS.json`: Full results with research data

## 🚀 Next Steps

After running the evaluation:
1. **Analyze Phoenix Traces**: Review detailed execution paths
2. **Identify Bottlenecks**: Look for slow steps or failures
3. **Optimize Performance**: Target specific improvement areas
4. **Expand Test Coverage**: Add more diverse queries
5. **Set Up Monitoring**: Run regular evaluations for regression detection

## 💡 Pro Tips

- **Run with Valid API Keys**: Best results with working OpenAI and Tavily keys
- **Monitor Resource Usage**: Evaluation makes multiple API calls
- **Save Results**: Export data for trend analysis over time
- **Phoenix Dashboard**: Use the web UI for deep trace analysis
- **Custom Metrics**: Modify evaluation functions for domain-specific needs

---

🎯 **The evaluation notebook provides a comprehensive framework for monitoring and improving the Product Research Agent's performance using industry-standard observability tools.**