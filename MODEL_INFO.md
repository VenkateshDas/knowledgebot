# Model Configuration: MiniMax M2.1

## Current Model

The personal assistant now uses **MiniMax M2.1** via OpenRouter.

### Model ID
```
minimax/minimax-m2.1
```

### Why MiniMax M2.1?

**Previous Issue with Gemini:**
- Gemini 3 models via OpenRouter required "thought signatures" for tool calling
- This caused 400 errors when agents tried to use tools (web_search, web_scrape)
- Agno framework doesn't preserve reasoning_details needed by Gemini through OpenRouter

**MiniMax M2.1 Advantages:**
- ✅ **Full tool calling support** - Works perfectly with OpenRouter + Agno
- ✅ **No reasoning_details requirement** - Doesn't have Gemini's complexity
- ✅ **Excellent coding capabilities** - 49.4% on Multi-SWE-Bench
- ✅ **Cost-effective** - $0.30 input / $1.20 output per million tokens
- ✅ **Large context** - 200K tokens (204,800 tokens)
- ✅ **Fast** - Good response times
- ✅ **Modern** - Knowledge cutoff June 2025

---

## Model Specifications

| Feature | Value |
|---------|-------|
| **Model ID** | minimax/minimax-m2.1 |
| **Parameters** | 10B activated (230B total MoE) |
| **Context Length** | 204,800 tokens |
| **Max Output** | 131,072 tokens |
| **Tool Calling** | ✅ Yes |
| **Function Calling** | ✅ Yes |
| **Response Format** | ✅ Structured outputs |
| **Reasoning** | ✅ Built-in (configurable) |
| **Modality** | Text-only (input & output) |

---

## Performance Benchmarks

| Benchmark | Score |
|-----------|-------|
| **Multi-SWE-Bench** | 49.4% |
| **SWE-Bench Multilingual** | 72.5% |
| **MMLU** | 88.0 |
| **HLE (w/o tools)** | 22.0 |
| **Coding (Baseline)** | 95.0% |

---

## Pricing

| Type | Cost |
|------|------|
| **Input** | $0.30 per million tokens |
| **Output** | $1.20 per million tokens |
| **Cache Read** | $0.00000003 per token |
| **Cache Write** | $0.000000375 per token |

**Cost Comparison:**
- **~8% of proprietary models** like GPT-4 or Claude Opus
- **More expensive than** Gemini Flash ($0.075/$0.30) but avoids tool calling issues
- **Cheaper than** Claude Sonnet ($3/$15)

---

## Key Features

### 1. Multi-Language Programming
Excellent support for:
- Rust, Java, Golang, C++
- Kotlin, Objective-C
- TypeScript, JavaScript
- Python (industry-leading)

### 2. Agentic Workflows
Works excellently with agent frameworks:
- ✅ Agno (our framework)
- Claude Code
- Cline
- Droid (Factory AI)
- Roo Code, Kilo Code

### 3. Tool Integration
- Native function calling support
- Works with OpenRouter's OpenAI-compatible API
- No special requirements (unlike Gemini's thought signatures)

### 4. Real-World Performance
- Enhanced for real-world complex tasks
- Strong design comprehension and aesthetic expression
- Native Android and iOS development capabilities

---

## Configuration

### Environment Variables (.env)
```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=minimax/minimax-m2.1
FIRECRAWL_API_KEY=your_firecrawl_api_key
```

### Code (agents/base_agent.py)
```python
from agno.models.openrouter import OpenRouter

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.1")
model = OpenRouter(id=OPENROUTER_MODEL)
```

---

## Testing Results

All 8 agents tested successfully:

| Agent | Status | Notes |
|-------|--------|-------|
| **Journal** | ✅ PASS | Empathetic, warm responses |
| **Health** | ✅ PASS | Supportive, evidence-based |
| **Wealth** | ✅ PASS | Practical financial advice |
| **Rants** | ✅ PASS | Validating, direct |
| **Ideas** | ✅ PASS | Probing, constructive |
| **AI Engineering** | ✅ PASS | Technical, specific |
| **Career** | ✅ PASS | Strategic, balanced |
| **General** | ✅ PASS | Informative, accurate |

**All tests: HTTP 200 OK - No errors**

---

## Alternative Models

If you want to switch models in the future, these work with OpenRouter + Agno + Tools:

### Recommended Alternatives

| Model | Pros | Cons |
|-------|------|------|
| **anthropic/claude-3-5-sonnet** | Excellent quality, great with tools | Expensive ($3/$15) |
| **anthropic/claude-3-5-haiku** | Fast, good quality | Medium cost ($1/$5) |
| **deepseek/deepseek-chat** | Very cheap, good quality | Less context |
| **qwen/qwen-2.5-72b-instruct** | Good balance | Medium quality |

### Models to Avoid (with OpenRouter)

| Model | Issue |
|-------|-------|
| **google/gemini-3-flash-preview** | ❌ Thought signature errors with tools |
| **google/gemini-3-pro-preview** | ❌ Same reasoning_details issues |
| **google/gemini-2-flash** | ⚠️ May work but not recommended |

---

## Troubleshooting

### Error: "Function call is missing a thought_signature"
**Solution:** You're using a Gemini model. Switch to MiniMax:
```env
OPENROUTER_MODEL=minimax/minimax-m2.1
```

### Error: "Model not found"
**Solution:** Check your OpenRouter API key and model ID spelling.

### Slow responses
**Solution:** MiniMax M2.1 should be fast (~14 tokens/sec). Check your internet connection.

### High costs
**Solution:** MiniMax is already cost-effective. For cheaper options, try `deepseek/deepseek-chat`.

---

## Future Considerations

### When to Switch Models

**Upgrade to Claude Sonnet if:**
- Quality becomes more important than cost
- You need even better reasoning
- Budget isn't a constraint

**Consider Gemini if:**
- They fix the OpenRouter integration (check Agno issues)
- You're using native Gemini API (not OpenRouter)
- Cost is critical (Gemini is cheapest)

### Monitoring

Watch for:
- New Agno releases fixing Gemini + OpenRouter
- MiniMax model updates (M3.0?)
- OpenRouter adding new models

---

## References

**Documentation:**
- [MiniMax M2.1 Announcement](https://www.minimax.io/news/minimax-m21)
- [OpenRouter Model Page](https://openrouter.ai/models/minimax/minimax-m2.1)
- [Agno OpenRouter Docs](https://docs.agno.com/reference/models/openrouter)

**Research:**
- [MiniMax M2.1 Review](https://medium.com/@leucopsis/an-analytical-review-of-minimax-m2-1-30eb5754b2d0)
- [MiniMax vs Gemini Comparison](https://www.geeky-gadgets.com/ai-models-tested-minimax-m2-1-vs-gemini-3-flash/)

---

**Last Updated:** 2024-12-24
**Model Version:** MiniMax M2.1
**Framework:** Agno 2.3.20
**Provider:** OpenRouter
