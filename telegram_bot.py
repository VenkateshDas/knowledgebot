# telegram_bot.py

import sqlite3
import logging
from datetime import datetime, UTC
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
import os
import requests
from openai import OpenAI
import re
import json
from contextlib import contextmanager
from dotenv import load_dotenv
import asyncio

# Import agent router
from agent_router import get_router

load_dotenv()

# ==========================================================
# CONFIG
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8497263383:AAEWuUq_F7fYPtev5ymbsIN9cnWlF0vgG3Q"
DB_PATH = os.getenv("DB_PATH", "bot.db")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.1")

if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY is not set. Categorization and summarization will fail.")
if not FIRECRAWL_API_KEY:
    logger.warning("FIRECRAWL_API_KEY is not set. Summarization will fail.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)



# ==========================================================
# DATABASE
# ==========================================================

def init_db():
    logger.info("Initializing database...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        chat_id INTEGER,
        thread_id INTEGER,
        topic_name TEXT,
        updated_at TEXT,
        PRIMARY KEY (chat_id, thread_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
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
        created_at TEXT
    )
    """)

    conn.commit()

    # Migration for new columns
    cur = conn.cursor()
    new_columns = [
        ("primary_category", "TEXT"),
        ("secondary_tags", "TEXT"),
        ("extracted_link", "TEXT"),
        ("summary", "TEXT")
    ]
    
    for col_name, col_type in new_columns:
        try:
            cur.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_type}")
            logger.info(f"Added column {col_name} to messages table.")
        except sqlite3.OperationalError:
            pass # Column likely exists

    conn.commit()
    conn.close()

@contextmanager
def db_session():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()

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

def categorize_message(text, topic_name=None):
    if not text or not OPENROUTER_API_KEY:
        return None, None

    # Check if we should use topic as primary category
    use_topic_as_category = (
        topic_name and
        topic_name != "General" and
        not topic_name.startswith("Topic_")
    )

    try:
        if use_topic_as_category:
            # Topic name is the primary category, only get secondary tags from LLM
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that generates relevant tags for messages.\n"
                            "Generate 2-5 short, descriptive keywords related to the message content.\n"
                            "Output ONLY a JSON object in this exact format:\n"
                            "{\"secondary_tags\": [\"tag1\", \"tag2\", \"tag3\"]}\n"
                            "Example: {\"secondary_tags\": [\"startup\", \"mobile app\", \"product idea\"]}"
                        )
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ]
            )

            content = completion.choices[0].message.content.strip()
            logger.debug(f"Categorization response (tags): {content}")

            # Try to extract JSON if wrapped in code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            return topic_name, json.dumps(data.get("secondary_tags", []))
        else:
            # No topic or generic topic, let LLM choose both category and tags
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that categorizes messages.\n"
                            "The primary categories are: 'AI Engineering', 'General', 'Rants', 'Ideas', 'Health', 'Wealth', 'Journal'.\n"
                            "Output ONLY a JSON object in this exact format:\n"
                            "{\"primary_category\": \"category_name\", \"secondary_tags\": [\"tag1\", \"tag2\"]}\n"
                            "Example: {\"primary_category\": \"Ideas\", \"secondary_tags\": [\"startup\", \"mobile app\"]}"
                        )
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ]
            )

            content = completion.choices[0].message.content.strip()
            logger.debug(f"Categorization response (full): {content}")

            # Try to extract JSON if wrapped in code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            return data.get("primary_category"), json.dumps(data.get("secondary_tags", []))

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing categorization JSON: {e}. Content: {content[:200]}")
        return None, None
    except Exception as e:
        logger.error(f"Error classifying message: {e}")
        return None, None

# --- Journal Agent Integration Helpers ---

async def categorize_message_async(text, topic_name=None):
    """Async wrapper for categorize_message to use in journal handler."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, categorize_message, text, topic_name)

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

# --- End Journal Integration Helpers ---

def extract_first_link(text):
    if not text:
        return None
    url_pattern = r'(https?://[^\s]+)'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None

def scrape_with_jina(url):
    """Fallback scraping using Jina Reader."""
    try:
        logger.info(f"Scraping with Jina Reader: {url}")
        jina_url = f"https://r.jina.ai/{url}"
        response = requests.get(jina_url)
        if response.status_code == 200:
            return response.text
        else:
            logger.error(f"Jina Reader failed: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error in Jina scraping: {e}")
    return None

def scrape_and_summarize(url):
    if not url or not OPENROUTER_API_KEY:
        return None
        
    markdown_content = None

    # 1. Determine scraping method
    # Prefer Firecrawl generally, but use Jina for LinkedIn or fallback
    use_jina = "linkedin.com" in url
    
    if not use_jina and FIRECRAWL_API_KEY:
        try:
            scrape_url = "https://api.firecrawl.dev/v1/scrape"
            headers = {
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {"url": url}
            
            response = requests.post(scrape_url, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    markdown_content = data.get("data", {}).get("markdown", "")
            
            if not markdown_content:
                logger.warning(f"Firecrawl failed or empty for {url}. Attempting fallback.")
        except Exception as e:
            logger.error(f"Firecrawl error: {e}")
    
    # 2. Fallback / Direct Jina
    if not markdown_content:
        markdown_content = scrape_with_jina(url)

    if not markdown_content:
        logger.error("All scraping methods failed.")
        return None

    # 3. Summarize with OpenRouter
    try:
        completion = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert summarizer. Create a concise, information-dense summary of the content.\n"
                        "Format your response as 5-10 bullet points maximum.\n"
                        "Use PLAIN TEXT only - no Markdown formatting, no asterisks, no underscores, no hashtags.\n"
                        "Start each bullet point with a dash (-) or bullet (•).\n"
                        "Focus on the most important insights, key takeaways, and actionable information.\n"
                        "Be direct and clear. Each bullet should be one concise sentence or phrase."
                    )
                },
                {
                    "role": "user",
                    "content": markdown_content[:50000] 
                }
            ]
        )
        return completion.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error in summary generation: {e}")
        return None

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
                categorize_func=categorize_message_async,
                update_categories_func=update_message_categories
            )

            # Update database with extracted link (for record-keeping)
            extracted_url = extract_first_link(text)
            if extracted_url:
                with db_session() as cur:
                    cur.execute(
                        "UPDATE messages SET extracted_link = ? WHERE id = ?",
                        (extracted_url, db_message_id)
                    )

            # Send agent response directly (agent handles link summarization via web_scrape tool)
            logger.info(f"Successfully processed message {msg.message_id}")
            await msg.reply_text(response_text)

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

    app = ApplicationBuilder().token(BOT_TOKEN).build()

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

    logger.info("Bot is running")
    app.run_polling()

if __name__ == "__main__":
    main()