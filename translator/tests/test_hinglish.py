"""Tests for bug #17: romanized Hindi (Hinglish) was detected as Swahili,
and for the PRIMARY_ENGINE setting."""
import os
from unittest.mock import patch

from deep_translator.exceptions import TooManyRequests
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from translator.services.detection import detect_language, detect_romanized_hindi
from translator.services.engine import primary_engine, translate_text

from .helpers import EngineMocksMixin


class RomanizedHindiDetectionTests(SimpleTestCase):
    def test_the_reported_bug(self):
        detection = detect_language("ye kya horha hai?")
        self.assertEqual(detection.code, "hi")
        self.assertTrue(detection.romanized)
        self.assertTrue(detection.reliable)
        self.assertEqual(detection.name, "Hindi (Roman script)")

    def test_more_hinglish_sentences(self):
        for text in ("aap kaise ho?", "mujhe nahi pata", "kal milte hai bhai", "tum kahan ho yaar"):
            with self.subTest(text=text):
                self.assertTrue(detect_language(text).romanized)

    def test_english_is_not_hinglish(self):
        for text in ("Good morning, how are you today?", "I love programming in Python",
                     "Ho ho ho, merry Christmas"):  # "ho" repeated is only ONE distinct word
            with self.subTest(text=text):
                self.assertIsNone(detect_romanized_hindi(text))
        self.assertEqual(detect_language("Good morning, how are you today?").code, "en")

    def test_real_swahili_is_still_swahili(self):
        detection = detect_language("Habari yako rafiki yangu, unaendeleaje leo asubuhi?")
        self.assertEqual(detection.code, "sw")
        self.assertFalse(detection.romanized)

    def test_devanagari_hindi_uses_langdetect(self):
        detection = detect_language("नमस्ते, आप कैसे हैं?")
        self.assertEqual(detection.code, "hi")
        self.assertFalse(detection.romanized)


class RomanizedHindiEngineTests(EngineMocksMixin, SimpleTestCase):
    def test_google_gets_auto_for_hinglish(self):
        self.google.return_value.translate.return_value = "What is happening?"
        result = translate_text("ye kya horha hai?", "en")

        self.google.assert_called_once_with(source="auto", target="en")
        self.assertEqual(result.source_lang, "hi")       # stored as Hindi for history/stats
        self.assertEqual(result.translated_text, "What is happening?")

    def test_mymemory_gets_hindi_not_swahili(self):
        self.google.return_value.translate.side_effect = TooManyRequests()
        with self.assertLogs("translator", level="WARNING"):
            result = translate_text("ye kya horha hai?", "en")
        self.mymemory.assert_called_once_with(source="hi-IN", target="en-GB")
        self.assertTrue(result.used_fallback)

    def test_hinglish_to_hindi_is_allowed(self):
        # Converting Roman script to Devanagari is a real request, not "same language"
        self.google.return_value.translate.return_value = "ये क्या हो रहा है?"
        result = translate_text("ye kya horha hai?", "hi")
        self.assertEqual(result.translated_text, "ये क्या हो रहा है?")


class PrimaryEngineTests(EngineMocksMixin, SimpleTestCase):
    def test_default_is_google(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRIMARY_ENGINE", None)
            self.assertEqual(primary_engine(), "google")

    def test_invalid_value_falls_back_to_google(self):
        with patch.dict(os.environ, {"PRIMARY_ENGINE": "bing"}):
            self.assertEqual(primary_engine(), "google")

    def test_mymemory_first_skips_google(self):
        with patch.dict(os.environ, {"PRIMARY_ENGINE": "mymemory"}):
            result = translate_text("Good morning, how are you today?", "hi")
        self.assertEqual(result.engine, "mymemory")
        self.assertFalse(result.used_fallback)   # it was the first choice, not a backup
        self.google.assert_not_called()

    def test_google_is_backup_when_mymemory_first(self):
        self.mymemory.return_value.translate.side_effect = TooManyRequests()
        with patch.dict(os.environ, {"PRIMARY_ENGINE": "mymemory"}), self.assertLogs("translator", "WARNING"):
            result = translate_text("Good morning, how are you today?", "hi")
        self.assertEqual(result.engine, "google")
        self.assertTrue(result.used_fallback)


class HinglishViewTests(EngineMocksMixin, TestCase):
    def test_page_shows_roman_script_hindi(self):
        self.google.return_value.translate.return_value = "What is happening?"
        response = self.client.post(reverse("translator:home"),
                                    {"text": "ye kya horha hai?", "source_lang": "auto", "target_lang": "en"})
        self.assertContains(response, "Detected: Hindi (Roman script)")
        self.assertContains(response, "What is happening?")
