# telegram_bot.py
"""
Main Telegram bot application.

Architecture (v2):
- Immediate ACK for URLs (non-blocking)
- Semantic caching for repeated queries
- Query routing for model selection
- Hybrid retrieval (BM25 + Vector)
- Background URL indexing
"""

import logging
import re
import asyncio
from datetime import datetime, UTC

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

from core.config import config
from core.database import db_session, init_db, check_url_indexed, increment_url_share_count
from core.retriever import get_retriever
from core.cache import get_cache
from core.router import get_query_router, QueryComplexity

from agent_router import get_router
from indexing_worker import get_indexing_worker

# ==========================================================
# LOGGING SETUP
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==========================================================
# HELPERS
# ==========================================================

def build_message_link(chat, message_id):
    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    internal_id = abs(chat.id) - 1000000000000
    return f"https://t.me/c/{internal_id}/{message_id}"


def save_topic(chat_id, thread_id, topic_name):
    with db_session() as cur:
        cur.execute("""
        INSERT OR REPLACE INTO topics
        (chat_id, thread_id, topic_name, updated_at)
        VALUES (?, ?, ?, ?)
        """, (chat_id, thread_id, topic_name, datetime.now(UTC).isoformat()))


def get_topic_name(chat_id, thread_id):
    if thread_id is None:
        return "General"

    with db_session() as cur:
        cur.execute("""
        SELECT topic_name FROM topics
        WHERE chat_id = ? AND thread_id = ?
        """, (chat_id, thread_id))
        row = cur.fetchone()

    if row:
        return row[0]

    return f"Topic_{thread_id}"


def is_topic_initialized(chat_id, thread_id):
    if thread_id is None:
        return True
    with db_session() as cur:
        cur.execute("""
        SELECT 1 FROM topics
        WHERE chat_id = ? AND thread_id = ?
        """, (chat_id, thread_id))
        return cur.fetchone() is not None


def should_notify_unknown_topic(chat_id, thread_id):
    if thread_id is None:
        return False
    with db_session() as cur:
        cur.execute("""
        SELECT 1 FROM topics
        WHERE chat_id = ? AND thread_id = ?
        """, (chat_id, thread_id))
        return cur.fetchone() is None


def mark_topic_as_notified(chat_id, thread_id):
    placeholder = f"Topic_{thread_id}"
    with db_session() as cur:
        cur.execute("""
        INSERT OR IGNORE INTO topics
        (chat_id, thread_id, topic_name, updated_at)
        VALUES (?, ?, ?, ?)
        """, (chat_id, thread_id, placeholder, datetime.now(UTC).isoformat()))


def parse_message(msg):
    msg_type = "text"
    text = msg.text or msg.caption
    file_id = None
    file_uid = None

    if msg.photo:
        msg_type = "photo"
        media = msg.photo[-1]
        file_id = media.file_id
        file_uid = media.file_unique_id
    elif msg.video:
        msg_type = "video"
        file_id = msg.video.file_id
        file_uid = msg.video.file_unique_id
    elif msg.document:
        msg_type = "document"
        file_id = msg.document.file_id
        file_uid = msg.document.file_unique_id
    elif msg.voice:
        msg_type = "voice"
        file_id = msg.voice.file_id
        file_uid = msg.voice.file_unique_id

    return msg_type, text, file_id, file_uid


def extract_first_link(text):
    if not text:
        return None
    url_pattern = r'(https?://[^\s]+)'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None


def update_message_categories(message_id, primary_category, secondary_tags):
    try:
        with db_session() as cur:
            cur.execute(
                "UPDATE messages SET primary_category = ?, secondary_tags = ? WHERE id = ?",
                (primary_category, secondary_tags, message_id)
            )
    except Exception as e:
        logger.error(f"Failed to update categories: {e}")


# ==========================================================
# COMMAND HANDLERS
# ==========================================================

async def name_topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to set the name for the current topic."""
    try:
        msg = update.message
        chat_id = msg.chat.id
        thread_id = msg.message_thread_id

        if thread_id is None:
            await msg.reply_text("This command only works in forum topics.")
            return

        if not context.args:
            await msg.reply_text("Usage: /name_topic <topic_name>\nExample: /name_topic AI Engineering")
            return

        topic_name = " ".join(context.args)
        save_topic(chat_id, thread_id, topic_name)
        logger.info(f"Set topic name for thread {thread_id}: {topic_name}")
        await msg.reply_text(f"Topic set to: '{topic_name}'")

    except Exception as e:
        logger.exception("Error in name_topic command")
        await msg.reply_text(f"Error: {str(e)}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show knowledge base and cache statistics."""
    try:
        retriever = get_retriever()
        cache = get_cache()

        retriever_stats = retriever.get_stats()
        cache_stats = cache.get_stats()

        stats_text = (
            f"Knowledge Base Stats:\n"
            f"  Total chunks: {retriever_stats['total_chunks']}\n"
            f"  Vectors in memory: {retriever_stats['vectors_in_memory']}\n\n"
            f"Cache Stats:\n"
            f"  Total entries: {cache_stats['total_entries']}\n"
            f"  Total hits: {cache_stats['total_hits']}\n"
            f"  By topic: {cache_stats['by_topic']}"
        )
        await update.message.reply_text(stats_text)

    except Exception as e:
        logger.exception("Error in stats command")
        await update.message.reply_text(f"Error: {str(e)}")


