# Single-Call Fix - December 24, 2025

## Problem

Categorization was happening in **two separate OpenRouter API calls**:
1. Agent processing (web_scrape, response generation)
2. Separate categorization call (parallel)

This caused:
- ❌ Wasted API calls (2 instead of 1)
- ❌ Categorization failures (JSON parsing errors with MiniMax)
- ❌ Tags not showing in response
- ❌ Extra latency from parallel calls

**Logs showed:**
```
2025-12-24 16:34:02,800 - HTTP Request: POST https://openrouter.ai/.../chat/completions "HTTP/1.1 200 OK"
2025-12-24 16:34:05,439 - HTTP Request: POST https://openrouter.ai/.../chat/completions "HTTP/1.1 200 OK"
2025-12-24 16:34:05,451 - ERROR - Error parsing categorization JSON: Extra data: line 3 column 1 (char 63)
```

## Solution

**Changed to single-call architecture** where the agent handles everything:

### 1. Updated Agent Instructions

**File: `agents/ai_engineering_agent.py`**

Added tags requirement to instructions:
```python
CRITICAL RESPONSE RULES:
- ALWAYS end your response with tags on a new line in this EXACT format: "Tags: tag1, tag2, tag3"

RESPONSE FORMAT (MANDATORY):
[Your concise answer here]

Tags: relevant, topic, keywords
```

**Example output:**
```
Python 3.14 t-strings - New template string literals for safer SQL query building.

Why it matters: Template and values separated → validate before interpolation.

Reality check: Parameterized queries already solved this. T-strings streamline workflow but aren't a replacement for critical systems.

Tags: python, security, sql
```

### 2. Updated Router

**File: `agent_router.py`**

- **Removed** parallel categorization call
- **Added** `_parse_tags_from_response()` method
- **Simplified** to single agent call

**Before:**
```python
# Start categorization in parallel
categorization_task = asyncio.create_task(categorize_func(text, topic_name))

# Get agent response
response_text = await run_agent()

# Wait for categorization
primary_category, tags = await categorization_task
```

**After:**
```python
# Single call - agent handles everything
response_text = await run_agent()

# Parse tags from agent response
parsed_response, tags = self._parse_tags_from_response(response_text)
```

### 3. Tag Parsing Logic

**Method: `_parse_tags_from_response()`**

Extracts tags from agent response:
```python
# Input: "Great answer\n\nTags: python, security, sql"
# Output: ("Great answer\n\n📁 Tags: python, security, sql", ["python", "security", "sql"])
```

## Results

### API Calls: 2 → 1
- ✅ Agent call (includes web_scrape if needed)
- ❌ ~~Separate categorization call~~

### Response Format:
```
[Agent's concise answer - under 100 words]

📁 Tags: relevant, keywords, here
```

### Database:
- `primary_category` = Topic name (e.g., "AI Engineering")
- `secondary_tags` = JSON array from agent (e.g., `["python", "security", "sql"]`)

## Status

**Completed:**
- ✅ AI Engineering Agent - includes tags in response
- ✅ Journal Agent - includes tags in response
- ✅ Router - parses tags from response
- ✅ Single API call architecture

**Pending:**
- ⏳ Remaining 6 agents (General, Health, Wealth, Ideas, Rants, Career) - need tags added to instructions

## Testing

Test the AI Engineering and Journal topics - they should:
1. Make only ONE OpenRouter API call per message
2. Show tags in response: `📁 Tags: ...`
3. Save tags to database correctly

Other topics will work but won't show tags until their agents are updated.

**To test:**
```bash
# Send message in AI Engineering topic
# Check logs - should see only ONE OpenRouter call
# Response should include "📁 Tags: ..."

# Verify database:
sqlite3 bot.db "SELECT text, secondary_tags FROM messages ORDER BY id DESC LIMIT 1"
```

---

**Impact:** 50% reduction in API calls, faster responses, tags actually work!
