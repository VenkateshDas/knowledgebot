"""
Migrate existing file-based LightRAG data to production databases.

Reads data from JSON files and re-indexes into PostgreSQL + Neo4j.
"""
import asyncio
import logging
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightrag_manager import get_lightrag_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LIGHTRAG_FILE_DIR = Path(os.getenv("LIGHTRAG_WORKING_DIR", "./lightrag_data"))


async def migrate_topic(topic_name: str, file_dir: Path, dry_run: bool = False):
    """
    Migrate a single topic's data.

    Args:
        topic_name: Name of the topic
        file_dir: Directory containing file-based data
        dry_run: If True, only simulate migration without writing
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Migrating topic: {topic_name}")
    logger.info(f"{'='*70}")

    # Load file-based data
    kv_docs_file = file_dir / "kv_store_full_docs.json"

    if not kv_docs_file.exists():
        logger.warning(f"No data found for {topic_name} at {kv_docs_file}, skipping...")
        return 0

    # Read documents
    try:
        with open(kv_docs_file, 'r', encoding='utf-8') as f:
            docs_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {kv_docs_file}: {e}")
        return 0

    documents = docs_data.get("data", [])

    if not documents:
        logger.warning(f"No documents found in {kv_docs_file}")
        return 0

    logger.info(f"Found {len(documents)} documents to migrate")

    if dry_run:
        logger.info("[DRY RUN] Would migrate these documents (not actually writing)")
        for i, doc_entry in enumerate(documents[:5], 1):  # Show first 5
            content_preview = str(doc_entry.get("content", ""))[:100]
            logger.info(f"  {i}. {content_preview}...")
        if len(documents) > 5:
            logger.info(f"  ... and {len(documents) - 5} more")
        return len(documents)

    # Get production RAG instance
    manager = get_lightrag_manager()
    rag = await manager.get_rag_for_topic(topic_name)

    # Re-index all documents
    migrated_count = 0
    failed_count = 0

    for i, doc_entry in enumerate(documents, 1):
        try:
            # Extract document content
            # LightRAG stores documents as {"id": "...", "content": "..."}
            if isinstance(doc_entry, dict):
                doc_content = doc_entry.get("content", "")
            else:
                doc_content = str(doc_entry)

            if not doc_content or len(doc_content.strip()) < 10:
                logger.debug(f"  [{i}/{len(documents)}] Skipping empty/short document")
                continue

            logger.info(f"  [{i}/{len(documents)}] Indexing document ({len(doc_content)} chars)...")

            # Re-insert into production storage
            await rag.ainsert(doc_content)
            migrated_count += 1

            # Small delay to avoid overwhelming the database
            if i % 10 == 0:
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"  Error migrating document {i}: {e}")
            failed_count += 1

    logger.info(f"\n✓ Migration summary for {topic_name}:")
    logger.info(f"  - Total documents: {len(documents)}")
    logger.info(f"  - Successfully migrated: {migrated_count}")
    logger.info(f"  - Failed: {failed_count}")

    return migrated_count


async def migrate_all_topics(dry_run: bool = False):
    """
    Migrate all topics from file storage to production.

    Args:
        dry_run: If True, only simulate migration
    """
    logger.info("="*70)
    logger.info("LIGHTRAG DATA MIGRATION TO PRODUCTION")
    logger.info("="*70)

    if dry_run:
        logger.info("\n⚠️  DRY RUN MODE - No data will be written\n")

    # Verify production mode
    production_mode = os.getenv("LIGHTRAG_PRODUCTION", "false").lower()
    if production_mode != "true" and not dry_run:
        logger.error("❌ LIGHTRAG_PRODUCTION is not set to 'true'")
        logger.error("   Add LIGHTRAG_PRODUCTION=true to your .env file")
        return

    if not LIGHTRAG_FILE_DIR.exists():
        logger.error(f"❌ File directory not found: {LIGHTRAG_FILE_DIR}")
        logger.error("   Make sure LIGHTRAG_WORKING_DIR is set correctly")
        return

    # Find all topic directories
    topic_dirs = [d for d in LIGHTRAG_FILE_DIR.iterdir() if d.is_dir()]

    if not topic_dirs:
        logger.warning(f"No topic directories found in {LIGHTRAG_FILE_DIR}")
        return

    logger.info(f"Found {len(topic_dirs)} topic(s) to migrate:\n")

    total_migrated = 0

    for topic_dir in sorted(topic_dirs):
        # Convert directory name to topic name
        # health -> Health, ai_engineering -> AI Engineering
        topic_name = topic_dir.name.replace("_", " ").title()

        migrated = await migrate_topic(topic_name, topic_dir, dry_run)
        total_migrated += migrated

    logger.info("\n" + "="*70)
    if dry_run:
        logger.info(f"✓ DRY RUN COMPLETE - Would migrate {total_migrated} documents")
        logger.info("\nTo perform actual migration:")
        logger.info("  uv run python scripts/migrate_to_production.py")
    else:
        logger.info(f"✅ MIGRATION COMPLETE - Migrated {total_migrated} documents")
        logger.info("\nNext steps:")
        logger.info("  1. Verify data: uv run python inspect_lightrag.py stats")
        logger.info("  2. Test queries: uv run python inspect_lightrag.py")
        logger.info("  3. Archive old files: mv lightrag_data lightrag_data.backup")
    logger.info("="*70)


def create_backup():
    """Create backup of file-based data before migration."""
    if not LIGHTRAG_FILE_DIR.exists():
        logger.warning(f"No data directory to backup: {LIGHTRAG_FILE_DIR}")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"lightrag_backup_{timestamp}.tar.gz"

    logger.info(f"\nCreating backup: {backup_name}")

    import subprocess
    try:
        result = subprocess.run(
            ["tar", "-czf", backup_name, str(LIGHTRAG_FILE_DIR)],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            logger.info(f"✓ Backup created successfully: {backup_name}")
            return backup_name
        else:
            logger.error(f"Backup failed: {result.stderr}")
            return None

    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


if __name__ == "__main__":
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Migrate LightRAG data to production")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without writing data"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup before migration"
    )

    args = parser.parse_args()

    # Create backup before migration (unless --no-backup or --dry-run)
    if not args.dry_run and not args.no_backup:
        backup_file = create_backup()
        if not backup_file:
            logger.error("❌ Backup failed. Aborting migration.")
            logger.error("   Use --no-backup to skip backup (not recommended)")
            sys.exit(1)

    # Run migration
    asyncio.run(migrate_all_topics(dry_run=args.dry_run))
