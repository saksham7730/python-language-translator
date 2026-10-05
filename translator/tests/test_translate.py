"""Tests for US-01: Translate text.

The real GoogleTranslator is replaced with a mock (a fake object we control), so:
- tests run offline and fast,
- we never hit the free API's rate limits,
- we can simulate failures on demand.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.exceptions import TranslationError
from translator.forms import TranslateForm
from translator.services import languages
from translator.services.engine import TranslationResult, translate_text

ENGINE_TRANSLATOR = "translator.services.engine.GoogleTranslator"


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


class EngineTests(SimpleTestCase):
    @patch(ENGINE_TRANSLATOR)
    def test_translate_returns_result(self, mock_cls):
        mock_cls.return_value.translate.return_value = "नमस्ते"

        result = translate_text("  Hello  ", "hi")

        mock_cls.assert_called_once_with(source="auto", target="hi")
        mock_cls.return_value.translate.assert_called_once_with("Hello")  # text was stripped
        self.assertIsInstance(result, TranslationResult)
        self.assertEqual(result.source_text, "Hello")
        self.assertEqual(result.translated_text, "नमस्ते")
        self.assertEqual(result.target_lang, "hi")

    def test_empty_text_is_rejected_without_calling_api(self):
        with patch(ENGINE_TRANSLATOR) as mock_cls:
            with self.assertRaises(TranslationError):
                translate_text("   ", "hi")
            mock_cls.assert_not_called()

    @patch(ENGINE_TRANSLATOR)
    def test_library_errors_become_translation_error(self, mock_cls):
        mock_cls.return_value.translate.side_effect = ConnectionError("no internet")
        with self.assertLogs("translator", level="ERROR"), self.assertRaises(TranslationError):
            translate_text("Hello", "hi")

    @patch(ENGINE_TRANSLATOR)
    def test_empty_api_result_is_an_error(self, mock_cls):
        mock_cls.return_value.translate.return_value = ""
        with self.assertRaises(TranslationError):
            translate_text("Hello", "hi")


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


class TranslateViewTests(TestCase):
    url = reverse("translator:home")

    def test_get_shows_full_language_list_with_defaults(self):
        response = self.client.get(self.url)
        self.assertContains(response, '<option value="mr">Marathi</option>', html=True)
        self.assertContains(response, '<option value="hi" selected>Hindi</option>', html=True)
        self.assertContains(response, '<option value="auto" selected>Auto-detect</option>', html=True)

    @patch(ENGINE_TRANSLATOR)
    def test_post_shows_translation_and_keeps_input(self, mock_cls):
        mock_cls.return_value.translate.return_value = "नमस्ते"
        response = self.client.post(self.url, {"text": "Hello", "source_lang": "auto", "target_lang": "hi"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "नमस्ते")
        self.assertContains(response, "Translated to Hindi")
        # input still filled (Django writes a newline after <textarea>, which browsers ignore)
        self.assertContains(response, ">\nHello</textarea>")

    def test_post_empty_text_shows_form_error(self):
        response = self.client.post(self.url, {"text": "", "source_lang": "auto", "target_lang": "hi"})
        self.assertContains(response, "Please enter some text to translate.")

    @patch(ENGINE_TRANSLATOR)
    def test_api_failure_shows_friendly_message_not_traceback(self, mock_cls):
        mock_cls.return_value.translate.side_effect = RuntimeError("boom")
        with self.assertLogs("translator", level="ERROR"):
            response = self.client.post(self.url, {"text": "Hello", "source_lang": "auto", "target_lang": "hi"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sorry, the translation failed")
        self.assertNotContains(response, "boom")
