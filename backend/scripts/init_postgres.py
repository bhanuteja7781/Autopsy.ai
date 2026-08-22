import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)
root_env = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(root_env, override=True)

# Add root directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from backend.api.database import engine, Base, DATABASE_URL
from backend.api.models import Entity, Claim, Comparison, User


def ensure_database_exists():
    """Checks if the PostgreSQL database exists; creates it if missing."""
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "autopsy_db")

    # If DATABASE_URL is set, extract components or use standard parameters
    if DATABASE_URL and "://" in DATABASE_URL:
        # Extract db name from URL
        db_name = DATABASE_URL.split("/")[-1].split("?")[0] or db_name

    try:
        # Connect to default 'postgres' database to check/create target database
        conn = psycopg2.connect(
            dbname="postgres",
            user=user,
            password=password,
            host=host,
            port=port,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()
        if not exists:
            print(f"[pgAdmin / PostgreSQL] Database '{db_name}' not found. Creating database '{db_name}'...")
            cur.execute(f'CREATE DATABASE "{db_name}"')
            print(f"[pgAdmin / PostgreSQL] Database '{db_name}' created successfully!")
        else:
            print(f"[pgAdmin / PostgreSQL] Database '{db_name}' exists.")
        cur.close()
        conn.close()
    except Exception as e:
        # If we can't create or connect to postgres db, continue to let Base.metadata.create_all report
        print(f"[pgAdmin Note] Pre-check connection note: {e}")


def init_db():
    print("\n=======================================================")
    print("  AUTOPSY.AI — PostgreSQL / pgAdmin Table Initialization")
    print("=======================================================")
    print(f"[PostgreSQL] Connecting with DATABASE_URL...")
    
    ensure_database_exists()

    try:
        # Create all tables (entities, claims, comparisons)
        Base.metadata.create_all(bind=engine)
        print("\n[SUCCESS] PostgreSQL tables successfully created:")
        print("  - entities")
        print("  - claims")
        print("  - comparisons")
        print("=======================================================\n")
    except psycopg2.OperationalError as e:
        print(f"\n[PostgreSQL Auth/Connection Error]: {e}")
        print("\n--> TO FIX THIS:")
        print("  1. Open 'backend/.env'")
        print("  2. Set your pgAdmin / PostgreSQL password:")
        print('     DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@localhost:5432/autopsy_db"')
        print("     or set POSTGRES_PASSWORD=YOUR_PASSWORD")
        print("  3. Re-run: python backend/scripts/init_postgres.py\n")
    except Exception as e:
        print(f"\n[PostgreSQL Init Error]: {e}")


if __name__ == "__main__":
    init_db()
