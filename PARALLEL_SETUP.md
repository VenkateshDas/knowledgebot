# Parallel AI Web Search Setup

## Overview

The web search tool has been upgraded to use **Parallel AI's Search API** - a purpose-built web search system designed specifically for AI agents.

## Why Parallel AI?

- ✅ **Real-time web search** - Actual current information from the web
- ✅ **Purpose-built for AI agents** - Optimized for agentic workflows
- ✅ **Fast & efficient** - "Agentic" mode returns token-efficient results
- ✅ **High-quality excerpts** - LLM-ready content with source URLs
- ✅ **Publish dates** - Know when content was published
- ⚠️ **Previous issue**: The old implementation just queried an LLM's training data (NO real web search)

## Setup Instructions

### 1. Get Parallel AI API Key

1. Sign up at [https://parallel.ai](https://parallel.ai)
2. Navigate to your dashboard
3. Generate an API key
4. Copy the API key

### 2. Add to Environment Variables

Add the following to your `.env` file:

```bash
# Parallel AI Web Search API
PARALLEL_API_KEY=your_parallel_api_key_here
```

### 3. Test the Implementation

Run the test script to verify everything works:

```bash
python test_parallel_search.py
```

You should see real-time search results from the web!

## How It Works

### API Configuration

- **Endpoint**: `https://api.parallel.ai/v1beta/search`
- **Mode**: `agentic` (fast, token-efficient for agents)
- **Max Results**: 6 (configurable)
- **Excerpt Length**: 800 characters per result
- **Timeout**: 15 seconds for fast responses

### Search Modes

Parallel AI offers two modes:

1. **Agentic** (Currently used)
   - Fast, token-efficient results
   - Concise excerpts optimized for agentic loops
   - Perfect for our use case

2. **One-shot** (Alternative)
   - More comprehensive results
   - Longer excerpts to answer questions in one response
   - Better for single-shot Q&A

### Response Format

The tool returns formatted search results with:

```
Web search results for: [query]

[1] Article Title
URL: https://example.com/article
Published: 2024-12-20
Key excerpts:
  - First relevant excerpt from the article
  - Second relevant excerpt
  - Third relevant excerpt

[2] Another Article
...
```

## Implementation Details

### Function Signature

```python
def web_search(query: str, max_results: int = 6) -> str:
    """
    Perform a real web search using Parallel AI Search API.

    Args:
        query: Search query or objective (natural language)
        max_results: Maximum number of results to return (default: 6)

    Returns:
        Formatted search results with excerpts and sources
    """
```

### Key Features

- ✅ Real web search (not LLM knowledge retrieval)
- ✅ Natural language queries supported
- ✅ Automatic excerpt extraction
- ✅ Source URLs and publish dates
- ✅ Fast response times (15s timeout)
- ✅ Comprehensive error handling
- ✅ Detailed logging

### Error Handling

The implementation handles:
- Missing API key
- Network timeouts
- API errors (with status codes)
- Empty results
- Malformed responses
- General exceptions

## Agent Integration

All agents now have access to **real web search** capabilities:

### Agents Using Web Search

1. **AI Engineering Agent** - Verifies technical claims, finds current library versions
2. **Ideas Agent** - Validates market data, finds comparable examples
3. **Wealth Agent** - Checks interest rates, market data, economic indicators
4. **Health Agent** - Verifies health claims, finds current research
5. **Career Agent** - Checks salary ranges, hiring trends, company info
6. **General Agent** - Searches for anything across all topics

### When Agents Use Search

Agents proactively use web search when:
- Answering questions requiring current information
- Verifying factual claims or statistics
- Finding recent news or events
- Checking product/service information
- Detecting uncertainty in knowledge

## Performance Optimization

### Speed Optimizations

- **Agentic mode**: Faster than one-shot mode
- **15-second timeout**: Prevents hanging
- **6 results default**: Balance between coverage and speed
- **800 chars per result**: Token-efficient excerpts

### Cost Optimization

- Uses "agentic" mode for token efficiency
- Limits results to avoid unnecessary data
- Caches API key configuration
- Reuses HTTP session (via requests library)

## Troubleshooting

### API Key Not Found

```
Error: PARALLEL_API_KEY not configured in environment variables.
```

**Solution**: Add `PARALLEL_API_KEY=your_key` to `.env` file

### Timeout Errors

```
Error: Search request timed out. Please try again.
```

**Solution**:
- Check internet connection
- Parallel AI API might be slow - retry
- Consider increasing timeout in code if needed

### No Results Found

```
No search results found for query: [your query]
```

**Solution**:
- Try rephrasing the query
- Make query more specific
- Check if query is too niche

### API Errors

```
Error: Parallel AI API error: 401
```

**Solution**:
- 401: Invalid API key - check your key
- 429: Rate limit - wait before retrying
- 500: Parallel AI server issue - retry later

## Documentation Resources

- [Parallel AI Documentation](https://docs.parallel.ai/home)
- [Search API Reference](https://docs.parallel.ai/api-reference/search-beta/search)
- [Parallel AI Blog - Search API Introduction](https://parallel.ai/blog/parallel-search-api)

## Next Steps

Once you've added your API key:

1. ✅ Test the search: `python test_parallel_search.py`
2. ✅ Start your bot: The agents will now have real web search!
3. ✅ Try asking agents questions requiring current information
4. ✅ Monitor logs to see search queries in action

---

**Note**: Make sure to keep your `PARALLEL_API_KEY` secure and never commit it to version control!
