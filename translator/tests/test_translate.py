"""Tests for US-01: Translate text.

Both engines are replaced with mocks (see helpers.py), so tests run offline,
never hit the free APIs' rate limits, and can simulate failures on demand.
"""
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.exceptions import TranslationError
from translator.forms import TranslateForm
from translator.services import languages
from translator.services.engine import TranslationResult, translate_text

from .helpers import EngineMocksMixin


class LanguageServiceTests(SimpleTestCase):
    def test_common_languages_are_supported(self):
        for code in ("en", "hi", "mr", "fr", "zh-CN"):
            self.assertTrue(languages.is_supported(code), code)

    def test_unknown_code_is_not_supported(self):
        self.assertFalse(languages.is_supported("xx"))

    def test_names_are_title_case(self):
        self.assertEqual(languages.get_language_name("hi"), "Hindi")
        self.assertEqual(languages.get_language_name("auto"), "Auto-detect")

    def test_choices_are_sorted_by_name(self):
        names = [name for _, name in languages.language_choices()]
        self.assertEqual(names, sorted(names))
        self.assertGreater(len(names), 100)


class EngineTests(EngineMocksMixin, SimpleTestCase):
    def test_translate_returns_result(self):
        result = translate_text("  Hello  ", "hi")

        self.google.assert_called_once_with(source="auto", target="hi")
        self.google.return_value.translate.assert_called_once_with("Hello")  # text was stripped
        self.assertIsInstance(result, TranslationResult)
        self.assertEqual(result.source_text, "Hello")
        self.assertEqual(result.translated_text, "नमस्ते")
        self.assertEqual(result.target_lang, "hi")
        self.assertEqual(result.engine, "google")

    def test_empty_text_is_rejected_without_calling_api(self):
        with self.assertRaises(TranslationError):
            translate_text("   ", "hi")
        self.google.assert_not_called()


class TranslateFormTests(SimpleTestCase):
    def form(self, **overrides):
        data = {"text": "Hello", "source_lang": "auto", "target_lang": "hi", **overrides}
        return TranslateForm(data=data)

    def test_valid_form(self):
        self.assertTrue(self.form().is_valid())

    def test_empty_text_is_invalid(self):
        form = self.form(text="   ")
        self.assertFalse(form.is_valid())
        self.assertIn("Please enter some text to translate.", form.errors["text"])

    def test_text_over_5000_chars_is_invalid(self):
        self.assertFalse(self.form(text="a" * 5001).is_valid())

    def test_unsupported_language_is_invalid(self):
        self.assertFalse(self.form(target_lang="xx").is_valid())

    def test_auto_is_not_a_valid_target(self):
        self.assertFalse(self.form(target_lang="auto").is_valid())


class TranslateViewTests(EngineMocksMixin, TestCase):
    url = reverse("translator:home")

    def test_get_shows_full_language_list_with_defaults(self):
        response = self.client.get(self.url)
        self.assertContains(response, '<option value="mr">Marathi</option>', html=True)
        self.assertContains(response, '<option value="hi" selected>Hindi</option>', html=True)
        self.assertContains(response, '<option value="auto" selected>Auto-detect</option>', html=True)

    def test_post_shows_translation_and_keeps_input(self):
        response = self.client.post(self.url, {"text": "Hello", "source_lang": "auto", "target_lang": "hi"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "नमस्ते")
        self.assertContains(response, "Translated to Hindi")
        # input still filled (Django writes a newline after <textarea>, which browsers ignore)
        self.assertContains(response, ">\nHello</textarea>")

    def test_post_empty_text_shows_form_error(self):
        response = self.client.post(self.url, {"text": "", "source_lang": "auto", "target_lang": "hi"})
        self.assertContains(response, "Please enter some text to translate.")
