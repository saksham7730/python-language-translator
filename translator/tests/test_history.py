"""Tests for US-03 (save history), US-04 (view), US-05 (search/filter), US-06 (delete)."""
from datetime import timedelta

from deep_translator.exceptions import TooManyRequests
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from translator.models import Translation

from .helpers import EngineMocksMixin


def make(text="Hello there", translated="नमस्ते", source="en", target="hi", days_ago=0, **extra):
    """Create a Translation row; days_ago moves created_at into the past."""
    t = Translation.objects.create(source_text=text, translated_text=translated, source_lang=source,
                                   target_lang=target, char_count=len(text), **extra)
    if days_ago:
        Translation.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
    return t


class SaveTranslationTests(EngineMocksMixin, TestCase):
    """US-03: every successful translation is saved."""
    url = reverse("translator:home")

    def post(self, text="Good morning, how are you today?", target="hi", **kwargs):
        return self.client.post(self.url, {"text": text, "source_lang": "auto", "target_lang": target}, **kwargs)

    def test_successful_translation_is_saved(self):
        self.post()
        t = Translation.objects.get()
        self.assertEqual(t.source_text, "Good morning, how are you today?")
        self.assertEqual(t.translated_text, "नमस्ते")
        self.assertEqual((t.source_lang, t.target_lang), ("en", "hi"))
        self.assertTrue(t.was_auto_detected)
        self.assertEqual(t.char_count, 32)
        self.assertEqual(t.engine, "google")
        self.assertEqual(t.origin, Translation.Origin.WEB)

    def test_post_redirects_then_shows_result_once(self):
        response = self.post()
        # fetch_redirect_response=False: otherwise assertRedirects opens the page and uses up the result
        self.assertRedirects(response, self.url, fetch_redirect_response=False)  # Post/Redirect/Get
        page = self.client.get(self.url)
        self.assertContains(page, "नमस्ते")
        self.assertContains(page, ">\nGood morning, how are you today?</textarea>")  # input refilled
        self.assertNotContains(self.client.get(self.url), "Translated to Hindi")    # shown only once

    def test_failed_translation_is_not_saved(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        self.mymemory.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", level="ERROR"):
            self.post()
        self.assertEqual(Translation.objects.count(), 0)

    def test_invalid_form_is_not_saved(self):
        self.post(text="")
        self.assertEqual(Translation.objects.count(), 0)

    def test_stat_tiles_show_real_numbers(self):
        make(source="en", target="hi")
        make(source="fr", target="hi")
        make(source="en", target="mr", days_ago=3)
        response = self.client.get(self.url)
        self.assertEqual(response.context["stats"], [("Total translations", 3), ("Languages used", 4), ("Today", 2)])


class SummaryTests(TestCase):
    def test_auto_is_not_counted_as_a_language(self):
        make(source="auto", target="hi")
        self.assertEqual(Translation.objects.summary()["languages"], 1)

    def test_empty_database(self):
        self.assertEqual(Translation.objects.summary(), {"total": 0, "languages": 0, "today": 0})


class HistoryListTests(TestCase):
    """US-04: view history, newest first, 10 per page."""
    url = reverse("translator:history")

    def test_empty_state(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'id="empty-history"')
        self.assertNotContains(response, "Clear all history")

    def test_newest_first(self):
        make(text="older one", days_ago=2)
        make(text="newer one")
        texts = [t.source_text for t in self.client.get(self.url).context["page_obj"]]
        self.assertEqual(texts, ["newer one", "older one"])

    def test_pagination_ten_per_page(self):
        for i in range(23):
            make(text=f"text {i}")
        first = self.client.get(self.url)
        self.assertEqual(len(first.context["page_obj"]), 10)
        self.assertEqual(first.context["page_obj"].paginator.num_pages, 3)
        self.assertEqual(len(self.client.get(self.url, {"page": 3}).context["page_obj"]), 3)

    def test_shows_language_names(self):
        make(source="en", target="mr")
        response = self.client.get(self.url)
        self.assertContains(response, "English")
        self.assertContains(response, "Marathi")

    def test_translate_again_link(self):
        make(text="Hello there", source="en", target="hi")
        response = self.client.get(self.url)
        self.assertContains(response, "?text=Hello%20there&amp;from=en&amp;to=hi")
        prefilled = self.client.get(reverse("translator:home"), {"text": "Hello there", "from": "en", "to": "hi"})
        self.assertEqual(prefilled.context["form"].initial["source_lang"], "en")


class HistoryFilterTests(TestCase):
    """US-05: search and filter."""
    url = reverse("translator:history")

    def setUp(self):
        make(text="Good morning", translated="सुप्रभात", source="en", target="hi")
        make(text="Bonjour mes amis", translated="Hello my friends", source="fr", target="en")
        make(text="Good night", translated="Bonne nuit", source="en", target="fr", days_ago=10)

    def texts(self, **params):
        return sorted(t.source_text for t in self.client.get(self.url, params).context["page_obj"])

    def test_search_is_case_insensitive_and_checks_both_texts(self):
        self.assertEqual(self.texts(q="GOOD"), ["Good morning", "Good night"])
        self.assertEqual(self.texts(q="friends"), ["Bonjour mes amis"])   # matches the translation

    def test_filter_by_languages(self):
        self.assertEqual(self.texts(source_lang="en"), ["Good morning", "Good night"])
        self.assertEqual(self.texts(source_lang="en", target_lang="fr"), ["Good night"])

    def test_filter_by_date_range(self):
        today = timezone.localdate()
        self.assertEqual(self.texts(date_from=(today - timedelta(days=1)).isoformat()),
                         ["Bonjour mes amis", "Good morning"])
        self.assertEqual(self.texts(date_to=(today - timedelta(days=5)).isoformat()), ["Good night"])

    def test_filters_combine(self):
        self.assertEqual(self.texts(q="good", target_lang="hi"), ["Good morning"])

    def test_no_matches_message(self):
        response = self.client.get(self.url, {"q": "zzz"})
        self.assertContains(response, 'id="no-matches"')

    def test_invalid_date_range_shows_error(self):
        response = self.client.get(self.url, {"date_from": "2026-10-10", "date_to": "2026-10-01"})
        self.assertContains(response, "must be on or before")

    def test_filters_kept_in_pagination_links(self):
        for i in range(12):
            make(text=f"good {i}")
        response = self.client.get(self.url, {"q": "good"})
        self.assertContains(response, "?q=good&amp;page=2")


class DeleteTests(TestCase):
    """US-06: delete one or all, only via POST, with confirmation."""

    def test_get_shows_confirmation_and_does_not_delete(self):
        t = make()
        response = self.client.get(reverse("translator:delete", args=[t.pk]))
        self.assertContains(response, "Delete this translation?")
        self.assertTrue(Translation.objects.filter(pk=t.pk).exists())

    def test_post_deletes_and_redirects(self):
        t = make()
        response = self.client.post(reverse("translator:delete", args=[t.pk]), follow=True)
        self.assertFalse(Translation.objects.filter(pk=t.pk).exists())
        self.assertContains(response, "Translation deleted.")

    def test_delete_returns_to_filtered_page(self):
        t = make()
        response = self.client.post(reverse("translator:delete", args=[t.pk]), {"next": "/history/?q=hello"})
        self.assertRedirects(response, "/history/?q=hello")

    def test_external_next_url_is_ignored(self):
        t = make()
        response = self.client.post(reverse("translator:delete", args=[t.pk]), {"next": "https://evil.example.com/"})
        self.assertRedirects(response, reverse("translator:history"))

    def test_missing_translation_is_404(self):
        self.assertEqual(self.client.post(reverse("translator:delete", args=[999])).status_code, 404)

    def test_clear_all_needs_confirmation(self):
        make(); make()
        self.assertContains(self.client.get(reverse("translator:clear")), "permanently deletes <strong>2</strong>")
        self.assertEqual(Translation.objects.count(), 2)
        response = self.client.post(reverse("translator:clear"), follow=True)
        self.assertEqual(Translation.objects.count(), 0)
        self.assertContains(response, "Deleted 2 translations.")
