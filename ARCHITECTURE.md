# Personal Assistant Architecture

## Overview

This project implements a **Router-Worker pattern** for a multi-agent personal assistant system using the Agno framework. Each Telegram topic routes to a specialized agent with domain-specific expertise.

## Architecture Pattern

```
Message from Telegram
        ↓
[Agent Router] ← Topic-based routing
        ↓
   Routing Decision (topic_name → agent)
        ↓
  ┌─────┴─────┬─────────┬─────────┬─────────┐
  ↓           ↓         ↓         ↓         ↓
[Journal]  [Health]  [Wealth]  [Ideas]  [Career] ...
  Agent      Agent     Agent     Agent     Agent
  ↓           ↓         ↓         ↓         ↓
Response + Tool Usage (web search, scraping)
        ↓
[Router formats response]
        ↓
 Send to Telegram
```

## Components

### 1. Agent Router (`agent_router.py`)

**Responsibilities:**
- Maps topic names to specialized agents
- Creates agent instances with proper session IDs
- Handles parallel categorization and agent response
- Formats final response with categories
- Falls back to General agent for unknown topics

**Key Features:**
- Simple dictionary-based routing (fast, predictable)
- Async message processing
- Integrated categorization pipeline

### 2. Base Agent (`agents/base_agent.py`)

**Provides:**
- Session management (per user + topic)
- Context retrieval (last 10 messages from topic)
- Common tool registration (web search, web scraping)
- Agno agent creation and configuration
- Memory management

**All agents inherit from BaseAgent.**

### 3. Specialized Agents

Each agent has:
- **Domain-specific instructions**: Tailored system prompts
- **Unique personality**: Appropriate tone for the domain
- **Common tools**: Web search and web scraping
- **Session memory**: Agno manages conversation history
- **Context awareness**: Retrieves recent messages from topic

| Agent | Topic | Role |
|-------|-------|------|
| **JournalAgent** | Journal | Compassionate listener for personal reflections |
| **HealthAgent** | Health | Wellness companion for health tracking |
| **WealthAgent** | Wealth | Financial tracking and mindful spending |
| **RantsAgent** | Rants | Safe space for venting and processing frustration |
| **IdeasAgent** | Ideas | Creative thinking partner for brainstorming |
| **AIEngineeringAgent** | AI Engineering | Technical assistant for AI/ML development |
| **CareerAgent** | Career | Professional development and career guidance |
| **GeneralAgent** | General | Versatile assistant for miscellaneous topics |

### 4. Common Tools (`tools/common_tools.py`)

**Available to all agents:**
- `web_search(query)`: LLM-powered web search
- `web_scrape(url)`: Scrape and summarize web content
  - Uses Firecrawl as primary method
  - Falls back to Jina Reader
  - Always uses Jina for LinkedIn

### 5. Telegram Bot (`telegram_bot.py`)

**Responsibilities:**
- Receive messages from Telegram
- Save messages to database
- Get topic name from thread ID
- Route text messages to appropriate agent
- Handle link summarization
- Send formatted responses

**Flow:**
1. Message arrives → Save to DB
2. If text message → Route to agent via router
3. Agent processes with context and tools
4. If link found → Scrape and summarize
5. Format response with agent reply + categories + summary
6. Send to Telegram

## Database Schema

### Messages Table
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    thread_id INTEGER,
    topic_name TEXT,
    message_id INTEGER,
    user_id INTEGER,
    username TEXT,
    message_type TEXT,
    text TEXT,
    file_id TEXT,
    file_unique_id TEXT,
    message_link TEXT,
    created_at TEXT,
    primary_category TEXT,
    secondary_tags TEXT,  -- JSON array
    extracted_link TEXT,
    summary TEXT
)
```

### Agent Sessions Tables
Each agent creates its own session table:
- `journal_agent_sessions`
- `health_agent_sessions`
- `wealth_agent_sessions`
- etc.

Managed by Agno framework for conversation memory.

## Session Management

**Session ID Format:**
```
{topic_name}_user_{user_id}_chat_{chat_id}
```

Example: `journal_user_123456_chat_789012`

**Benefits:**
- Separate conversation history per topic
- User-specific context
- Chat-specific isolation
- Easy memory cleanup

## Adding New Agents

To add a new agent:

1. Create agent file in `agents/`:
```python
from agents.base_agent import BaseAgent

