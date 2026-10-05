"""Smoke tests for the project skeleton and home page layout (issue #13)."""
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def setUp(self):
        self.response = self.client.get(reverse("translator:home"))

    def test_home_page_loads(self):
        self.assertEqual(self.response.status_code, 200)

    def test_home_uses_base_template(self):
        self.assertTemplateUsed(self.response, "translator/home.html")
        self.assertTemplateUsed(self.response, "translator/base.html")

    def test_translator_card_is_shown(self):
        self.assertContains(self.response, 'id="translate-form"')
        self.assertContains(self.response, "Auto-detect")

    def test_stat_tiles_are_shown(self):
        self.assertContains(self.response, "Total translations")

    def test_theme_toggle_is_shown(self):
        self.assertContains(self.response, 'id="theme-toggle"')
