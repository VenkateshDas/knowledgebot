"""
Test database connectivity.

Helps diagnose connection issues with PostgreSQL and Neo4j.
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv("/Users/venkateshmurugadas/software_codes/telegram_exp/.env")


async def test_postgres():
    """Test PostgreSQL connection."""
    print("=" * 70)
    print("TESTING POSTGRESQL CONNECTION")
    print("=" * 70)

    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DATABASE")

    print(f"\nConnection details:")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  User: {user}")
    print(f"  Password: {'*' * len(password) if password else 'NOT SET'}")
    print(f"  Database: {database}")
    print()

    # Check DNS resolution
    print("Testing DNS resolution...")
    import socket
    try:
        ip = socket.gethostbyname(host)
        print(f"✓ DNS resolved: {host} -> {ip}")
    except socket.gaierror as e:
        print(f"✗ DNS resolution failed: {e}")
        print(f"\nPossible issues:")
        print(f"  1. Hostname is incorrect")
        print(f"  2. Supabase project doesn't exist or was deleted")
        print(f"  3. Network connectivity issue")
        print(f"\nPlease verify:")
        print(f"  1. Go to https://supabase.com/dashboard")
        print(f"  2. Select your project")
        print(f"  3. Go to Settings → Database")
        print(f"  4. Copy the connection string and update .env")
        return False

    # Try to connect
    print("\nTesting database connection...")
    try:
        import asyncpg
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
            timeout=10,
            ssl='require'  # Supabase requires SSL
        )
        print("✓ Successfully connected to PostgreSQL!")

        # Test pgvector extension
        print("\nChecking pgvector extension...")
        result = await conn.fetch(
            "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"
        )
        if result:
            print(f"✓ pgvector extension installed: version {result[0]['extversion']}")
        else:
            print("✗ pgvector extension not installed")
            print("\nTo install:")
            print("  1. Go to Supabase SQL Editor")
            print("  2. Run: CREATE EXTENSION IF NOT EXISTS vector;")

        await conn.close()
        return True

    except Exception as e:
        import traceback
        print(f"✗ Connection failed: {type(e).__name__}: {e}")
        print(f"\nDetailed error:")
        print(traceback.format_exc())

        # Provide specific guidance based on error type
        if "authentication failed" in str(e).lower():
            print("\n💡 Password is incorrect. Check:")
            print("  1. Go to Supabase Dashboard → Settings → Database")
            print("  2. Click 'Reset Database Password'")
            print("  3. Copy the new password to .env")
        elif "does not exist" in str(e).lower():
            print("\n💡 Database name might be wrong. Try:")
            print("  POSTGRES_DATABASE=postgres")
        elif "timeout" in str(e).lower() or "refused" in str(e).lower():
            print("\n💡 Connection blocked. Possible causes:")
            print("  1. Supabase project is paused (check dashboard)")
            print("  2. Firewall blocking connection")
            print("  3. Try connection pooler instead (see SUPABASE_CONNECTION_FIX.md)")

        return False


async def test_neo4j():
    """Test Neo4j connection."""
    print("\n" + "=" * 70)
    print("TESTING NEO4J CONNECTION")
    print("=" * 70)

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    print(f"\nConnection details:")
    print(f"  URI: {uri}")
    print(f"  Username: {username}")
    print(f"  Password: {'*' * len(password) if password else 'NOT SET'}")
    print()

    if not uri:
        print("✗ NEO4J_URI not set in .env")
        return False

    if not password:
        print("✗ NEO4J_PASSWORD not set in .env")
        return False

    print("Testing Neo4j connection...")
    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

        async with driver.session() as session:
            result = await session.run("RETURN 1 AS num")
            record = await result.single()

        await driver.close()

        print("✓ Successfully connected to Neo4j!")
        return True

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print(f"\nPossible issues:")
        print(f"  1. NEO4J_URI is incorrect")
        print(f"  2. NEO4J_PASSWORD is incorrect")
        print(f"  3. Neo4j Aura instance is paused or deleted")
        print(f"\nPlease verify:")
        print(f"  1. Go to https://console.neo4j.io")
        print(f"  2. Check if your instance is running")
        print(f"  3. Verify connection details")
        return False


async def main():
    """Run all connection tests."""
    postgres_ok = await test_postgres()
    neo4j_ok = await test_neo4j()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"PostgreSQL: {'✓ OK' if postgres_ok else '✗ FAILED'}")
    print(f"Neo4j: {'✓ OK' if neo4j_ok else '✗ FAILED'}")

    if postgres_ok and neo4j_ok:
        print("\n🎉 All connections successful!")
        print("You can now run: uv run python scripts/init_production_db.py")
    else:
        print("\n⚠️  Fix the connection issues above before proceeding")


if __name__ == "__main__":
    asyncio.run(main())