INSTRUCTIONS = """Your agent instructions here..."""

class MyNewAgent(BaseAgent):
    def __init__(self, user_id: int, chat_id: int):
        super().__init__(
            name="Agent Name",
            instructions=INSTRUCTIONS,
            description="Brief description",
            user_id=user_id,
            chat_id=chat_id,
            topic_name="TopicName"
        )
```

2. Register in `agent_router.py`:
```python
from agents.my_new_agent import MyNewAgent

AGENT_REGISTRY = {
    # ... existing agents ...
    "TopicName": MyNewAgent,
}
```

3. Create corresponding topic in Telegram forum

That's it! The router handles the rest.

## Configuration

**Environment Variables (.env):**
```
OPENROUTER_API_KEY=your_openrouter_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key
OPENROUTER_MODEL=minimax/minimax-m2.1
```

**Model:**
All agents use the same model specified in `OPENROUTER_MODEL`.
Currently configured: **MiniMax M2.1** - A cost-effective model with excellent tool calling support and 200K context window. See MODEL_INFO.md for detailed specifications.

## Testing

Run the test script to verify all agents:
```bash
python test_agents.py
```

This will:
- List all available agents
- Test each agent with sample messages
- Verify fallback to General agent for unknown topics

## Performance Characteristics

**Router Pattern Benefits:**
- ✅ Fast routing (dictionary lookup, no LLM inference)
- ✅ Predictable behavior (explicit topic → agent mapping)
- ✅ Low latency (no routing overhead)
- ✅ Easy debugging (clear agent boundaries)
- ✅ Scalable (add agents without touching existing ones)

**Agno Framework Benefits:**
- ✅ 529× faster instantiation than LangGraph
- ✅ 24× lower memory usage than LangGraph
- ✅ Built-in session management
- ✅ Automatic conversation history
- ✅ Native tool support

## Future Extensions

**Potential additions:**
1. **MCP Integration**: Connect to external services (Calendar, Email, Notion)
2. **Specific Agent Tools**: Health metrics DB, expense tracking, etc.
3. **Proactive Agents**: Periodic summaries, reminders, insights
4. **Multi-agent Collaboration**: Agents consulting each other for complex tasks
5. **Workflow Orchestration**: Multi-step tasks across agents

**Migration Path:**
Current router-worker pattern is foundation for hierarchical or swarm patterns if needed later. Agno supports all patterns natively.

## File Structure

```
telegram_exp/
├── telegram_bot.py              # Main bot
├── agent_router.py              # Router logic
├── test_agents.py               # Test script
├── bot.db                       # SQLite database
├── .env                         # Configuration
├── agents/
│   ├── __init__.py
│   ├── base_agent.py            # Base class
│   ├── journal_agent.py         # Journal agent
│   ├── health_agent.py          # Health agent
│   ├── wealth_agent.py          # Wealth agent
│   ├── rants_agent.py           # Rants agent
│   ├── ideas_agent.py           # Ideas agent
│   ├── ai_engineering_agent.py  # AI Engineering agent
│   ├── career_agent.py          # Career agent
│   └── general_agent.py         # General agent
└── tools/
    ├── __init__.py
    └── common_tools.py          # Web search & scraping
```

## Key Design Decisions

1. **Topic-based routing**: Uses Telegram topics for explicit, user-controlled categorization
2. **Shared tools**: All agents have web search and scraping capabilities
3. **Conversation memory**: Agno manages per-agent, per-user session history
4. **Plain text responses**: No Markdown for Telegram compatibility
5. **Parallel processing**: Categorization runs alongside agent response
6. **Graceful fallbacks**: Unknown topics route to General agent
7. **Clean separation**: Each agent is independent and testable

---

**Last Updated:** 2025-12-23
**Framework:** Agno v0.9.0+
**Model:** Gemini 3.0 Flash Preview (OpenRouter)
**Pattern:** Router-Worker (Hub-and-Spoke)
