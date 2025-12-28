# Migration Guide: Old Implementation → Router-Worker Architecture

## What Changed

### Before (Single Journal Agent)
- Only Journal topic used Agno agent
- Other topics got simple categorization + summarization
- Journal-specific logic embedded in `telegram_bot.py`
- `agent_utils.py` had journal-specific helpers

### After (Multi-Agent Router System)
- **All topics** route to specialized Agno agents
- Each topic has tailored instructions and personality
- Clean router architecture with specialized agents
- Unified agent base class for consistency

## File Changes

### New Files Created
```
agents/
  __init__.py
  base_agent.py              ← Base class for all agents
  journal_agent.py           ← Refactored journal agent
  health_agent.py            ← NEW
  wealth_agent.py            ← NEW
  rants_agent.py             ← NEW
  ideas_agent.py             ← NEW
  ai_engineering_agent.py    ← NEW
  career_agent.py            ← NEW
  general_agent.py           ← NEW

tools/
  __init__.py
  common_tools.py            ← Web search & scraping tools

agent_router.py              ← Central routing logic
test_agents.py               ← Test script
ARCHITECTURE.md              ← This architecture doc
MIGRATION_GUIDE.md           ← This migration guide
```

### Modified Files
- `telegram_bot.py`: Replaced journal-specific logic with router

### Files No Longer Needed
- `agent_utils.py`: Functions moved to router/base agent
- `journal_agent.py` (old): Replaced with new version in `agents/`

**Note:** Old files are still present but not imported. You can archive or delete them.

## Database Changes

### No Breaking Changes!
Existing database schema remains the same:
- `messages` table unchanged
- `topics` table unchanged
- Old `journal_agent_sessions` table still works

### New Session Tables
Each agent creates its own session table (managed by Agno):
- `journal_agent_sessions` (already exists)
- `health_agent_sessions`
- `wealth_agent_sessions`
- `rants_agent_sessions`
- `ideas_agent_sessions`
- `ai_engineering_agent_sessions`
- `career_agent_sessions`
- `general_agent_sessions`

**These are created automatically on first use.**

## Behavior Changes

### Journal Topic
**Before:**
- Compassionate response + subcategories
- Custom formatting in `agent_utils.py`

**After:**
- Same compassionate response (refactored to `JournalAgent`)
- Same categorization
- Cleaner code structure

**User experience: Identical**

### Other Topics (Health, Wealth, Ideas, etc.)
**Before:**
- Simple categorization with LLM
- Link summarization
- Generic response: "✅ Saved!"

**After:**
- **Specialized agent response** tailored to topic
- Same categorization
- Same link summarization
- Contextual, helpful responses

**User experience: Significantly improved!**

### Unknown/General Topics
**Before:**
- Generic categorization
- Simple "✅ Saved!" response

**After:**
- Routes to General agent
- Helpful, versatile responses
- Can use web search and scraping tools

**User experience: Better**

## Running the New System

### 1. Ensure Dependencies
All existing dependencies work. No new packages needed.

```bash
# Check your .env file has required keys
cat .env

# Should have:
# OPENROUTER_API_KEY=sk-or-v1-...
# FIRECRAWL_API_KEY=fc-...
# OPENROUTER_MODEL=google/gemini-3-flash-preview
```

### 2. Test the Agents
```bash
python test_agents.py
```

This verifies all agents are working correctly.

### 3. Run the Bot
```bash
python telegram_bot.py
```

**That's it!** No configuration changes needed.

## Setting Up Topics in Telegram

Ensure your Telegram forum has these topics created:
1. **Journal**
2. **Health**
3. **Wealth**
4. **Rants**
5. **Ideas**
6. **AI Engineering**
7. **Career**
8. **General**

**How to create a topic:**
1. Go to your Telegram forum
2. Click "Create Topic"
3. Enter exact topic name (case-sensitive: "Journal" not "journal")
4. Send a test message
5. Bot will auto-register the topic

**Or use the command:**
```
/name_topic TopicName
```

## Verification Checklist

After migration, verify:

- [ ] Bot starts without errors
- [ ] Can send message to Journal topic → get compassionate response
- [ ] Can send message to Health topic → get health-focused response
- [ ] Can send message to Wealth topic → get finance-focused response
- [ ] Can send message to Ideas topic → get creative feedback
- [ ] Can send message to AI Engineering topic → get technical guidance
- [ ] Can send message to Career topic → get career advice
- [ ] Can send message to Rants topic → get validating response
- [ ] Can send message to General topic → get helpful answer
- [ ] Can send message to unknown topic → routes to General agent
- [ ] Link summarization still works
- [ ] Categorization still works
- [ ] Messages saved to database correctly

## Rollback Plan (If Needed)

If you need to rollback to the old system:

1. **Restore old imports in `telegram_bot.py`:**
```python
# Change:
from agent_router import get_router

# Back to:
from agent_utils import is_journal_topic, handle_journal_message
```

2. **Restore old message handling logic:**
   - Replace the "AGENT ROUTING" section with the old "JOURNAL TOPIC" section
   - Restore the old categorization logic

3. **Restart bot:**
```bash
python telegram_bot.py
```

**Database will work with both systems** (no schema changes).

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'agents'"
**Solution:** Ensure you're running from project root directory.

### Error: "No module named 'tools'"
**Solution:** Ensure `tools/__init__.py` exists.

### Agent not responding
**Solution:**
1. Check logs for errors
2. Verify `OPENROUTER_API_KEY` is set
3. Test with `test_agents.py` first

### Wrong agent selected
**Solution:**
1. Check topic name matches exactly (case-sensitive)
2. Use `/name_topic TopicName` to set correct name
3. Unknown topics route to General agent (expected behavior)

### Session memory not working
**Solution:**
1. Check `bot.db` has agent session tables
2. Verify session ID format: `{topic}_user_{user_id}_chat_{chat_id}`
3. Check Agno is installed: `pip show agno`

## Performance Notes

### Router Overhead
**Negligible.** Simple dictionary lookup (< 1ms).

### Agent Instantiation
Agents are created on-demand. First message to a new user+topic creates the agent.
Subsequent messages reuse existing agent with memory.

### Memory Usage
Each agent maintains separate session history (last 10 message pairs).
Memory is topic-scoped, so:
- Journal conversations don't affect Health conversations
- Each topic has clean, focused context

## Future Enhancements

Now that the router architecture is in place, you can easily:

1. **Add new agents** (see ARCHITECTURE.md)
2. **Add agent-specific tools** (override `get_tools()` in agent)
3. **Integrate MCP** (Agno has native support)
4. **Add proactive features** (agents can initiate conversations)
5. **Enable agent collaboration** (agents consulting each other)

## Support

If you encounter issues:
1. Check logs in `bot.log`
2. Run `test_agents.py` to isolate problem
3. Verify environment variables in `.env`
4. Check database integrity: `sqlite3 bot.db ".schema"`

---

**Migration Date:** 2025-12-23
**Old System:** Single Journal agent + categorization
**New System:** Router-Worker with 8 specialized agents
**Breaking Changes:** None (backward compatible)
