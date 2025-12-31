# telegram_bot.py
"""
Main Telegram bot application.

Handles message routing to specialized agents and topic management.
"""

import logging
import re
import asyncio
from datetime import datetime, UTC

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# Core modules (centralized config, database, LLM client)
from core.config import config
from core.database import db_session, init_db

# Import agent router
from agent_router import get_router

# Import indexing worker
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

def escape_markdown(text):
    """Escape special characters for Telegram MarkdownV2."""
    if not text:
        return text
    # Characters that need to be escaped in MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

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
        topic = row[0]
        logger.info(f"Lookup topic for thread {thread_id}: {topic}")
        return topic

    # Unknown topic - use fallback
    topic = f"Topic_{thread_id}"
    logger.warning(
        f"Unknown topic for thread {thread_id} in chat {chat_id}. "
        f"Using fallback name '{topic}'."
    )
    return topic

def is_topic_initialized(chat_id, thread_id):
    """Check if a topic is in the database."""
    if thread_id is None:
        return True

    with db_session() as cur:
        cur.execute("""
        SELECT 1 FROM topics
        WHERE chat_id = ? AND thread_id = ?
        """, (chat_id, thread_id))
        return cur.fetchone() is not None

def should_notify_unknown_topic(chat_id, thread_id):
    """Check if we should send a notification about an unknown topic."""
    if thread_id is None:
        return False

    # Check if the topic exists at all (either with real name or placeholder)
    with db_session() as cur:
        cur.execute("""
        SELECT 1 FROM topics
        WHERE chat_id = ? AND thread_id = ?
        """, (chat_id, thread_id))
        topic_exists = cur.fetchone() is not None

    # Only notify if topic doesn't exist at all
    return not topic_exists

def mark_topic_as_notified(chat_id, thread_id):
    """Mark that we've notified about this unknown topic."""
    placeholder_name = f"Topic_{thread_id}"
    with db_session() as cur:
        cur.execute("""
        INSERT OR IGNORE INTO topics
        (chat_id, thread_id, topic_name, updated_at)
        VALUES (?, ?, ?, ?)
        """, (chat_id, thread_id, placeholder_name, datetime.now(UTC).isoformat()))

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


def update_message_categories(message_id, primary_category, secondary_tags):
    """Update message with categorization results."""
    try:
        with db_session() as cur:
            cur.execute(
                "UPDATE messages SET primary_category = ?, secondary_tags = ? WHERE id = ?",
                (primary_category, secondary_tags, message_id)
            )
        logger.info(f"Updated categories for message {message_id}")
    except Exception as e:
        logger.error(f"Failed to update categories: {e}")


def extract_first_link(text):
    """Extract the first URL from text."""
    if not text:
        return None
    url_pattern = r'(https?://[^\s]+)'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None


# ==========================================================
# COMMAND HANDLERS
# ==========================================================

async def name_topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to manually set the name for the current topic."""
    try:
        msg = update.message
        chat_id = msg.chat.id
        thread_id = msg.message_thread_id

        if thread_id is None:
            await msg.reply_text("⚠️ This command only works in forum topics, not in the general chat.")
            return

        # Get the topic name from command arguments
        if not context.args:
            await msg.reply_text(
                "Usage: /name_topic <topic_name>\n\n"
                "Example: /name_topic AI Engineering"
            )
            return

        topic_name = " ".join(context.args)

        # Save to database
        save_topic(chat_id, thread_id, topic_name)
        logger.info(f"Manually set topic name for thread {thread_id}: {topic_name}")

        await msg.reply_text(f"✅ Topic set to: '{topic_name}'")

    except Exception as e:
        logger.exception("Error in name_topic command")
        await msg.reply_text(f"Error: {str(e)}")

async def check_topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to check and list unknown topics that need initialization."""
    try:
        chat_id = update.effective_chat.id

        with db_session() as cur:
            # Get all unique thread_ids from messages
            cur.execute("""
                SELECT DISTINCT thread_id
                FROM messages
                WHERE chat_id = ? AND thread_id IS NOT NULL
            """, (chat_id,))
            message_threads = {row[0] for row in cur.fetchall()}

            # Get known topics
            cur.execute("""
                SELECT thread_id, topic_name
                FROM topics
                WHERE chat_id = ?
            """, (chat_id,))
            known_topics = {row[0]: row[1] for row in cur.fetchall()}

        # Find unknown threads
        unknown_threads = message_threads - set(known_topics.keys())

        if not unknown_threads:
            await update.message.reply_text(
                "✅ All topics are properly initialized!\n\n"
                f"Known topics: {len(known_topics)}"
            )
        else:
            response = (
                f"⚠️ Found {len(unknown_threads)} unknown topic(s):\n\n"
                f"Thread IDs: {', '.join(map(str, sorted(unknown_threads)))}\n\n"
                "To fix this:\n"
                "1. Go to each topic in Telegram\n"
                "2. Edit the topic name (you can keep the same name)\n"
                "3. Save it - this will trigger an update for the bot\n\n"
                f"Known topics ({len(known_topics)}):\n"
            )
            for tid, name in sorted(known_topics.items()):
                response += f"  • Thread {tid}: {name}\n"

            await update.message.reply_text(response)

    except Exception as e:
        logger.exception("Error in check_topics command")
        await update.message.reply_text(f"Error: {str(e)}")

