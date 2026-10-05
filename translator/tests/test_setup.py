"""Smoke tests for the project skeleton (issue #13)."""
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("translator:home"))
        self.assertEqual(response.status_code, 200)

    def test_home_uses_base_template(self):
        response = self.client.get(reverse("translator:home"))
        self.assertTemplateUsed(response, "translator/home.html")
        self.assertTemplateUsed(response, "translator/base.html")

    def test_home_shows_feature_cards(self):
        response = self.client.get(reverse("translator:home"))
        self.assertContains(response, "Auto-detect")