# ==========================================================
# MESSAGE HANDLER
# ==========================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler with optimized pipeline."""
    try:
        msg = update.message
        if not msg:
            return

        chat = msg.chat
        user = msg.from_user
        thread_id = msg.message_thread_id

        # Log incoming message
        logger.info(f"Message from {user.username or user.id} in {chat.title or chat.id}")

        # Handle topic events
        if msg.forum_topic_created:
            topic_name = msg.forum_topic_created.name
            save_topic(chat.id, thread_id, topic_name)
            await msg.reply_text(f"Topic '{topic_name}' registered!")
            return

        if msg.forum_topic_edited:
            topic_name = msg.forum_topic_edited.name
            save_topic(chat.id, thread_id, topic_name)
            await msg.reply_text(f"Topic renamed to '{topic_name}'")
            return

        # Unknown topic notification
        if should_notify_unknown_topic(chat.id, thread_id):
            await msg.reply_text(
                "This topic hasn't been named yet.\n"
                "Use: /name_topic <name>\n"
                "Example: /name_topic AI Engineering"
            )
            mark_topic_as_notified(chat.id, thread_id)

        topic_name = get_topic_name(chat.id, thread_id)
        msg_type, text, file_id, file_uid = parse_message(msg)
        link = build_message_link(chat, msg.message_id)

        user_id = user.id if user else None
        username = user.username if user else None

        # Save message to database
        db_message_id = None
        with db_session() as cur:
            cur.execute("""
            INSERT INTO messages (
                chat_id, thread_id, topic_name,
                message_id, user_id, username,
                message_type, text,
                file_id, file_unique_id,
                message_link, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chat.id, thread_id, topic_name,
                msg.message_id, user_id, username,
                msg_type, text,
                file_id, file_uid,
                link, datetime.now(UTC).isoformat()
            ))
            db_message_id = cur.lastrowid

        # Non-text messages: simple acknowledgment
        if not text:
            await msg.reply_text("Saved!")
            return

        # Check for URL
        extracted_url = extract_first_link(text)

        # --- DUPLICATE URL DETECTION ---
        if extracted_url:
            indexed_info = check_url_indexed(extracted_url, topic_name)
            if indexed_info:
                updated_count = increment_url_share_count(extracted_url, topic_name)
                summary = indexed_info.get('summary') or 'No summary available'
                if len(summary) > 500:
                    summary = summary[:497] + "..."

                notification = (
                    f"Already Indexed!\n\n"
                    f"This link is in the {topic_name} knowledge base.\n\n"
                    f"Summary:\n{summary}\n"
                )
                if updated_count > 1:
                    notification += f"\nShared {updated_count} times in this topic"

                await msg.reply_text(notification)
                return

        # --- QUERY ROUTING ---
        query_router = get_query_router()
        route_result = query_router.route(text, has_url=bool(extracted_url))

        # Handle instant responses (greetings, acknowledgments)
        if route_result.complexity == QueryComplexity.INSTANT:
            await msg.reply_text(route_result.template_response)
            return

        # --- SEMANTIC CACHE CHECK ---
        cache = get_cache()
        cached_response = cache.get(text, topic_name)

        if cached_response:
            logger.info(f"Cache HIT for message {msg.message_id}")
            await msg.reply_text(cached_response)
            return

        # --- URL HANDLING: Immediate ACK + Background Processing ---
        if extracted_url:
            # Send immediate acknowledgment
            await msg.reply_text("Got it! Processing the link...")

            # Update database with URL
            with db_session() as cur:
                cur.execute(
                    "UPDATE messages SET extracted_link = ? WHERE id = ?",
                    (extracted_url, db_message_id)
                )

        # --- AGENT ROUTING ---
        logger.info(f"Routing to agent for topic '{topic_name}' (complexity: {route_result.complexity.value})")

        router = get_router()
        response_text, primary_cat, secondary_tags = await router.route_message(
            topic_name=topic_name,
            user_id=user_id,
            chat_id=chat.id,
            thread_id=thread_id,
            text=text,
            message_id=db_message_id,
            update_categories_func=update_message_categories
        )

        # Update with scraped summary if available
        if extracted_url:
            try:
                with db_session() as cur:
                    cur.execute(
                        "SELECT summary FROM url_scrape_cache WHERE url = ?",
                        (extracted_url,)
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        cur.execute(
                            "UPDATE messages SET summary = ? WHERE id = ?",
                            (row[0], db_message_id)
                        )
            except Exception as e:
                logger.error(f"Error updating summary: {e}")

        # Send response
        if response_text and response_text.strip():
            await msg.reply_text(response_text)

            # Cache successful responses (except for URL-specific responses)
            if not extracted_url:
                cache.set(text, response_text, topic_name)
        else:
            logger.warning(f"Empty response for message {msg.message_id}")
            await msg.reply_text("Got it! I'm processing this information.")

    except Exception:
        logger.exception("Failed to process message")


# ==========================================================
# ENTRYPOINT
# ==========================================================

def main():
    init_db()

    async def post_init(application):
        """Post-initialization: start background workers."""
        logger.info("Starting background workers...")

        # Initialize retriever (creates schema if needed)
        retriever = get_retriever()
        logger.info(f"Retriever initialized: {retriever.get_stats()}")

        # Initialize cache
        cache = get_cache()
        cache.cleanup_expired()
        logger.info(f"Cache initialized: {cache.get_stats()}")

        # Start indexing worker
        worker = get_indexing_worker()
        asyncio.create_task(worker.start())

        logger.info("Bot is running with hybrid retrieval")

    app = ApplicationBuilder().token(config.telegram_bot_token).post_init(post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("name_topic", name_topic_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # Message handler
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.StatusUpdate.ALL,
            handle_message
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()
