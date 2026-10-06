"""Tests for the Gemini engine (issue: better translation and detection). HTTP calls are mocked."""
import json
import os
from unittest.mock import MagicMock, patch

from deep_translator.exceptions import TooManyRequests
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.exceptions import RateLimitError, ServiceError
from translator.services import gemini
from translator.services.engine import translate_text

from .helpers import EngineMocksMixin

POST = "translator.services.gemini.requests.post"


def fake_response(translation="What is happening?", lang="hi", romanized=True, status=200, text=None):
    """Build a fake HTTP response shaped like Gemini's generateContent reply."""
    response = MagicMock(status_code=status)
    reply = {"translation": translation, "detected_language": lang, "romanized": romanized}
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": json.dumps(reply)}]}}]}
    response.text = text if text is not None else json.dumps(reply)
    return response


class GeminiTestCase(EngineMocksMixin, SimpleTestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-test"})
        env.start()
        self.addCleanup(env.stop)


class CodeMappingTests(SimpleTestCase):
    def test_iso_codes_map_to_our_codes(self):
        self.assertEqual(gemini.to_google_code("he"), "iw")
        self.assertEqual(gemini.to_google_code("zh"), "zh-CN")
        self.assertEqual(gemini.to_google_code("hi-Latn"), "hi")
        self.assertEqual(gemini.to_google_code("mr"), "mr")
        self.assertIsNone(gemini.to_google_code("xx"))
        self.assertIsNone(gemini.to_google_code(""))


class GeminiClientTests(GeminiTestCase):
    @patch(POST)
    def test_request_shape(self, post):
        post.return_value = fake_response()
        gemini.translate("ye kya ho raha hai?", "auto", "en")
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertIn("models/gemini-test:generateContent", url)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key")       # key in a header, not the URL
        self.assertEqual(kwargs["json"]["contents"][0]["parts"][0]["text"], "ye kya ho raha hai?")
        self.assertEqual(kwargs["json"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("English", kwargs["json"]["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(kwargs["timeout"], gemini.REQUEST_TIMEOUT)

    @patch(POST)
    def test_reply_is_parsed(self, post):
        post.return_value = fake_response()
        reply = gemini.translate("ye kya ho raha hai?", "auto", "en")
        self.assertEqual(reply, gemini.GeminiReply("What is happening?", "hi", True))

    @patch(POST)
    def test_quota_exceeded(self, post):
        post.return_value = fake_response(status=429)
        with self.assertRaises(RateLimitError):
            gemini.translate("Hello", "en", "hi")

    @patch(POST)
    def test_bad_key(self, post):
        post.return_value = fake_response(status=400, text='{"error": {"message": "API key not valid"}}')
        with self.assertRaisesMessage(ServiceError, "GEMINI_API_KEY"):
            gemini.translate("Hello", "en", "hi")

    @patch(POST)
    def test_unknown_model(self, post):
        post.return_value = fake_response(status=404)
        with self.assertRaisesMessage(ServiceError, "GEMINI_MODEL"):
            gemini.translate("Hello", "en", "hi")

    @patch(POST)
    def test_unexpected_reply(self, post):
        post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"candidates": []}))
        with self.assertRaises(ServiceError):
            gemini.translate("Hello", "en", "hi")


class GeminiInEngineTests(GeminiTestCase):
    @patch(POST)
    def test_gemini_is_skipped_without_key(self, post):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            self.google.return_value.translate.side_effect = TooManyRequests()
            with self.assertLogs("translator", "WARNING"):
                result = translate_text("Good morning, how are you today?", "hi")
        post.assert_not_called()
        self.assertEqual(result.engine, "mymemory")

    @patch(POST)
    def test_gemini_is_the_backup_for_google(self, post):
        post.return_value = fake_response("सुप्रभात, आज आप कैसे हैं?", "en", False)
        self.google.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", "WARNING"):
            result = translate_text("Good morning, how are you today?", "hi")
        self.assertEqual(result.engine, "gemini")
        self.assertTrue(result.used_fallback)
        self.mymemory.assert_not_called()

    @patch(POST)
    def test_primary_engine_gemini_and_its_detection_wins(self, post):
        post.return_value = fake_response("What is happening?", "hi", True)
        with patch.dict(os.environ, {"PRIMARY_ENGINE": "gemini"}):
            result = translate_text("ye kya ho raha hai?", "en")
        self.google.assert_not_called()
        self.assertEqual(result.engine, "gemini")
        self.assertEqual(result.source_lang, "hi")
        self.assertEqual(result.detection.detector, "Gemini")
        self.assertEqual(result.detection.name, "Hindi (Roman script)")

    @patch(POST)
    def test_gemini_failure_falls_back_to_mymemory(self, post):
        post.return_value = fake_response(status=500)
        with patch.dict(os.environ, {"PRIMARY_ENGINE": "gemini"}):
            self.google.return_value.translate.side_effect = TooManyRequests()
            with self.assertLogs("translator", "WARNING"):
                result = translate_text("Good morning, how are you today?", "hi")
        self.assertEqual(result.engine, "mymemory")

    @patch(POST)
    def test_chosen_source_is_not_overridden(self, post):
        post.return_value = fake_response("Hola", "en", False)
        with patch.dict(os.environ, {"PRIMARY_ENGINE": "gemini"}):
            result = translate_text("Hello there", "es", source_lang="en")
        self.assertIsNone(result.detection)
        self.assertFalse(result.was_auto_detected)


class GeminiViewTests(EngineMocksMixin, TestCase):
    @patch(POST)
    def test_page_says_detected_by_gemini(self, post):
        post.return_value = fake_response("What is happening?", "hi", True)
        with patch.dict(os.environ, {"PRIMARY_ENGINE": "gemini", "GEMINI_API_KEY": "test-key"}):
            response = self.client.post(reverse("translator:home"),
                                        {"text": "ye kya ho raha hai?", "source_lang": "auto", "target_lang": "en"},
                                        follow=True)
        self.assertContains(response, "Detected: Hindi (Roman script)")
        self.assertContains(response, "(detected by Gemini)")
        self.assertContains(response, "via Gemini")
