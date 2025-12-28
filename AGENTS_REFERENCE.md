# Agents Quick Reference

## All Agents Overview

| Topic | Agent Name | Personality | Use Case |
|-------|------------|-------------|----------|
| **Journal** | Compassionate Journal Listener | Warm, empathetic, psychologist-like | Personal reflections, emotions, daily experiences |
| **Health** | Wellness Companion | Supportive, motivating, evidence-based | Health tracking, fitness goals, wellness habits |
| **Wealth** | Financial Companion | Practical, non-judgmental, mindful | Expense tracking, budgeting, financial planning |
| **Rants** | Rant Listener | Validating, direct, real | Venting frustrations, processing anger |
| **Ideas** | Ideas Partner | Constructive, probing, creative | Brainstorming, idea refinement, feasibility checks |
| **AI Engineering** | AI Engineering Assistant | Technical, code-aware, experienced | AI/ML questions, architecture, debugging |
| **Career** | Career Advisor | Strategic, grounded, honest | Career decisions, workplace challenges, growth |
| **General** | General Assistant | Versatile, helpful, resourceful | Misc questions, research, general assistance |

---

## Agent Capabilities

### Common to All Agents
- ✅ Web search
- ✅ Web scraping (Firecrawl + Jina fallback)
- ✅ Conversation memory (last 10 exchanges)
- ✅ Context awareness (recent messages from topic)
- ✅ Session persistence (per user + topic)

### Response Characteristics
- **Length:** 2-5 sentences (concise and actionable)
- **Format:** Plain text (no Markdown)
- **Tone:** Tailored to domain (empathetic, technical, direct, etc.)
- **Style:** Conversational, human-like, authentic

---

## Agent Behaviors by Topic

### Journal Agent
**What it does:**
- Validates emotions without judgment
- Reflects back what it hears
- Asks gentle questions for deeper reflection
- Recognizes patterns across entries
- Never diagnoses or gives medical advice

**Example exchanges:**
```
You: "Had a rough day at work. Manager criticized my code publicly."
Agent: "That sounds really challenging, especially being called out publicly. How are you processing that now?"

You: "Feeling anxious about the presentation tomorrow."
Agent: "That anticipation can be tough. What's been helpful for you in the past when you've felt this way?"
```

---

### Health Agent
**What it does:**
- Tracks health metrics and habits
- Provides evidence-based wellness info
- Celebrates progress and effort
- Asks about goals and challenges
- Recommends professional help when appropriate

**Example exchanges:**
```
You: "Started running 5k every morning this week!"
Agent: "That's solid consistency! How are you feeling with the new routine - energy levels, sleep quality?"

You: "Trying to drink more water but keep forgetting."
Agent: "Hydration is foundational. What's been helping you remember - bottle on desk, phone reminders, something else?"
```

---

### Wealth Agent
**What it does:**
- Tracks income, expenses, goals
- Offers financial literacy tips
- Provides perspective on spending
- Encourages mindful money management
- Never gives specific investment advice

**Example exchanges:**
```
You: "Spent $500 on eating out this month."
Agent: "Interesting pattern. Have you set a target for dining expenses, or just tracking for awareness right now?"

You: "Saved $2k this month towards emergency fund."
Agent: "Strong saving rate! What's your target for the emergency fund - 3 months, 6 months?"
```

---

### Rants Agent
**What it does:**
- Validates frustration without minimizing
- Matches energy (direct, real talk)
- Helps identify root issues
- Avoids toxic positivity
- Moves toward "what's next" when ready

**Example exchanges:**
```
You: "This stupid software keeps crashing during demos!"
Agent: "That's genuinely maddening - tech failing at the worst moment is brutal. Have you figured out a pattern or is it random?"

You: "Management keeps changing priorities every week."
Agent: "Yeah, that whiplash is exhausting. Are you pushing back on it or just rolling with the chaos?"
```

---

### Ideas Agent
**What it does:**
- Engages ideas enthusiastically
- Asks probing questions
- Identifies challenges early
- Offers alternatives
- Balances creativity with reality checks

**Example exchanges:**
```
You: "What if we built a marketplace for local artisans?"
Agent: "I like it - direct artist-to-buyer cuts out middlemen. What's the biggest obstacle to getting your first 50 artisans onboard?"

You: "App idea: AI that organizes your photos automatically."
Agent: "Google Photos does this already - what would you do differently? Better UI, privacy-focused, something else?"
```

---

### AI Engineering Agent
**What it does:**
- Provides technical guidance
- Discusses architecture patterns
- Helps debug issues
- Stays current with AI/ML trends
- Suggests specific tools and approaches

**Example exchanges:**
```
You: "Should I use LangGraph or LangChain for multi-step workflows?"
Agent: "For complex branching logic, LangGraph's state management is cleaner. LangChain works if it's linear. What's your flow - branching or sequential?"

You: "Getting high latency on embeddings in production."
Agent: "Likely the embedding calls. Try batching requests or switch to text-embedding-3-small - significantly faster for real-time use."
```

---

### Career Agent
**What it does:**
- Guides career decisions
- Offers workplace perspective
- Helps think strategically
- Identifies skill gaps
- Encourages long-term thinking

**Example exchanges:**
```
You: "Got offer: +25% salary but startup vs stable company now."
Agent: "Solid bump. What matters more right now - learning/equity upside or stability/work-life balance? Both are valid."

You: "Feeling stuck at 2 years in current role."
Agent: "Common inflection point. What skills or experiences would make your next move more compelling - management, new tech, domain expertise?"
```

---

### General Agent
**What it does:**
- Handles diverse topics
- Uses tools for current info
- Provides clear, accurate answers
- Admits when uncertain
- Adapts tone to topic

**Example exchanges:**
```
You: "What's the capital of France?"
Agent: "Paris. It's been France's capital since 508 AD and is home to about 2.2 million people in the city proper."

You: "How does photosynthesis work?"
Agent: "Plants convert light energy into chemical energy. Chlorophyll absorbs sunlight, which powers conversion of CO2 and water into glucose and oxygen."
```

---

## How to Use This Reference

1. **Choose the right topic** for your message
2. **Expect domain-specific responses** tailored to that topic
3. **Build context** - agents remember your last 10 exchanges per topic
4. **Use tools** - agents can search and scrape web content when helpful
5. **Switch topics** - each topic maintains separate conversation history

## Pro Tips

### Get Better Responses
- **Be specific**: More context = better responses
- **Ask follow-ups**: Agents remember conversation history
- **Use the right topic**: Journal for emotions, Ideas for brainstorming, etc.
- **Include links**: Agents can scrape and summarize URLs

### Context Management
- Each topic has **independent memory**
- Agents see **last 10 message pairs** from that topic
- **Cross-topic privacy**: Health conversations don't leak into Career

### Tool Usage
- Agents automatically use web search when needed
- Links are automatically detected and summarized
- No special commands needed - just send your message

---

## Telegram Topics Setup

Create these topics in your Telegram forum:

1. Journal
2. Health
3. Wealth
4. Rants
5. Ideas
6. AI Engineering
7. Career
8. General

**Case-sensitive!** "Journal" works, "journal" routes to General agent.

Use `/name_topic TopicName` to set or rename topics.

---

**Last Updated:** 2025-12-23
**Total Agents:** 8
**Common Tools:** Web Search, Web Scraping
**Memory:** 10 messages per topic per user
