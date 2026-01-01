#!/usr/bin/env python3
"""
Migration: Add indexed_urls table and backfill from existing data.

This migration:
1. Creates indexed_urls table (via init_db)
2. Backfills data from existing indexed messages
3. Handles duplicates gracefully

Run: python scripts/migrate_indexed_urls.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from core.database import init_db, db_session
from core.url_utils import normalize_url

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate():
    """Run migration to add indexed_urls table and backfill data."""
    logger.info("=" * 60)
    logger.info("Starting migration: Add indexed_urls table")
    logger.info("=" * 60)

    # Step 1: Initialize database (creates indexed_urls table if not exists)
    logger.info("Step 1: Creating indexed_urls table...")
    init_db()
    logger.info("✓ Table created")

    # Step 2: Backfill from existing indexed messages
    logger.info("\nStep 2: Backfilling from existing messages...")

    with db_session() as cur:
        # Get all indexed messages with URLs
        cur.execute("""
            SELECT id, extracted_link, topic_name, created_at
            FROM messages
            WHERE indexed_to_rag = 1
              AND extracted_link IS NOT NULL
            ORDER BY created_at ASC
        """)
        messages = cur.fetchall()

        logger.info(f"Found {len(messages)} indexed messages with URLs")

        inserted = 0
        skipped = 0

        for msg_id, url, topic, created_at in messages:
            try:
                normalized = normalize_url(url)

                cur.execute("""
                    INSERT OR IGNORE INTO indexed_urls
                    (url, original_url, topic_name, first_indexed_at, first_message_id, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (normalized, url, topic, created_at, msg_id, created_at))

                if cur.rowcount > 0:
                    inserted += 1
                    if inserted % 10 == 0:
                        logger.info(f"  Processed {inserted} URLs...")
                else:
                    skipped += 1

            except Exception as e:
                logger.warning(f"  Error processing message {msg_id}: {e}")
                skipped += 1

    # Step 3: Verify results
    logger.info("\nStep 3: Verifying migration...")

    with db_session() as cur:
        cur.execute("SELECT COUNT(*) FROM indexed_urls")
        total_indexed = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT topic_name) FROM indexed_urls")
        topics_count = cur.fetchone()[0]

    logger.info("=" * 60)
    logger.info("Migration Complete!")
    logger.info("=" * 60)
    logger.info(f"✓ Total URLs tracked: {total_indexed}")
    logger.info(f"✓ Topics with indexed URLs: {topics_count}")
    logger.info(f"✓ New entries: {inserted}")
    logger.info(f"✓ Skipped (duplicates): {skipped}")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        migrate()
    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)
