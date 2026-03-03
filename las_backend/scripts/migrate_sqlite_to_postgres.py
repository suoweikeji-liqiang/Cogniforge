import argparse
import asyncio
import os
import sys

from sqlalchemy import delete, inspect, select
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base
import app.models.entities  # noqa: F401


def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy Cogniforge data from a SQLite database into PostgreSQL."
    )
    parser.add_argument(
        "--source-sqlite",
        required=True,
        help="Path to the source SQLite database file.",
    )
    parser.add_argument(
        "--target-url",
        required=True,
        help="Target PostgreSQL SQLAlchemy URL.",
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Delete existing target rows before importing.",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    source_url = f"sqlite+aiosqlite:///{args.source_sqlite}"
    source_engine = create_async_engine(source_url, echo=False)
    target_engine = create_async_engine(args.target_url, echo=False)

    try:
        async with source_engine.connect() as source_conn:
            source_tables = await source_conn.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )

            async with target_engine.begin() as target_conn:
                if args.truncate_target:
                    for table in reversed(Base.metadata.sorted_tables):
                        await target_conn.execute(delete(table))

                for table in Base.metadata.sorted_tables:
                    if table.name not in source_tables:
                        print(f"Skipping {table.name}: not present in source database")
                        continue

                    result = await source_conn.execute(select(table))
                    rows = [dict(row) for row in result.mappings().all()]
                    if rows:
                        await target_conn.execute(table.insert(), rows)
                    print(f"Migrated {table.name}: {len(rows)} rows")
    finally:
        await source_engine.dispose()
        await target_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
