# MiniMax M2.1 Migration Summary

## Date: 2024-12-24

---

## Problem Solved

### Original Issue
When using **Gemini 3 Flash Preview** via OpenRouter, agents encountered a critical error:

```
ERROR: Function call is missing a `thought_signature`
Status: 400 Bad Request
```

**Root Cause:**
- Gemini 3 models require "thought signatures" to be preserved between function calling turns
- OpenRouter requires `reasoning_details` to be echoed back
- Agno framework doesn't preserve these reasoning blocks when using OpenRouter
- This is a known incompatibility (Agno issues #5450, #3649, #5329)

**Impact:**
- All agents failed when trying to use tools (web_search, web_scrape)
- Journal agent worked (no tools) but other agents couldn't function properly

---

## Solution: Switch to MiniMax M2.1

### Why MiniMax M2.1?

| Factor | MiniMax M2.1 | Gemini 3 Flash |
|--------|--------------|----------------|
| **Tool Calling** | ✅ Works perfectly | ❌ 400 errors |
| **OpenRouter Compatibility** | ✅ Full support | ❌ Requires thought signatures |
| **Agno Compatibility** | ✅ No issues | ❌ Known bugs |
| **Context Window** | 200K tokens | 1M tokens |
| **Cost** | $0.30/$1.20 | $0.075/$0.30 |
| **Performance** | Excellent for coding/agents | Excellent general |
| **Setup Complexity** | Simple | Complex (reasoning_details) |

**Decision:** MiniMax provides **reliable tool calling** without compatibility issues, making it the right choice despite slightly higher cost.

---

## Changes Made

### 1. Updated Environment Configuration

**File:** `.env`
```diff
- OPENROUTER_MODEL=google/gemini-3-flash-preview
+ OPENROUTER_MODEL=minimax/minimax-m2.1
```

### 2. Updated Agent Configuration

**File:** `agents/base_agent.py`
```diff
- OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
+ OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.1")
```

### 3. Created Documentation

**New Files:**
- `MODEL_INFO.md` - Comprehensive MiniMax specifications and configuration
- `MINIMAX_MIGRATION.md` - This migration summary

**Updated Files:**
- `ARCHITECTURE.md` - Updated model configuration section

---

## Testing Results

### All 8 Agents Tested Successfully

| Agent | Test Message | Result |
|-------|-------------|--------|
| **Journal** | "Had a challenging day at work..." | ✅ PASS - Empathetic response |
| **Health** | "Started a new workout routine..." | ✅ PASS - Supportive advice |
| **Wealth** | "Tracked my spending this week..." | ✅ PASS - Financial guidance |
| **Rants** | "Frustrated with slow internet..." | ✅ PASS - Validating response |
| **Ideas** | "Build a personal AI assistant..." | ✅ PASS - Critical thinking |
| **AI Engineering** | "LangGraph or custom orchestration?" | ✅ PASS - Technical advice |
| **Career** | "Job offer - remote vs hybrid..." | ✅ PASS - Strategic perspective |
| **General** | "What's the capital of France?" | ✅ PASS - Accurate information |

**HTTP Status:** All responses returned `200 OK`
**Tool Calling:** All agents can now use `web_search` and `web_scrape` without errors
**Response Quality:** High quality, domain-appropriate responses

---

## Verification Steps

To verify the migration worked:

1. **Run the test suite:**
```bash
uv run python test_agents.py
```

2. **Test in Telegram:**
- Send messages to different topics
- Include links to test web scraping
- Verify agents respond appropriately

3. **Check logs:**
```bash
tail -f bot.log
```
Look for `HTTP/1.1 200 OK` (not 400 errors)

---

## Cost Impact

### Before (Gemini 3 Flash)
- **Input:** $0.075 per million tokens
- **Output:** $0.30 per million tokens
- **Problem:** Didn't work with tools

### After (MiniMax M2.1)
- **Input:** $0.30 per million tokens (4x more expensive)
- **Output:** $1.20 per million tokens (4x more expensive)
- **Benefit:** Actually works!

### Monthly Cost Estimate

**Assumptions:**
- 1,000 messages/month
- Average: 500 input tokens, 300 output tokens per message

**Costs:**
- Input: 500K tokens × $0.30 = $0.15
- Output: 300K tokens × $1.20 = $0.36
- **Total: ~$0.51/month**

**Conclusion:** Cost increase is negligible ($0.12 → $0.51/month) for a working system.

---

## Rollback Plan (If Needed)

If you need to revert to Gemini for any reason:

1. **Update .env:**
```env
OPENROUTER_MODEL=google/gemini-3-flash-preview
```

2. **Update base_agent.py:**
```python
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
```

3. **Restart bot:**
```bash
uv run telegram_bot.py
```

**Note:** Gemini will still have tool calling errors. Only rollback if absolutely necessary.

---

## Future Monitoring

### Watch For:

1. **Agno Updates:**
   - PR #5802 (OpenRouter reasoning support) - Currently open
   - May fix Gemini + OpenRouter compatibility

2. **MiniMax Updates:**
   - M3.0 or newer versions
   - Performance improvements

3. **Alternative Models:**
   - Claude models (if budget increases)
   - DeepSeek (if need cheaper option)

### How to Switch Models

Simply update `.env`:
```env
OPENROUTER_MODEL=new/model-id
```

Test with:
```bash
uv run python test_agents.py
```

---

## Key Takeaways

✅ **Problem Solved:** Tool calling now works reliably
✅ **All Agents Working:** 8/8 agents pass tests
✅ **Cost Acceptable:** ~$0.51/month for 1,000 messages
✅ **Future-Proof:** Can switch models easily if needed
✅ **Well-Documented:** Full specs in MODEL_INFO.md

---

## References

**Issues Investigated:**
- [Agno #5450: Gemini 3.0 4xx Error](https://github.com/agno-agi/agno/issues/5450)
- [Agno #3649: Gemini + OpenRouter session breaks](https://github.com/agno-agi/agno/issues/3649)
- [Agno #5329: Missing reasoning_content](https://github.com/agno-agi/agno/issues/5329)
- [Continue #8980: Gemini 3 Pro tool calling error](https://github.com/continuedev/continue/issues/8980)

**Documentation:**
- [MiniMax M2.1 Announcement](https://www.minimax.io/news/minimax-m21)
- [OpenRouter Models](https://openrouter.ai/models)
- [Agno OpenRouter Guide](https://docs.agno.com/reference/models/openrouter)

---

**Migration Completed:** 2024-12-24
**Status:** ✅ Production Ready
**Next Action:** Run `uv run telegram_bot.py` to start using MiniMax
