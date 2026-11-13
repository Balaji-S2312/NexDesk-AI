"""
Safe SQLite to PostgreSQL data migration utility for NexDesk AI.
Preserves existing SQLite database, reads schema via SQLAlchemy reflection,
and transfers records row-by-row into target PostgreSQL database.
"""
import os
import sys
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker

def migrate(sqlite_url: str, postgres_url: str):
    print("=" * 60)
    print("NexDesk AI — Production SQLite to PostgreSQL Data Migrator")
    print("=" * 60)

    if postgres_url.startswith("postgres://"):
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)

    print(f"Source: {sqlite_url}")
    print(f"Target: {postgres_url.split('@')[-1] if '@' in postgres_url else 'PostgreSQL'}")

    # Connect to source and target
    src_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    dst_engine = create_engine(postgres_url, pool_pre_ping=True)

    src_meta = MetaData()
    src_meta.reflect(bind=src_engine)

    # Order of tables for foreign key dependency resolution
    table_order = [
        "users",
        "email_verifications",
        "knowledge_documents",
        "knowledge_chunks",
        "sla_policies",
        "assignment_groups",
        "tickets",
        "ticket_comments",
        "ticket_audit_logs",
        "email_delivery_logs",
        "in_app_notifications",
    ]

    # First, import backend app models to create all tables in Postgres if not existing
    from app.database.session import Base
    import app.models  # load all models
    Base.metadata.create_all(bind=dst_engine)
    print("Ensured all tables and constraints exist on target PostgreSQL.")

    dst_conn = dst_engine.connect()
    src_conn = src_engine.connect()

    trans = dst_conn.begin()
    try:
        for tname in table_order:
            if tname not in src_meta.tables:
                continue
            table = src_meta.tables[tname]
            rows = src_conn.execute(select(table)).fetchall()
            print(f"Migrating table '{tname}': {len(rows)} records found...")
            if not rows:
                continue

            columns = [c.name for c in table.columns]
            insert_data = [dict(zip(columns, row)) for row in rows]

            dst_table = Table(tname, MetaData(), autoload_with=dst_engine)
            dst_conn.execute(dst_table.insert(), insert_data)
            print(f"  Successfully inserted {len(rows)} records into '{tname}'.")

        trans.commit()
        print("Migration committed successfully!")
    except Exception as e:
        trans.rollback()
        print(f"Error during migration: {e}", file=sys.stderr)
        raise
    finally:
        src_conn.close()
        dst_conn.close()

if __name__ == "__main__":
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else "sqlite:///../nexdesk.db"
    pg_url = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DATABASE_URL")
    if not pg_url or "sqlite" in pg_url:
        print("Usage: python migrate_sqlite_to_postgres.py [sqlite_url] [postgres_url]")
        print("Please provide a valid PostgreSQL connection string in DATABASE_URL.")
        sys.exit(1)
    migrate(sqlite_path, pg_url)