# ==========================================================
# MESSAGE HANDLER
# ==========================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = update.message
        if not msg:
            return

        chat = msg.chat
        user = msg.from_user
        user_info = f"User: {user.username} ({user.id})" if user else "User: Unknown"
        chat_info = f"Chat: {chat.title or chat.username} ({chat.id})"
        thread_info = f"Thread: {msg.message_thread_id}" if msg.message_thread_id else "No Thread"
        
        logger.info(f"Received update: {chat_info} | {thread_info} | {user_info}")

        # Topic created (auto-register new topics)
        if msg.forum_topic_created:
            topic_name = msg.forum_topic_created.name
            thread_id = msg.message_thread_id
            logger.info(f"Topic created: '{topic_name}' (thread {thread_id}) in chat {chat.id}")
            save_topic(chat.id, thread_id, topic_name)
            await msg.reply_text(
                f"✅ Topic '{topic_name}' registered!\n\n"
                f"Use /name_topic to change the name if needed."
            )
            return

        # Topic edited (note: bot needs admin permissions to receive these events)
        if msg.forum_topic_edited:
            topic_name = msg.forum_topic_edited.name
            thread_id = msg.message_thread_id
            logger.info(f"Topic edited: '{topic_name}' (thread {thread_id}) in chat {chat.id}")
            save_topic(chat.id, thread_id, topic_name)
            await msg.reply_text(f"✅ Topic renamed to '{topic_name}'")
            return

        thread_id = msg.message_thread_id

        # Check if topic is unknown and needs initialization
        if should_notify_unknown_topic(chat.id, thread_id):
            logger.info(f"Unknown topic detected (thread {thread_id}). Sending setup notification.")
            await msg.reply_text(
                "⚠️ This topic hasn't been named yet.\n\n"
                "To set a name, use:\n"
                "/name_topic <your topic name>\n\n"
                "Example:\n"
                "/name_topic AI Engineering\n\n"
                "You only need to do this once per topic."
            )
            mark_topic_as_notified(chat.id, thread_id)

        topic_name = get_topic_name(chat.id, thread_id)

        msg_type, text, file_id, file_uid = parse_message(msg)
        link = build_message_link(chat, msg.message_id)

        user_id = user.id if user else None
        username = user.username if user else None

        logger.info(f"Saving message: type={msg_type}, topic='{topic_name}', user={username}")
        
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
                chat.id,
                thread_id,
                topic_name,
                msg.message_id,
                user_id,
                username,
                msg_type,
                text,
                file_id,
                file_uid,
                link,
                datetime.now(UTC).isoformat()
            ))
            db_message_id = cur.lastrowid

        # --- AGENT ROUTING: Route to specialized agent based on topic ---
        if text:  # Only route text messages to agents
            logger.info(f"Routing message to agent for topic '{topic_name}'...")

            # Get router and route message
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

            # Update database with extracted link and summary (for indexing worker)
            extracted_url = extract_first_link(text)
            if extracted_url:
                # Get scraped content from cache (populated by web_scrape tool)
                scraped_summary = None
                try:
                    # Check url_scrape_cache table for the summary
                    with db_session() as cur:
                        cur.execute(
                            "SELECT summary FROM url_scrape_cache WHERE url = ?",
                            (extracted_url,)
                        )
                        row = cur.fetchone()
                        if row:
                            scraped_summary = row[0]
                            logger.debug(f"Found cached summary for {extracted_url}")
                except Exception as e:
                    logger.error(f"Error fetching summary from cache: {e}")

                # Update messages table with link and summary
                with db_session() as cur:
                    if scraped_summary:
                        cur.execute(
                            "UPDATE messages SET extracted_link = ?, summary = ? WHERE id = ?",
                            (extracted_url, scraped_summary, db_message_id)
                        )
                        logger.info(f"Updated message {db_message_id} with URL and summary")
                    else:
                        cur.execute(
                            "UPDATE messages SET extracted_link = ? WHERE id = ?",
                            (extracted_url, db_message_id)
                        )
                        logger.info(f"Updated message {db_message_id} with URL (summary not yet available)")

            # Send agent response directly (agent handles link summarization via web_scrape tool)
            logger.info(f"Successfully processed message {msg.message_id}")

            # Safety check: Ensure response is not empty
            if response_text and response_text.strip():
                await msg.reply_text(response_text)
            else:
                logger.warning(f"Agent returned empty response for message {msg.message_id}")
                await msg.reply_text("✅ Got it! I'm processing this information.")

        else:
            # Non-text message (photos, videos, etc.) - simple acknowledgment
            await msg.reply_text("✅ Saved!")

    except Exception:
        logger.exception("Failed to process message")

# ==========================================================
# ENTRYPOINT
# ==========================================================

def main():
    init_db()

    async def post_init(application):
        """Post-initialization hook to start background tasks."""
        # Set main event loop reference for RAG tools
        # This is required for asyncpg connection pools in production mode
        from tools.rag_tools import set_main_loop
        loop = asyncio.get_running_loop()
        set_main_loop(loop)

        # Pre-initialize LightRAG instances for faster first queries
        # This avoids 7+ second initialization delay on first message
        from lightrag_manager import warm_up_lightrag
        logger.info("Warming up LightRAG instances...")
        await warm_up_lightrag()

        # Start URL indexing worker in background
        indexing_worker = get_indexing_worker()
        asyncio.create_task(indexing_worker.start())
        logger.info("Bot is running with RAG indexing worker")

    app = ApplicationBuilder().token(config.telegram_bot_token).post_init(post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("name_topic", name_topic_command))
    app.add_handler(CommandHandler("check_topics", check_topics_command))

    # Message handler (must be last to not intercept commands)
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.StatusUpdate.ALL,
            handle_message
        )
    )

    app.run_polling()

if __name__ == "__main__":
    main()