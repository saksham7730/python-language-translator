"""Tests for US-02: Auto-detect source language.

langdetect runs offline, so detection is tested for real; only Google is mocked.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.services.detection import detect_language
from translator.services.engine import translate_text

ENGINE_TRANSLATOR = "translator.services.engine.GoogleTranslator"


class DetectLanguageTests(SimpleTestCase):
    def test_detects_french_sentence(self):
        detection = detect_language("Bonjour, comment allez-vous aujourd'hui ?")
        self.assertEqual(detection.code, "fr")
        self.assertEqual(detection.name, "French")
        self.assertTrue(detection.reliable)
        self.assertGreaterEqual(detection.percent, 90)

    def test_short_non_latin_text_is_reliable(self):
        detection = detect_language("नमस्ते")
        self.assertEqual(detection.code, "hi")
        self.assertTrue(detection.reliable)

    def test_marathi(self):
        self.assertEqual(detect_language("तुम्ही कसे आहात? मी बरा आहे.").code, "mr")

    def test_codes_are_mapped_to_google_codes(self):
        self.assertEqual(detect_language("你好，你好吗？").code, "zh-CN")
        self.assertEqual(detect_language("שלום, מה שלומך?").code, "iw")  # Google's code for Hebrew

    def test_short_latin_text_is_not_reliable(self):
        # langdetect claims 100% that "Hi" is Dutch, so length matters too
        detection = detect_language("Hi")
        self.assertFalse(detection.reliable)

    def test_text_without_letters_returns_none(self):
        self.assertIsNone(detect_language("12345"))
        self.assertIsNone(detect_language("😀👍"))


class EngineDetectionTests(SimpleTestCase):
    @patch(ENGINE_TRANSLATOR)
    def test_reliable_detection_is_used_as_source(self, mock_cls):
        mock_cls.return_value.translate.return_value = "Hello, how are you today?"
        result = translate_text("Bonjour, comment allez-vous aujourd'hui ?", "en")

        mock_cls.assert_called_once_with(source="fr", target="en")
        self.assertEqual(result.source_lang, "fr")
        self.assertTrue(result.was_auto_detected)

    @patch(ENGINE_TRANSLATOR)
    def test_unreliable_detection_falls_back_to_google_auto(self, mock_cls):
        mock_cls.return_value.translate.return_value = "नमस्ते"
        result = translate_text("Hi", "hi")

        mock_cls.assert_called_once_with(source="auto", target="hi")
        self.assertEqual(result.source_lang, "auto")
        self.assertFalse(result.detection.reliable)

    @patch("translator.services.engine.detect_language")
    @patch(ENGINE_TRANSLATOR)
    def test_no_detection_when_source_is_chosen(self, mock_cls, mock_detect):
        mock_cls.return_value.translate.return_value = "Hola"
        result = translate_text("Hello", "es", source_lang="en")

        mock_detect.assert_not_called()
        self.assertFalse(result.was_auto_detected)


class DetectionViewTests(TestCase):
    url = reverse("translator:home")

    def post(self, text, source="auto"):
        return self.client.post(self.url, {"text": text, "source_lang": source, "target_lang": "hi"})

    @patch(ENGINE_TRANSLATOR)
    def test_shows_detected_language(self, mock_cls):
        mock_cls.return_value.translate.return_value = "नमस्ते"
        response = self.post("Bonjour, comment allez-vous aujourd'hui ?")
        self.assertContains(response, "Detected: French")

    @patch(ENGINE_TRANSLATOR)
    def test_short_text_shows_fallback_note(self, mock_cls):
        mock_cls.return_value.translate.return_value = "नमस्ते"
        response = self.post("Hi")
        self.assertContains(response, "too short to detect reliably")
        self.assertNotContains(response, "Detected:")

    @patch(ENGINE_TRANSLATOR)
    def test_no_detection_shown_when_source_chosen(self, mock_cls):
        mock_cls.return_value.translate.return_value = "नमस्ते"
        response = self.post("Hello there", source="en")
        self.assertNotContains(response, 'id="detected-lang"')
