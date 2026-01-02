"""
Query Router - Route queries to appropriate models based on complexity.

Like ChatGPT's model selector:
- Instant: Template responses for greetings/acknowledgments
- Fast: Lightweight model for simple tasks (URL summaries, simple Q&A)
- Balanced: Default model for general queries
- Powerful: Complex reasoning, analysis, comparisons
"""

import re
import logging
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels."""
    INSTANT = "instant"      # No LLM needed
    FAST = "fast"            # Quick, simple response
    BALANCED = "balanced"    # Standard response
    POWERFUL = "powerful"    # Complex reasoning


@dataclass
class RouteResult:
    """Result of query routing."""
    complexity: QueryComplexity
    model: Optional[str]
    template_response: Optional[str] = None
    needs_retrieval: bool = True
    needs_web_search: bool = False


# Patterns for instant responses (no LLM needed)
GREETING_PATTERNS = [
    r"^(hi|hello|hey|hola|yo)[\s!.,]*$",
    r"^good\s*(morning|afternoon|evening|night)[\s!.,]*$",
    r"^(thanks|thank\s*you|thx|ty)[\s!.,]*$",
    r"^(ok|okay|k|got\s*it|understood|sure|alright)[\s!.,]*$",
    r"^(bye|goodbye|see\s*you|cya|later)[\s!.,]*$",
    r"^(yes|no|yeah|nope|yep|nah)[\s!.,]*$",
]

# Patterns indicating URL content (use fast model)
URL_PATTERN = r"https?://[^\s]+"

# Patterns indicating complex queries (use powerful model)
COMPLEX_PATTERNS = [
    r"\b(compare|contrast|difference|between)\b",
    r"\b(analyze|analysis|evaluate|assessment)\b",
    r"\b(explain\s+why|how\s+does|what\s+causes)\b",
    r"\b(pros?\s+and\s+cons?|advantages?\s+and\s+disadvantages?)\b",
    r"\b(step\s+by\s+step|in\s+detail|comprehensive|thorough)\b",
    r"\b(implications?|consequences?|impact)\b",
    r"\b(strategy|strategic|plan|planning)\b",
    r"\b(recommend|suggestion|advice|should\s+i)\b",
]

# Patterns indicating retrieval needed
RETRIEVAL_PATTERNS = [
    r"\b(remember|recall|previously|earlier|last\s+time)\b",
    r"\b(what\s+did\s+(i|we|you)\s+say)\b",
    r"\b(that\s+(article|link|url|post))\b",
    r"\b(based\s+on|according\s+to)\b",
]

# Patterns indicating web search needed
SEARCH_PATTERNS = [
    r"\b(latest|recent|current|today|now|2024|2025)\b",
    r"\b(news|update|happening)\b",
    r"\b(how\s+much|price|cost)\b.*\b(now|current|today)\b",
    r"\b(who\s+is|what\s+is)\b.*\b(now|current|today)\b",
]

# Template responses for instant queries
INSTANT_TEMPLATES = {
    "greeting": "Hey! How can I help you today?",
    "thanks": "You're welcome! Let me know if you need anything else.",
    "acknowledgment": "Got it!",
    "farewell": "See you later! Take care.",
    "affirmative": "Understood!",
}


class QueryRouter:
    """
    Routes queries to appropriate models based on complexity analysis.

    Fast pattern matching - no LLM calls for routing.
    """

    def __init__(self):
        """Initialize the router."""
        from core.config import config

        # Model mapping
        self.models = {
            QueryComplexity.INSTANT: None,  # No model needed
            QueryComplexity.FAST: getattr(config, 'fast_model', config.openrouter_model),
            QueryComplexity.BALANCED: config.openrouter_model,
            QueryComplexity.POWERFUL: getattr(config, 'powerful_model', config.openrouter_model),
        }

        # Compile patterns for efficiency
        self._greeting_patterns = [re.compile(p, re.IGNORECASE) for p in GREETING_PATTERNS]
        self._url_pattern = re.compile(URL_PATTERN, re.IGNORECASE)
        self._complex_patterns = [re.compile(p, re.IGNORECASE) for p in COMPLEX_PATTERNS]
        self._retrieval_patterns = [re.compile(p, re.IGNORECASE) for p in RETRIEVAL_PATTERNS]
        self._search_patterns = [re.compile(p, re.IGNORECASE) for p in SEARCH_PATTERNS]

        logger.info("QueryRouter initialized")

    def route(self, query: str, has_url: bool = False) -> RouteResult:
        """
        Route a query to the appropriate model.

        Args:
            query: User query text
            has_url: Whether the message contains a URL

        Returns:
            RouteResult with complexity, model, and flags
        """
        query_lower = query.strip().lower()
        query_stripped = query.strip()

        # Check for instant responses (greetings, acknowledgments)
        template = self._match_instant(query_stripped)
        if template:
            logger.debug(f"Routed to INSTANT: '{query[:30]}...'")
            return RouteResult(
                complexity=QueryComplexity.INSTANT,
                model=None,
                template_response=template,
                needs_retrieval=False,
                needs_web_search=False
            )

        # Check for URL - use fast model for summarization
        if has_url or self._url_pattern.search(query):
            logger.debug(f"Routed to FAST (URL): '{query[:30]}...'")
            return RouteResult(
                complexity=QueryComplexity.FAST,
                model=self.models[QueryComplexity.FAST],
                needs_retrieval=False,  # URL content is fetched, not retrieved
                needs_web_search=False
            )

        # Check for complex queries
        if self._is_complex(query):
            logger.debug(f"Routed to POWERFUL: '{query[:30]}...'")
            return RouteResult(
                complexity=QueryComplexity.POWERFUL,
                model=self.models[QueryComplexity.POWERFUL],
                needs_retrieval=self._needs_retrieval(query),
                needs_web_search=self._needs_search(query)
            )

        # Default: balanced model
        logger.debug(f"Routed to BALANCED: '{query[:30]}...'")
        return RouteResult(
            complexity=QueryComplexity.BALANCED,
            model=self.models[QueryComplexity.BALANCED],
            needs_retrieval=self._needs_retrieval(query),
            needs_web_search=self._needs_search(query)
        )

    def _match_instant(self, query: str) -> Optional[str]:
        """Check if query matches instant response patterns."""
        for pattern in self._greeting_patterns:
            if pattern.match(query):
                # Determine template type
                q_lower = query.lower()
                if any(w in q_lower for w in ["hi", "hello", "hey", "hola", "yo", "morning", "afternoon", "evening"]):
                    return INSTANT_TEMPLATES["greeting"]
                if any(w in q_lower for w in ["thank", "thx", "ty"]):
                    return INSTANT_TEMPLATES["thanks"]
                if any(w in q_lower for w in ["bye", "goodbye", "see you", "cya", "later"]):
                    return INSTANT_TEMPLATES["farewell"]
                if any(w in q_lower for w in ["yes", "yeah", "yep"]):
                    return INSTANT_TEMPLATES["affirmative"]
                return INSTANT_TEMPLATES["acknowledgment"]
        return None

    def _is_complex(self, query: str) -> bool:
        """Check if query requires complex reasoning."""
        for pattern in self._complex_patterns:
            if pattern.search(query):
                return True
        # Long queries are often complex
        if len(query.split()) > 30:
            return True
        return False

    def _needs_retrieval(self, query: str) -> bool:
        """Check if query needs knowledge base retrieval."""
        for pattern in self._retrieval_patterns:
            if pattern.search(query):
                return True
        return False

    def _needs_search(self, query: str) -> bool:
        """Check if query needs web search."""
        for pattern in self._search_patterns:
            if pattern.search(query):
                return True
        return False


# Singleton instance
_router_instance: Optional[QueryRouter] = None


def get_query_router() -> QueryRouter:
    """Get the global QueryRouter instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = QueryRouter()
    return _router_instance
