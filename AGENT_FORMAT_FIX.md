# Agent Format Fix - December 24, 2025

## Problems Found

Testing revealed agents were NOT following the format requirements:

1. ❌ **No tags** - Agents weren't including "Tags: ..." at the end
2. ❌ **Too verbose** - Responses exceeded 100 words significantly
3. ❌ **Asking questions for URLs** - Instead of summarizing, agents asked what the user wanted to know
4. ❌ **Not using web_scrape** - Sometimes didn't fetch URL content properly

**Log evidence:**
```
2025-12-24 16:45:56,908 - agent_router - WARNING - No tags found in agent response
```

**Example bad response:**
```
I see you've shared the same article again. Let me engage with it from a different angle.

**A few provocative takes I'd love to explore:**

The uncomfortable truth about "AI-native law firms"...
[200+ words of questions]

❌ NO TAGS
```

## Root Cause

The original instructions were TOO PERMISSIVE:
- Said "ALWAYS end with tags" but agents ignored it
- Didn't explicitly forbid asking questions for URL-only messages
- Examples showed questions being asked
- No enforcement of word count

## Solution

Updated agent instructions to be **MUCH MORE STRICT**:

### 1. Mandatory Format Section

**Added to ALL agents:**
```
MANDATORY RESPONSE FORMAT:
1. Keep response under 100 words (3-5 sentences max)
2. For URLs: Summarize the content, don't ask questions
3. For questions: Answer directly with specific feedback
4. ALWAYS end with: "Tags: tag1, tag2, tag3" on a new line
```

### 2. Critical URL Handling

**Added explicit instructions:**
```
CRITICAL: When given just a URL/link (and NO other text):
- Use web_scrape tool to fetch content
- Summarize the key points briefly (2-3 sentences)
- Highlight what's interesting or promising
- Add relevant tags
- DON'T ask clarifying questions - just summarize
- Even if you've seen the URL before, provide a fresh summary
```

### 3. Concrete Examples

**Replaced vague examples with strict format:**
```
URL only → "Python 3.14 t-strings introduce template literals for safer SQL.
Separates template and values for validation before interpolation.
Nice DX improvement for scripts, but parameterized queries preferred for production.

Tags: python, security, sql"
```

## Files Updated

**Strict format enforced:**
- ✅ `agents/ai_engineering_agent.py` - Updated with mandatory format
- ✅ `agents/ideas_agent.py` - Updated with mandatory format

**Remaining agents** (General, Health, Wealth, Rants, Career, Journal):
- Have "Tags: ..." instruction added
- Should be updated with similar strict format if issues occur

## Expected Behavior Now

### URL-only message:
**Input:** `https://example.com/article`

**Expected output:**
```
[2-3 sentence concise summary of the article content]

Tags: relevant, keywords, here
```

### Question about URL:
**Input:** `https://example.com/article - What do you think about the security implications?`

**Expected output:**
```
[Direct answer to the security question, referencing article]

Tags: security, analysis, relevant
```

### Regular question:
**Input:** `How should I architect a RAG system?`

**Expected output:**
```
[Concise technical guidance, 3-5 sentences]

Tags: rag, architecture, llm
```

## Testing

Test with AI Engineering or Ideas topics:

```bash
# Send URL only - should get concise summary with tags
# Send URL + question - should answer question with tags
# Send regular message - should get response with tags
```

All responses should:
✅ Be under 100 words
✅ Include "📁 Tags: ..." at the end (added by router)
✅ Not ask questions when given only a URL
✅ Use web_scrape tool for URLs

## What Was Changed

**Before:**
- Permissive instructions
- Agents could ignore tag requirement
- Verbose responses (200+ words)
- Asked questions instead of summarizing

**After:**
- MANDATORY format requirements
- Explicit "don't ask questions for URLs"
- Strict word count (under 100)
- Concrete examples of correct format

---

**Status:** ✅ Fixed for AI Engineering and Ideas agents
**Impact:** Better summaries, consistent tags, concise responses
**Next:** Monitor other agents, update if they show same issues
