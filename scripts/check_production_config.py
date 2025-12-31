"""
Check production configuration before deployment.

Validates that all required environment variables are set correctly.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def check_env_var(var_name: str, required: bool = True) -> bool:
    """
    Check if environment variable is set.

    Args:
        var_name: Name of the environment variable
        required: Whether this variable is required

    Returns:
        True if valid, False otherwise
    """
    value = os.getenv(var_name)

    if not value:
        if required:
            print(f"{RED}✗{RESET} {var_name}: NOT SET (required)")
            return False
        else:
            print(f"{YELLOW}⚠{RESET} {var_name}: NOT SET (optional)")
            return True

    # Check for placeholder values
    placeholder_values = [
        "your_",
        "xxxxx",
        "password_here",
        "token_here",
        "key_here"
    ]

    if any(placeholder in value.lower() for placeholder in placeholder_values):
        print(f"{RED}✗{RESET} {var_name}: Contains placeholder value")
        print(f"   Current: {value[:50]}...")
        return False

    # Mask sensitive values
    if "password" in var_name.lower() or "token" in var_name.lower() or "key" in var_name.lower():
        masked = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "***"
        print(f"{GREEN}✓{RESET} {var_name}: {masked}")
    else:
        # Show full value for non-sensitive vars
        display_value = value if len(value) < 50 else value[:47] + "..."
        print(f"{GREEN}✓{RESET} {var_name}: {display_value}")

    return True


def check_production_mode():
    """Check if production mode is enabled."""
    production_mode = os.getenv("LIGHTRAG_PRODUCTION", "false").lower()

    if production_mode == "true":
        print(f"{GREEN}✓{RESET} LIGHTRAG_PRODUCTION: true (production mode enabled)")
        return True
    else:
        print(f"{YELLOW}⚠{RESET} LIGHTRAG_PRODUCTION: {production_mode} (development mode)")
        print(f"   {BLUE}Note:{RESET} Set LIGHTRAG_PRODUCTION=true to use databases")
        return False


def check_database_config(production_mode: bool):
    """
    Check database configuration.

    Args:
        production_mode: Whether production mode is enabled
    """
    if not production_mode:
        print(f"\n{BLUE}Development Mode:{RESET} Using file-based storage")
        print(f"  Working directory: {os.getenv('LIGHTRAG_WORKING_DIR', './lightrag_data')}")
        return True

    print(f"\n{BLUE}Checking Production Database Configuration:{RESET}")
    print("-" * 60)

    all_valid = True

    # PostgreSQL configuration
    print(f"\n{BLUE}PostgreSQL (Supabase):{RESET}")
    all_valid &= check_env_var("POSTGRES_HOST")
    all_valid &= check_env_var("POSTGRES_PORT")
    all_valid &= check_env_var("POSTGRES_USER")
    all_valid &= check_env_var("POSTGRES_PASSWORD")
    all_valid &= check_env_var("POSTGRES_DATABASE")

    # Neo4j configuration
    print(f"\n{BLUE}Neo4j Aura:{RESET}")
    all_valid &= check_env_var("NEO4J_URI")
    all_valid &= check_env_var("NEO4J_USERNAME")
    all_valid &= check_env_var("NEO4J_PASSWORD")

    return all_valid


def check_bot_config():
    """Check bot configuration."""
    print(f"\n{BLUE}Bot Configuration:{RESET}")
    print("-" * 60)

    all_valid = True

    all_valid &= check_env_var("TELEGRAM_BOT_TOKEN")
    all_valid &= check_env_var("OPENROUTER_API_KEY")

    return all_valid


def check_production_dependencies():
    """Check if production dependencies are installed."""
    print(f"\n{BLUE}Production Dependencies:{RESET}")
    print("-" * 60)

    dependencies = [
        ("psycopg2", "PostgreSQL adapter"),
        ("asyncpg", "Async PostgreSQL"),
        ("neo4j", "Neo4j driver"),
    ]

    all_installed = True

    for package, description in dependencies:
        try:
            __import__(package)
            print(f"{GREEN}✓{RESET} {package}: Installed ({description})")
        except ImportError:
            print(f"{RED}✗{RESET} {package}: NOT INSTALLED ({description})")
            all_installed = False

    if not all_installed:
        print(f"\n{YELLOW}Install production dependencies:{RESET}")
        print(f"  uv sync --extra production")

    return all_installed


def check_files_exist():
    """Check if required files exist."""
    print(f"\n{BLUE}Required Files:{RESET}")
    print("-" * 60)

    files = [
        (".env", "Environment variables"),
        ("config/lightrag_production.py", "Production configuration"),
        ("scripts/init_production_db.py", "Database initialization"),
    ]

    all_exist = True

    for file_path, description in files:
        if Path(file_path).exists():
            print(f"{GREEN}✓{RESET} {file_path}: Exists ({description})")
        else:
            print(f"{RED}✗{RESET} {file_path}: NOT FOUND ({description})")
            all_exist = False

    return all_exist


def main():
    """Main entry point."""
    print("=" * 70)
    print(f"{BLUE}PRODUCTION CONFIGURATION CHECK{RESET}")
    print("=" * 70)

    # Load .env file if it exists
    env_file = Path(".env")
    if env_file.exists():
        print(f"\n{GREEN}Loading .env file...{RESET}")
        from dotenv import load_dotenv
        load_dotenv()
    else:
        print(f"\n{YELLOW}⚠ .env file not found{RESET}")
        print(f"  Copy .env.example to .env and fill in your values")

    # Check production mode
    print(f"\n{BLUE}Mode Detection:{RESET}")
    print("-" * 60)
    production_mode = check_production_mode()

    # Check files
    files_ok = check_files_exist()

    # Check dependencies (only if production mode)
    if production_mode:
        deps_ok = check_production_dependencies()
    else:
        deps_ok = True

    # Check bot configuration
    bot_ok = check_bot_config()

    # Check database configuration
    db_ok = check_database_config(production_mode)

    # Summary
    print("\n" + "=" * 70)
    print(f"{BLUE}CONFIGURATION SUMMARY{RESET}")
    print("=" * 70)

    all_ok = files_ok and deps_ok and bot_ok and (db_ok or not production_mode)

    if all_ok:
        print(f"\n{GREEN}✅ All checks passed!{RESET}")

        if production_mode:
            print(f"\n{BLUE}Next steps:{RESET}")
            print(f"  1. Initialize databases: uv run python scripts/init_production_db.py")
            print(f"  2. Test locally: uv run python telegram_bot.py")
            print(f"  3. Deploy to Fly.io: fly deploy")
        else:
            print(f"\n{BLUE}Development mode ready!{RESET}")
            print(f"  To enable production mode:")
            print(f"  1. Set LIGHTRAG_PRODUCTION=true in .env")
            print(f"  2. Configure Supabase and Neo4j credentials")
            print(f"  3. Run this check again")

    else:
        print(f"\n{RED}❌ Configuration incomplete{RESET}")

        print(f"\n{BLUE}Fix these issues:{RESET}")
        if not files_ok:
            print(f"  • Create missing files (see above)")
        if not deps_ok:
            print(f"  • Install dependencies: uv sync --extra production")
        if not bot_ok:
            print(f"  • Set bot credentials in .env")
        if production_mode and not db_ok:
            print(f"  • Set database credentials in .env")

        print(f"\n{BLUE}See setup guide:{RESET} SETUP_PRODUCTION.md")

        return 1

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
