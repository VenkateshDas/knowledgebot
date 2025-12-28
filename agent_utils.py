"""
Utility functions for journal agent integration with the Telegram bot.

Provides context retrieval, message handling, and formatting functions
for the compassionate journal listener system.
"""

import sqlite3
import logging
import json
import asyncio
import os
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "bot.db")


def get_journal_context(chat_id: int, thread_id: int, limit: int = 10) -> List[Dict]:
    """
    Retrieve the last N messages from Journal topic for context.

    This provides conversation history to the agent so it can maintain
    continuity and reference previous journal entries.

    Args:
        chat_id: Telegram chat ID
        thread_id: Telegram thread/topic ID
        limit: Number of recent messages to retrieve (default: 10)

    Returns:
        List of message dictionaries with role, content, and metadata
        Ordered chronologically (oldest first)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT text, username, created_at, primary_category, secondary_tags
            FROM messages
            WHERE chat_id = ? AND thread_id = ?
            AND text IS NOT NULL
            AND text != ''
            ORDER BY created_at DESC
            LIMIT ?
        """, (chat_id, thread_id, limit))

        messages = cursor.fetchall()
        conn.close()

        # Format for agent context (reverse to chronological order)
        context = []
        for msg in reversed(messages):
            text, username, created_at, category, tags = msg

            context.append({
                "role": "user",
                "content": text,
                "metadata": {
                    "timestamp": created_at,
                    "username": username or "Unknown",
                    "category": category,
                    "tags": tags
                }
            })

        logger.info(f"Retrieved {len(context)} messages for context (chat_id={chat_id}, thread_id={thread_id})")
        return context

    except Exception as e:
        logger.error(f"Failed to retrieve journal context: {e}", exc_info=True)
        return []


async def handle_journal_message(
    message,
    chat_id: int,
    thread_id: int,
    user_id: int,
    text: str,
    message_id: int,
    categorize_func,
    update_categories_func
) -> str:
    """
    Handle a journal topic message with compassionate response.

    This function:
    1. Runs categorization in parallel with agent response
    2. Generates compassionate response using Agno agent
    3. Formats response with subcategories
    4. Updates database with categories

    Args:
        message: Telegram message object
        chat_id: Telegram chat ID
        thread_id: Telegram thread/topic ID
        user_id: Telegram user ID
        text: Message text content
        message_id: Database message ID
        categorize_func: Async function to categorize message
        update_categories_func: Function to update DB with categories

    Returns:
        Formatted response text with compassion + subcategories
    """
    from journal_agent import get_compassionate_response

    logger.info(f"Handling journal message (msg_id={message_id}, user={user_id})")

    try:
        # Step 1: Start categorization in parallel
        categorization_task = asyncio.create_task(
            categorize_func(text, topic_name="Journal")
        )

        # Step 2: Get compassionate response from agent (this is the main response)
        # The agent has its own memory system and doesn't need explicit context here
        compassionate_response = await asyncio.get_event_loop().run_in_executor(
            None,
            get_compassionate_response,
            user_id,
            chat_id,
            text
        )

        # Step 3: Wait for categorization to complete
        primary_category, tags_json = await categorization_task

        # Step 4: Format subcategories
        tags = json.loads(tags_json) if tags_json else []
        tags_text = ", ".join(tags) if tags else "None"

        # Step 5: Combine compassionate response with subcategories
        response_text = f"""{compassionate_response}

📁 Subcategories: {tags_text}"""

        # Step 6: Update database with categories
        update_categories_func(message_id, primary_category, tags_json)

        logger.info(f"Successfully handled journal message (msg_id={message_id})")
        return response_text

    except Exception as e:
        logger.error(f"Error handling journal message: {e}", exc_info=True)

        # Fallback response if anything fails
        return """Thank you for sharing. I'm here to listen.

📁 Subcategories: None"""


def format_journal_response(compassionate_text: str, tags: List[str]) -> str:
    """
    Format the final journal response with compassion + subcategories.

    Args:
        compassionate_text: The empathetic response from the agent
        tags: List of subcategory tags

    Returns:
        Formatted response string
    """
    tags_text = ", ".join(tags) if tags else "None"

    return f"""{compassionate_text}

📁 Subcategories: {tags_text}"""


def is_journal_topic(topic_name: str) -> bool:
    """
    Check if a topic name is the Journal topic.

    Args:
        topic_name: Name of the topic

    Returns:
        True if this is the Journal topic, False otherwise
    """
    # Case-insensitive comparison
    return topic_name and topic_name.strip().lower() == "journal"


# Statistics and monitoring functions

def get_journal_stats(chat_id: int, thread_id: int) -> Dict:
    """
    Get statistics about journal entries.

    Args:
        chat_id: Telegram chat ID
        thread_id: Journal thread ID

    Returns:
        Dictionary with stats (total_entries, date_range, etc.)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get total count
        cursor.execute("""
            SELECT COUNT(*), MIN(created_at), MAX(created_at)
            FROM messages
            WHERE chat_id = ? AND thread_id = ?
        """, (chat_id, thread_id))

        count, first_date, last_date = cursor.fetchone()

        # Get unique categories
        cursor.execute("""
            SELECT DISTINCT primary_category
            FROM messages
            WHERE chat_id = ? AND thread_id = ?
            AND primary_category IS NOT NULL
        """, (chat_id, thread_id))

        categories = [row[0] for row in cursor.fetchall()]

        conn.close()

        return {
            "total_entries": count or 0,
            "first_entry": first_date,
            "last_entry": last_date,
            "categories": categories
        }

    except Exception as e:
        logger.error(f"Failed to get journal stats: {e}")
        return {
            "total_entries": 0,
            "first_entry": None,
            "last_entry": None,
            "categories": []
        }


def clear_agent_memory(user_id: int, chat_id: int) -> bool:
    """
    Clear the agent's memory for a specific user/chat session.

    Useful for starting fresh or debugging.

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID

    Returns:
        True if successful, False otherwise
    """
    try:
        session_id = f"user_{user_id}_chat_{chat_id}"

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM journal_agent_sessions
            WHERE session_id = ?
        """, (session_id,))

        rows_deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Cleared agent memory for session {session_id} ({rows_deleted} rows)")
        return True

    except Exception as e:
        logger.error(f"Failed to clear agent memory: {e}")
        return False
