"""
Parse PostgreSQL connection string and output .env format.

Supports both Supabase and Neon connection strings.
"""
import sys
import re
from urllib.parse import urlparse, parse_qs


def parse_postgres_url(connection_string: str) -> dict:
    """
    Parse PostgreSQL connection string.

    Args:
        connection_string: PostgreSQL connection URL

    Returns:
        Dict with connection details
    """
    try:
        # Parse URL
        parsed = urlparse(connection_string)

        # Extract components
        host = parsed.hostname
        port = parsed.port or 5432
        database = parsed.path.lstrip('/')
        username = parsed.username
        password = parsed.password

        # Parse query parameters
        params = parse_qs(parsed.query)

        return {
            "host": host,
            "port": port,
            "database": database or "postgres",
            "user": username,
            "password": password,
            "ssl_mode": params.get("sslmode", ["prefer"])[0]
        }

    except Exception as e:
        print(f"Error parsing connection string: {e}")
        return None


def detect_provider(host: str) -> str:
    """Detect database provider from hostname."""
    if "supabase" in host:
        return "Supabase"
    elif "neon" in host:
        return "Neon"
    elif "railway" in host:
        return "Railway"
    elif "render" in host:
        return "Render"
    else:
        return "PostgreSQL"


def print_env_format(details: dict):
    """Print connection details in .env format."""
    provider = detect_provider(details["host"])

    print("\n" + "="*70)
    print(f"PARSED CONNECTION DETAILS ({provider})")
    print("="*70)
    print("\nAdd these to your .env file:\n")
    print("# PostgreSQL connection")
    print(f'POSTGRES_HOST={details["host"]}')
    print(f'POSTGRES_PORT={details["port"]}')
    print(f'POSTGRES_USER={details["user"]}')
    print(f'POSTGRES_PASSWORD={details["password"]}')
    print(f'POSTGRES_DATABASE={details["database"]}')
    print(f'POSTGRES_MAX_CONNECTIONS=10')
    print("\n" + "="*70)
    print("\n✅ Copy the lines above to your .env file")
    print("\nNext steps:")
    print("  1. Update .env with these values")
    print("  2. Run: uv run python scripts/check_production_config.py")
    print("  3. Run: uv run python scripts/init_production_db.py")
    print("="*70 + "\n")


def main():
    """Main entry point."""
    print("="*70)
    print("POSTGRESQL CONNECTION STRING PARSER")
    print("="*70)
    print("\nSupports: Supabase, Neon, Railway, Render, and standard PostgreSQL")
    print()

    # Check if connection string provided as argument
    if len(sys.argv) > 1:
        connection_string = sys.argv[1]
    else:
        # Ask for input
        print("Paste your PostgreSQL connection string:")
        print()
        print("Examples:")
        print("  Neon:     postgresql://user:pass@ep-xxx.neon.tech:5432/db")
        print("  Supabase: postgresql://postgres:[pass]@db.xxx.supabase.co:5432/postgres")
        print()
        connection_string = input("Connection string: ").strip()

    if not connection_string:
        print("\n❌ No connection string provided")
        print("\nUsage:")
        print('  python scripts/parse_connection_string.py "postgresql://..."')
        print("  OR")
        print("  python scripts/parse_connection_string.py")
        print("  (then paste when prompted)")
        sys.exit(1)

    # Remove quotes if present
    connection_string = connection_string.strip('"\'')

    # Parse
    details = parse_postgres_url(connection_string)

    if details:
        # Validate required fields
        if not details["host"]:
            print("\n❌ Error: No host found in connection string")
            sys.exit(1)
        if not details["user"]:
            print("\n❌ Error: No username found in connection string")
            sys.exit(1)
        if not details["password"]:
            print("\n⚠️  Warning: No password found in connection string")
            print("   You may need to add it manually")

        # Print formatted output
        print_env_format(details)

        # Additional info
        provider = detect_provider(details["host"])
        if provider == "Neon":
            print("💡 Neon Tips:")
            print("  - Connection string shown on dashboard immediately")
            print("  - Auto-pauses after 5 minutes (saves compute hours)")
            print("  - pgvector: CREATE EXTENSION IF NOT EXISTS vector;")
        elif provider == "Supabase":
            print("💡 Supabase Tips:")
            print("  - Find connection string: Settings → Database → Python tab")
            print("  - Use connection pooler for better performance")
            print("  - pgvector is pre-installed (PostgreSQL 15.2+)")

    else:
        print("\n❌ Failed to parse connection string")
        print("\nMake sure it's in the format:")
        print("  postgresql://user:password@host:port/database")


if __name__ == "__main__":
    main()
