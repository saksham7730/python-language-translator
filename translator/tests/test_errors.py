"""Tests for US-07: Friendly error handling and the backup engine."""
import time
from unittest.mock import patch

import requests
from deep_translator.exceptions import TooManyRequests
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.exceptions import (
    NetworkError,
    RateLimitError,
    SameLanguageError,
    ServiceError,
    ServiceTimeoutError,
    TranslationError,
    UnsupportedLanguageError,
)
from translator.forms import TranslateForm
from translator.services.engine import translate_text
from translator.services.languages import mymemory_code

from .helpers import EngineMocksMixin

ENGLISH = "Good morning, how are you today?"   # long enough to be detected reliably as English


class ExceptionTests(SimpleTestCase):
    def test_every_error_has_a_friendly_default_message(self):
        for cls in (NetworkError, RateLimitError, SameLanguageError, ServiceError,
                    ServiceTimeoutError, UnsupportedLanguageError):
            self.assertTrue(issubclass(cls, TranslationError))
            self.assertTrue(str(cls()), cls.__name__)

    def test_custom_message_overrides_default(self):
        self.assertEqual(str(ServiceError("custom")), "custom")


class MyMemoryCodeTests(SimpleTestCase):
    def test_google_codes_map_to_mymemory_locales(self):
        self.assertEqual(mymemory_code("hi"), "hi-IN")
        self.assertEqual(mymemory_code("en"), "en-GB")
        self.assertEqual(mymemory_code("iw"), "he-IL")     # Google's old code for Hebrew
        self.assertEqual(mymemory_code("zh-CN"), "zh-CN")

    def test_unknown_language_returns_none(self):
        self.assertIsNone(mymemory_code("co"))  # Corsican: Google only


class ValidationErrorTests(EngineMocksMixin, SimpleTestCase):
    def test_same_source_and_target(self):
        with self.assertRaises(SameLanguageError):
            translate_text("Hello", "en", source_lang="en")
        self.google.assert_not_called()

    def test_detected_language_equals_target(self):
        with self.assertRaisesMessage(SameLanguageError, "already in Hindi"):
            translate_text("नमस्ते, आप कैसे हैं?", "hi")

    def test_unsupported_language(self):
        with self.assertRaises(UnsupportedLanguageError):
            translate_text("Hello", "xx")


class FallbackTests(EngineMocksMixin, SimpleTestCase):
    def test_rate_limited_google_falls_back_to_mymemory(self):
        self.google.return_value.translate.side_effect = TooManyRequests()

        with self.assertLogs("translator", level="WARNING"):
            result = translate_text(ENGLISH, "hi")

        self.assertEqual(result.engine, "mymemory")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.translated_text, "नमस्ते (backup)")
        self.mymemory.assert_called_once_with(source="en-GB", target="hi-IN")

    def test_google_is_skipped_during_cooldown(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", level="WARNING"):
            translate_text(ENGLISH, "hi")
            translate_text(ENGLISH, "mr")
        self.assertEqual(self.google.return_value.translate.call_count, 1)  # not retried for 60 s
        self.assertEqual(self.mymemory.return_value.translate.call_count, 2)

    def test_both_engines_offline_gives_network_error(self):
        self.google.return_value.translate.side_effect = requests.exceptions.ConnectionError()
        self.mymemory.return_value.translate.side_effect = requests.exceptions.ConnectionError()
        with self.assertLogs("translator", level="ERROR"), self.assertRaises(NetworkError):
            translate_text(ENGLISH, "hi")

    def test_unknown_library_error_gives_service_error(self):
        self.google.return_value.translate.side_effect = RuntimeError("boom")
        self.mymemory.return_value.translate.side_effect = RuntimeError("boom")
        with self.assertLogs("translator", level="ERROR"), self.assertRaises(ServiceError):
            translate_text(ENGLISH, "hi")

    def test_mymemory_quota_warning_is_a_rate_limit(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        self.mymemory.return_value.translate.return_value = "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS"
        with self.assertLogs("translator", level="ERROR"), self.assertRaises(RateLimitError):
            translate_text(ENGLISH, "hi")

    def test_long_text_skips_mymemory(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", level="ERROR"), self.assertRaises(RateLimitError):
            translate_text("Hello world. " * 50, "hi")   # 650 characters > MyMemory's limit
        self.mymemory.assert_not_called()

    def test_mymemory_skipped_when_language_unknown(self):
        # No letters -> nothing detected -> MyMemory has no source language to use
        self.google.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", level="ERROR"), self.assertRaises(RateLimitError):
            translate_text("12345", "hi")
        self.mymemory.assert_not_called()

    @patch("translator.services.engine.TIMEOUT_SECONDS", 0.05)
    def test_slow_engine_times_out(self):
        self.google.return_value.translate.side_effect = lambda text: time.sleep(0.5)
        self.mymemory.return_value.translate.side_effect = lambda text: time.sleep(0.5)
        with self.assertLogs("translator", level="ERROR"), self.assertRaises(ServiceTimeoutError):
            translate_text(ENGLISH, "hi")


class SameLanguageFormTests(SimpleTestCase):
    def test_form_rejects_same_languages(self):
        form = TranslateForm(data={"text": "Hello", "source_lang": "en", "target_lang": "en"})
        self.assertFalse(form.is_valid())
        self.assertIn("same", form.non_field_errors()[0])


class ErrorViewTests(EngineMocksMixin, TestCase):
    url = reverse("translator:home")

    def post(self, text=ENGLISH, source="auto", target="hi"):
        return self.client.post(self.url, {"text": text, "source_lang": source, "target_lang": target}, follow=True)

    def test_fallback_is_shown_to_user(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", level="WARNING"):
            response = self.post()
        self.assertContains(response, "नमस्ते (backup)")
        self.assertContains(response, "via MyMemory")
        self.assertContains(response, 'id="fallback-note"')

    def test_rate_limit_message_and_no_traceback(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        self.mymemory.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", level="ERROR"):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "too many requests")
        self.assertNotContains(response, "Traceback")

    def test_same_language_shows_form_error(self):
        response = self.post(text="Hello", source="en", target="en")
        self.assertContains(response, "source and target languages are the same")
        self.google.assert_not_called()
