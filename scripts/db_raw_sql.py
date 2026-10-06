"""Raw SQL with Python's DB-API: DDL and DML on the translator database.

The website uses Django's ORM. This script talks to the SAME database directly
with SQL, using sqlite3 (built into Python) or PyMySQL, to show DDL and DML:

    python scripts/db_raw_sql.py seed --count 30    INSERT sample rows (executemany)
    python scripts/db_raw_sql.py summary            CREATE TABLE + INSERT ... SELECT + SELECT
    python scripts/db_raw_sql.py top --min 2        parameterised SELECT ... WHERE
    python scripts/db_raw_sql.py drop               DROP TABLE

DDL (Data Definition Language): CREATE / DROP          - change the structure
DML (Data Manipulation Language): INSERT / SELECT / UPDATE / DELETE - change the data
"""
import argparse
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))        # so "translator_project" can be imported

TRANSLATIONS = "translator_translation"      # table Django created for the Translation model
SUMMARY = "daily_summary"                    # our own table, created with raw DDL below


def connect():
    """Open a DB-API connection using the same settings (.env) as Django.

    Returns (connection, placeholder): sqlite3 uses ? and PyMySQL uses %s for parameters.
    """
    from django.conf import settings
    db = settings.DATABASES["default"]
    if db["ENGINE"].endswith("sqlite3"):
        return sqlite3.connect(db["NAME"]), "?"
    import pymysql
    conn = pymysql.connect(host=db["HOST"], port=int(db["PORT"]), user=db["USER"],
                           password=db["PASSWORD"], database=db["NAME"], charset="utf8mb4")
    return conn, "%s"


def with_cursor(conn, sql, params=()):
    """Run one statement with a short-lived cursor."""
    cur = conn.cursor()
    cur.execute(sql, params)
    cur.close()


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

def create_summary_table(conn):
    """DDL: CREATE TABLE (IF NOT EXISTS makes it safe to run twice)."""
    with_cursor(conn, f"""
        CREATE TABLE IF NOT EXISTS {SUMMARY} (
            day          DATE PRIMARY KEY,
            total        INTEGER NOT NULL,
            avg_chars    REAL    NOT NULL,
            target_langs INTEGER NOT NULL
        )
    """)


def drop_summary_table(conn):
    """DDL: DROP TABLE."""
    with_cursor(conn, f"DROP TABLE IF EXISTS {SUMMARY}")


# ---------------------------------------------------------------------------
# DML
# ---------------------------------------------------------------------------

def rebuild_summary(conn):
    """DML: empty the table, then fill it with one row per day using INSERT ... SELECT + GROUP BY."""
    with_cursor(conn, f"DELETE FROM {SUMMARY}")
    with_cursor(conn, f"""
        INSERT INTO {SUMMARY} (day, total, avg_chars, target_langs)
        SELECT DATE(created_at), COUNT(*), AVG(char_count), COUNT(DISTINCT target_lang)
        FROM {TRANSLATIONS}
        GROUP BY DATE(created_at)
    """)
    conn.commit()   # make the changes permanent (end of the transaction)


def fetch_summary(conn):
    """DML: SELECT every summary row, newest day first. Returns a list of tuples."""
    cur = conn.cursor()
    cur.execute(f"SELECT day, total, avg_chars, target_langs FROM {SUMMARY} ORDER BY day DESC")
    rows = cur.fetchall()
    cur.close()
    return rows


def busy_days(conn, placeholder, min_total):
    """DML with a parameter. The value is passed separately, never pasted into the SQL
    string, which prevents SQL injection."""
    cur = conn.cursor()
    cur.execute(f"SELECT day, total FROM {SUMMARY} WHERE total >= {placeholder} ORDER BY total DESC",
                (min_total,))
    rows = cur.fetchall()
    cur.close()
    return rows


SAMPLE_PAIRS = [("en", "hi"), ("en", "mr"), ("hi", "en"), ("fr", "en"), ("en", "fr"), ("de", "en"), ("en", "ja")]
SAMPLE_TEXTS = ["Good morning", "How are you?", "Where is the station?", "Thank you very much",
                "I am learning Python", "See you tomorrow", "What is your name?", "The weather is nice today"]


def seed(conn, placeholder, count, days=14):
    """DML: INSERT many sample rows in one call with executemany()."""
    now = datetime.now(timezone.utc)
    rows = []
    for _ in range(count):
        source, target = random.choice(SAMPLE_PAIRS)
        text = random.choice(SAMPLE_TEXTS)
        created = now - timedelta(days=random.randint(0, days - 1), minutes=random.randint(0, 1440))
        rows.append((text, f"[{target}] {text}", source, target, random.random() < 0.6, len(text),
                     random.choice(["google", "google", "mymemory"]), random.choice(["web", "web", "cli"]),
                     created.strftime("%Y-%m-%d %H:%M:%S")))
    marks = ", ".join([placeholder] * 9)
    cur = conn.cursor()
    cur.executemany(
        f"INSERT INTO {TRANSLATIONS} (source_text, translated_text, source_lang, target_lang, "
        f"was_auto_detected, char_count, engine, origin, created_at) VALUES ({marks})",
        rows,
    )
    conn.commit()
    inserted = cur.rowcount
    cur.close()
    return inserted


# ---------------------------------------------------------------------------

def print_table(rows, headers):
    widths = [max([len(str(h))] + [len(str(r[i])) for r in rows]) for i, h in enumerate(headers)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Raw SQL demo on the translator database.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary", help="create and fill the daily_summary table, then show it")
    seed_p = sub.add_parser("seed", help="insert sample translations")
    seed_p.add_argument("--count", type=int, default=30)
    top_p = sub.add_parser("top", help="days with at least --min translations")
    top_p.add_argument("--min", type=int, default=2)
    sub.add_parser("drop", help="drop the daily_summary table")
    args = parser.parse_args(argv)

    # Load Django only to read the database settings from settings.py / .env
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "translator_project.settings")
    import django
    django.setup()

    conn, placeholder = connect()
    try:
        if args.command == "seed":
            print(f"Inserted {seed(conn, placeholder, args.count)} sample translations.")
        elif args.command == "summary":
            create_summary_table(conn)
            rebuild_summary(conn)
            print_table([(d, t, f"{a:.1f}", n) for d, t, a, n in fetch_summary(conn)],
                        ["day", "total", "avg_chars", "target_langs"])
        elif args.command == "top":
            create_summary_table(conn)
            rebuild_summary(conn)
            print_table(busy_days(conn, placeholder, args.min), ["day", "total"])
        elif args.command == "drop":
            drop_summary_table(conn)
            conn.commit()
            print(f"Dropped table {SUMMARY}.")
    finally:
        conn.close()   # always release the connection, even after an error


if __name__ == "__main__":
    main()
