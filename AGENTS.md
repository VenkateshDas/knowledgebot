# AGENTS.md - Codebase Guidelines

## Build, Lint, Test Commands

**Install dependencies:**
```bash
uv sync
```

**Run bot:**
```bash
uv run telegram_bot.py
```

**Run all tests:**
```bash
python test_agents.py
```

**Run single test:**
```bash
python -m pytest test_agents.py::test_name -v
```

## Architecture & Structure

**Router-Worker Pattern**: Central `AgentRouter` routes Telegram messages by topic name to 8 specialized agents. Each agent inherits from `BaseAgent` and manages its own Agno session. Database: SQLite (`bot.db`) with messages table + per-agent session tables.

**Key Components:**
- `telegram_bot.py`: Main bot entry point, handles Telegram message flow
- `agent_router.py`: Routes messages to agents, parses tags from responses
- `agents/base_agent.py`: Base class with session management, context retrieval, Agno agent creation
- `agents/*.py`: Specialized agents (Journal, Health, Wealth, Rants, Ideas, AI Engineering, Career, General)
- `tools/common_tools.py`: web_search, web_scrape (Firecrawl + Jina fallback)
- `tools/rag_tools.py`: knowledge_retrieve, knowledge_index, context management
- `config/`: Configuration files

**Stack:** Python 3.12+, Agno v0.9.0+, SQLAlchemy, OpenRouter API (MiniMax M2.1 model)

## Code Style & Conventions

**Imports:** Standard lib → third-party → local (organized by relevance, grouped)

**Naming:** `snake_case` for functions/variables, `PascalCase` for classes. Agents use `AGENT_REGISTRY` dict (all caps). Topic names are `PascalCase` ("Journal", "Health").

**Functions:** All have docstrings (Args, Returns, purpose). Use type hints (`List[Dict]`, `Optional[int]`). Async/sync: Use async in router, sync in agents.

**Error Handling:** Log errors with context, return graceful fallback messages. Always clear RAG context in finally blocks.

**Formatting:** 4-space indents, max ~100 chars. Use `markdown=False` in agents for Telegram plain text.

**Database:** Async PostgreSQL in production, SQLite dev. Use SqliteDb from Agno for session management.

**Agent Response Format:** Plain text (no Markdown). Optionally include tags: `Tags: tag1, tag2` at end for router parsing.

**Tools:** web_search uses English queries, include dates for weather. web_scrape handles both URLs (Firecrawl) and LinkedIn (Jina). knowledge_index only for insights/decisions/experiences (not Q&A).

**Session IDs:** Format: `{topic_lower}_user_{user_id}_chat_{chat_id}` for unique memory per topic+user+chat.
