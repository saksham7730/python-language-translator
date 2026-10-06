"""Tests for scripts/db_raw_sql.py using a throw-away in-memory SQLite database."""
import importlib.util
import sqlite3
from pathlib import Path

from django.test import SimpleTestCase

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "db_raw_sql.py"
spec = importlib.util.spec_from_file_location("db_raw_sql", SCRIPT)
db_raw_sql = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_raw_sql)


class RawSqlTests(SimpleTestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""CREATE TABLE translator_translation (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_text TEXT, translated_text TEXT,
            source_lang TEXT, target_lang TEXT, was_auto_detected BOOL, char_count INT,
            engine TEXT, origin TEXT, created_at DATETIME)""")
        rows = [("a", "x", "en", "hi", 1, 10, "google", "web", "2026-10-01 10:00:00"),
                ("b", "y", "en", "mr", 0, 20, "google", "web", "2026-10-01 12:00:00"),
                ("c", "z", "fr", "hi", 1, 30, "mymemory", "cli", "2026-10-02 09:00:00")]
        self.conn.executemany("INSERT INTO translator_translation (source_text, translated_text, source_lang, "
                              "target_lang, was_auto_detected, char_count, engine, origin, created_at) "
                              "VALUES (?,?,?,?,?,?,?,?,?)", rows)

    def tearDown(self):
        self.conn.close()

    def test_summary_groups_by_day(self):
        db_raw_sql.create_summary_table(self.conn)
        db_raw_sql.rebuild_summary(self.conn)
        self.assertEqual(db_raw_sql.fetch_summary(self.conn),
                         [("2026-10-02", 1, 30.0, 1), ("2026-10-01", 2, 15.0, 2)])

    def test_rebuild_twice_does_not_duplicate(self):
        db_raw_sql.create_summary_table(self.conn)
        db_raw_sql.rebuild_summary(self.conn)
        db_raw_sql.rebuild_summary(self.conn)
        self.assertEqual(len(db_raw_sql.fetch_summary(self.conn)), 2)

    def test_parameterised_query(self):
        db_raw_sql.create_summary_table(self.conn)
        db_raw_sql.rebuild_summary(self.conn)
        self.assertEqual(db_raw_sql.busy_days(self.conn, "?", 2), [("2026-10-01", 2)])

    def test_seed_inserts_rows(self):
        self.assertEqual(db_raw_sql.seed(self.conn, "?", 25), 25)
        count = self.conn.execute("SELECT COUNT(*) FROM translator_translation").fetchone()[0]
        self.assertEqual(count, 28)

    def test_drop(self):
        db_raw_sql.create_summary_table(self.conn)
        db_raw_sql.drop_summary_table(self.conn)
        tables = [r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertNotIn("daily_summary", tables)
