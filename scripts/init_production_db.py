"""
Initialize production databases for LightRAG.

Creates necessary tables, extensions, and indexes.
"""
import asyncio
import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightrag_manager import get_lightrag_manager
from config.lightrag_production import validate_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def init_databases():
    """Initialize production databases."""
    logger.info("="*70)
    logger.info("LIGHTRAG PRODUCTION DATABASE INITIALIZATION")
    logger.info("="*70)

    # Validate configuration
    try:
        validate_config()
        logger.info("✓ Configuration validated")
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return False

    # Verify production mode is enabled
    production_mode = os.getenv("LIGHTRAG_PRODUCTION", "false").lower()
    if production_mode != "true":
        logger.error("❌ LIGHTRAG_PRODUCTION is not set to 'true'")
        logger.error("   Add LIGHTRAG_PRODUCTION=true to your .env file")
        return False

    logger.info("✓ Production mode enabled")

    manager = get_lightrag_manager()

    # Create a test RAG instance to trigger database initialization
    test_topic = "initialization_test"

    try:
        logger.info(f"\nInitializing databases for topic: {test_topic}")
        rag = await manager.get_rag_for_topic(test_topic)
        logger.info("✓ Database tables created successfully")

        # Test basic operations
        logger.info("\nTesting database operations...")

        test_content = "This is a test document for database initialization. PostgreSQL and Neo4j are working correctly."

        await rag.ainsert(test_content)
        logger.info("✓ Insert operation successful")

        from lightrag import QueryParam
        result = await rag.aquery(
            "test database",
            param=QueryParam(mode="naive", top_k=1)
        )
        logger.info(f"✓ Query operation successful")

        if result and len(str(result)) > 10:
            logger.info(f"  Retrieved result: {str(result)[:100]}...")
        else:
            logger.warning(f"  Query returned minimal result: {result}")

        logger.info("\n" + "="*70)
        logger.info("✅ PRODUCTION DATABASES INITIALIZED SUCCESSFULLY!")
        logger.info("="*70)
        logger.info("\nNext steps:")
        logger.info("  1. Run migration: uv run python scripts/migrate_to_production.py")
        logger.info("  2. Verify data: uv run python inspect_lightrag.py stats")
        logger.info("  3. Test queries: uv run python inspect_lightrag.py query <topic> '<query>'")

        return True

    except Exception as e:
        logger.error(f"\n❌ DATABASE INITIALIZATION FAILED")
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("\nTroubleshooting:")
        logger.error("  1. Verify database credentials in .env")
        logger.error("  2. Check database connectivity")
        logger.error("  3. Ensure pgvector extension is installed (PostgreSQL)")
        logger.error("  4. Verify Neo4j instance is accessible")
        return False


if __name__ == "__main__":
    success = asyncio.run(init_databases())
    sys.exit(0 if success else 1)
