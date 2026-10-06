"""Tests for US-08: statistics with Pandas, NumPy and Matplotlib."""
import base64
from datetime import date, datetime, timezone

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.models import Translation
from translator.services import analytics


def record(day, source="en", target="hi", chars=10, auto=False, hour=6):
    return {"created_at": datetime(2026, 10, day, hour, 0, tzinfo=timezone.utc), "source_lang": source,
            "target_lang": target, "char_count": chars, "engine": "google", "origin": "web",
            "was_auto_detected": auto}


RECORDS = [
    record(1, "en", "hi", 10, True), record(1, "en", "hi", 20, True), record(1, "en", "mr", 30),
    record(3, "fr", "en", 40, True), record(5, "en", "hi", 100), record(5, "auto", "fr", 50),
]


class AnalyticsTests(SimpleTestCase):
    def setUp(self):
        self.df = analytics.to_dataframe(RECORDS)

    def test_dataframe_has_names_and_pairs(self):
        self.assertEqual(self.df.loc[0, "pair"], "English → Hindi")
        self.assertEqual(self.df.loc[5, "source_name"], "Unknown")       # "auto" is shown as Unknown

    def test_dates_use_indian_time(self):
        late = analytics.to_dataframe([record(1, hour=20)])              # 20:00 UTC = 01:30 IST next day
        self.assertEqual(late.loc[0, "day"], date(2026, 10, 2))

    def test_top_pairs(self):
        self.assertEqual(analytics.top_pairs(self.df).iloc[0], 3)
        self.assertEqual(analytics.top_pairs(self.df).index[0], "English → Hindi")

    def test_daily_counts_include_zero_days(self):
        daily = analytics.daily_counts(self.df, days=5, today=date(2026, 10, 5))
        self.assertEqual(list(daily.values), [3, 0, 1, 0, 2])

    def test_target_share_adds_up_to_100(self):
        share = analytics.target_share(self.df, n=2)
        self.assertAlmostEqual(share.sum(), 100, places=0)
        self.assertIn("Other", share.index)

    def test_numpy_length_stats(self):
        stats = analytics.length_stats(self.df)     # lengths 10, 20, 30, 40, 100, 50
        self.assertEqual(stats["mean"], 41.7)
        self.assertEqual(stats["median"], 35.0)
        self.assertEqual(stats["max"], 100)
        self.assertEqual(stats["total_chars"], 250)
        self.assertEqual(stats["p90"], 75.0)

    def test_headline_numbers(self):
        h = analytics.headline_numbers(self.df)
        self.assertEqual(h["total"], 6)
        self.assertEqual(h["auto_pct"], 50.0)
        self.assertEqual(h["top_target"], "Hindi")
        self.assertEqual(h["busiest_day"], date(2026, 10, 1))

    def test_charts_are_png_for_both_themes(self):
        report = analytics.build_report(RECORDS, today=date(2026, 10, 5))
        self.assertTrue(report["enough_data"])
        for chart in report["charts"].values():
            self.assertEqual(set(chart), {"light", "dark"})
            self.assertTrue(base64.b64decode(chart["light"]).startswith(b"\x89PNG"))

    def test_not_enough_data(self):
        self.assertEqual(analytics.build_report([record(1)]), {"enough_data": False, "total": 1})
        self.assertFalse(analytics.build_report([])["enough_data"])


class StatsPageTests(TestCase):
    url = reverse("translator:stats")

    def test_empty_state(self):
        self.assertContains(self.client.get(self.url), 'id="not-enough-data"')

    def test_page_with_data(self):
        for text, target in [("Hello", "hi"), ("Good night", "hi"), ("Thanks", "mr")]:
            Translation.objects.create(source_text=text, translated_text="x", source_lang="en",
                                       target_lang=target, char_count=len(text))
        response = self.client.get(self.url)
        self.assertContains(response, "data:image/png;base64,")
        self.assertContains(response, 'id="length-stats"')
        self.assertContains(response, "English → Hindi")      # in the accessible data table
