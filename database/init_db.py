"""
database/init_db.py
Run this script once after creating your new PostgreSQL database.
Usage:
    python database/init_db.py
    # or pass URL directly:
    python database/init_db.py "postgresql://user:pass@host:5432/dbname?schema=public"
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.postgres_service import _parse_database_url

def init_database(db_url: str = None):
    if not db_url:
        if len(sys.argv) > 1:
            db_url = sys.argv[1]
        else:
            db_url = os.getenv("DATABASE_URL", "").strip()

    if not db_url or "<username>" in db_url or "<friend-ip>" in db_url:
        print("[ERROR] Please provide a valid DATABASE_URL in .env or pass it as an argument:")
        print('  python database/init_db.py "postgresql://username:password@host:5432/dbname?schema=public"')
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("[ERROR] psycopg2 is not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    print(f"[InitDB] Parsing connection URL...")
    conn_params = _parse_database_url(db_url)

    print(f"[InitDB] Connecting to database '{conn_params.get('database')}' at {conn_params.get('host')}...")
    try:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to database: {e}")
        sys.exit(1)

    schema_file = Path(__file__).resolve().parent / "schema.sql"
    if not schema_file.exists():
        print(f"[ERROR] schema.sql not found at {schema_file}")
        sys.exit(1)

    print(f"[InitDB] Reading schema from {schema_file}...")
    sql_commands = schema_file.read_text(encoding="utf-8-sig")

    print("[InitDB] Executing DDL statements...")
    try:
        cur.execute(sql_commands)
        print("[InitDB] Schema created successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to execute schema: {e}")
        sys.exit(1)

    # Verify tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [r[0] for r in cur.fetchall()]
    print(f"\n[InitDB] Verification: Found {len(tables)} tables in 'public' schema:")
    for t in tables:
        cur.execute(f'SELECT COUNT(*) FROM "{t}";')
        cnt = cur.fetchone()[0]
        print(f"  [OK] {t:<15} ({cnt} rows)")

    cur.close()
    conn.close()
    print("\n[InitDB] Database is fully initialized and ready for CoPenny AI!")

if __name__ == "__main__":
    init_database()
