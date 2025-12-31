"""
Monitor Free Tier Usage for Supabase and Neo4j Aura.

Alerts when approaching capacity limits.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Free tier limits
SUPABASE_STORAGE_LIMIT_MB = 500
NEO4J_NODE_LIMIT = 50000
NEO4J_WRITE_LIMIT_MONTHLY = 1000
NEO4J_READ_LIMIT_MONTHLY = 100000

# Alert thresholds (percentage)
ALERT_THRESHOLD = 80


async def check_supabase_usage() -> Dict:
    """
    Check Supabase database storage usage.

    Returns:
        Dict with usage metrics
    """
    try:
        import psycopg2

        # Get connection details from environment
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            database=os.getenv("POSTGRES_DATABASE", "postgres")
        )

        cursor = conn.cursor()

        # Query database size
        cursor.execute("""
            SELECT pg_database_size(current_database()) / 1024 / 1024 AS size_mb;
        """)

        size_mb = cursor.fetchone()[0]

        # Query table sizes (top 10)
        cursor.execute("""
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 10;
        """)

        tables = cursor.fetchall()

        conn.close()

        usage_percent = (size_mb / SUPABASE_STORAGE_LIMIT_MB) * 100

        return {
            "provider": "Supabase",
            "storage_mb": round(size_mb, 2),
            "limit_mb": SUPABASE_STORAGE_LIMIT_MB,
            "usage_percent": round(usage_percent, 2),
            "alert": usage_percent >= ALERT_THRESHOLD,
            "top_tables": tables
        }

    except Exception as e:
        logger.error(f"Error checking Supabase usage: {e}")
        return {
            "provider": "Supabase",
            "error": str(e)
        }


async def check_neo4j_usage() -> Dict:
    """
    Check Neo4j Aura database usage.

    Returns:
        Dict with usage metrics
    """
    try:
        from neo4j import GraphDatabase

        # Get connection details from environment
        uri = os.getenv("NEO4J_URI")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")

        driver = GraphDatabase.driver(uri, auth=(username, password))

        with driver.session() as session:
            # Count total nodes
            result = session.run("MATCH (n) RETURN count(n) AS node_count")
            node_count = result.single()["node_count"]

            # Count total relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) AS rel_count")
            rel_count = result.single()["rel_count"]

            # Get node labels distribution
            result = session.run("""
                CALL db.labels() YIELD label
                CALL apoc.cypher.run('MATCH (:`'+label+'`) RETURN count(*) as count', {})
                YIELD value
                RETURN label, value.count AS count
                ORDER BY count DESC
                LIMIT 10
            """)
            labels = [(record["label"], record["count"]) for record in result]

        driver.close()

        node_usage_percent = (node_count / NEO4J_NODE_LIMIT) * 100

        return {
            "provider": "Neo4j Aura Free",
            "nodes": node_count,
            "node_limit": NEO4J_NODE_LIMIT,
            "node_usage_percent": round(node_usage_percent, 2),
            "relationships": rel_count,
            "alert": node_usage_percent >= ALERT_THRESHOLD,
            "top_labels": labels,
            "monthly_write_limit": NEO4J_WRITE_LIMIT_MONTHLY,
            "monthly_read_limit": NEO4J_READ_LIMIT_MONTHLY
        }

    except Exception as e:
        logger.error(f"Error checking Neo4j usage: {e}")
        return {
            "provider": "Neo4j Aura Free",
            "error": str(e)
        }


def print_usage_report(supabase_usage: Dict, neo4j_usage: Dict):
    """
    Print formatted usage report.

    Args:
        supabase_usage: Supabase metrics
        neo4j_usage: Neo4j metrics
    """
    print("\n" + "="*70)
    print("FREE TIER USAGE REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Supabase Report
    print("\n📦 SUPABASE (PostgreSQL + pgvector)")
    print("-"*70)

    if "error" in supabase_usage:
        print(f"❌ Error: {supabase_usage['error']}")
    else:
        size = supabase_usage["storage_mb"]
        limit = supabase_usage["limit_mb"]
        percent = supabase_usage["usage_percent"]

        print(f"Storage Used:  {size:.2f} MB / {limit} MB ({percent:.1f}%)")

        # Progress bar
        bar_length = 40
        filled = int(bar_length * percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        if percent < 50:
            status = "🟢 HEALTHY"
        elif percent < 80:
            status = "🟡 MONITOR"
        else:
            status = "🔴 ALERT - APPROACHING LIMIT"

        print(f"Progress:      [{bar}] {status}")

        if supabase_usage["alert"]:
            print(f"\n⚠️  WARNING: Storage at {percent:.1f}%")
            print(f"   Consider upgrading to Supabase Pro ($10/mo for 8GB)")

        # Top tables
        if supabase_usage.get("top_tables"):
            print(f"\nTop Tables by Size:")
            for schema, table, size in supabase_usage["top_tables"][:5]:
                print(f"  • {schema}.{table}: {size}")

    # Neo4j Report
    print("\n📊 NEO4J AURA FREE (Knowledge Graph)")
    print("-"*70)

    if "error" in neo4j_usage:
        print(f"❌ Error: {neo4j_usage['error']}")
    else:
        nodes = neo4j_usage["nodes"]
        node_limit = neo4j_usage["node_limit"]
        percent = neo4j_usage["node_usage_percent"]
        rels = neo4j_usage["relationships"]

        print(f"Nodes:         {nodes:,} / {node_limit:,} ({percent:.1f}%)")
        print(f"Relationships: {rels:,}")

        # Progress bar
        bar_length = 40
        filled = int(bar_length * percent / 100)
        bar = "█" * filled + "░" * (bar_length - filled)

        if percent < 50:
            status = "🟢 HEALTHY"
        elif percent < 80:
            status = "🟡 MONITOR"
        else:
            status = "🔴 ALERT - APPROACHING LIMIT"

        print(f"Progress:      [{bar}] {status}")

        if neo4j_usage["alert"]:
            print(f"\n⚠️  WARNING: Node count at {percent:.1f}%")
            print(f"   Consider upgrading to Neo4j Aura Professional ($65/mo)")

        # Monthly limits
        print(f"\nMonthly Limits:")
        print(f"  • Writes:  1,000/month (~33/day)")
        print(f"  • Reads:   100,000/month (~3,333/day)")
        print(f"  ℹ️  Track actual usage in Neo4j Aura Console")

        # Top labels
        if neo4j_usage.get("top_labels"):
            print(f"\nTop Node Labels:")
            for label, count in neo4j_usage["top_labels"][:5]:
                print(f"  • {label}: {count:,} nodes")

    # Overall Status
    print("\n" + "="*70)

    supabase_ok = not supabase_usage.get("alert", False) and "error" not in supabase_usage
    neo4j_ok = not neo4j_usage.get("alert", False) and "error" not in neo4j_usage

    if supabase_ok and neo4j_ok:
        print("✅ OVERALL STATUS: HEALTHY - All systems within free tier limits")
    elif not supabase_usage.get("alert") and not neo4j_usage.get("alert"):
        print("🟡 OVERALL STATUS: MONITOR - Usage increasing, watch carefully")
    else:
        print("🔴 OVERALL STATUS: ACTION REQUIRED - Approaching free tier limits")

    print("="*70)

    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-"*70)

    if supabase_usage.get("alert"):
        print("📦 Supabase:")
        print("  1. Review and delete old/unused data")
        print("  2. Compress embeddings if possible")
        print("  3. Consider upgrading to Pro ($10/mo for 8GB)")

    if neo4j_usage.get("alert"):
        print("📊 Neo4j:")
        print("  1. Review node count - delete test/old data")
        print("  2. Consider PostgreSQL AGE extension (unlimited, free)")
        print("  3. Or upgrade to Neo4j Aura Pro ($65/mo)")

    if not supabase_usage.get("alert") and not neo4j_usage.get("alert"):
        print("  ✓ No action needed - continue monitoring monthly")

    print()


async def send_telegram_alert(message: str):
    """
    Send alert to Telegram bot owner.

    Args:
        message: Alert message
    """
    # TODO: Implement Telegram notification
    # Use your bot to send message to admin user
    pass


async def main():
    """Main entry point."""
    logger.info("Checking free tier usage...")

    # Check both services
    supabase_usage = await check_supabase_usage()
    neo4j_usage = await check_neo4j_usage()

    # Print report
    print_usage_report(supabase_usage, neo4j_usage)

    # Send alerts if needed
    if supabase_usage.get("alert") or neo4j_usage.get("alert"):
        alert_msg = "⚠️ Free Tier Alert:\n"
        if supabase_usage.get("alert"):
            alert_msg += f"Supabase at {supabase_usage['usage_percent']:.1f}%\n"
        if neo4j_usage.get("alert"):
            alert_msg += f"Neo4j at {neo4j_usage['node_usage_percent']:.1f}%\n"

        await send_telegram_alert(alert_msg)


if __name__ == "__main__":
    asyncio.run(main())
