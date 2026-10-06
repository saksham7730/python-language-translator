"""Source-language detection with langdetect (offline, no API key).

Why not just let Google auto-detect? deep-translator's GoogleTranslator translates
with source="auto" but does not tell us WHICH language it detected. We need the
actual language to show it to the user and to store it in the history/stats.
"""
from dataclasses import dataclass

from langdetect import DetectorFactory, LangDetectException, detect_langs

from .languages import get_language_name, is_supported

# langdetect is randomised internally; a fixed seed makes results repeatable
DetectorFactory.seed = 0

MIN_CONFIDENCE = 0.70   # tuned by testing: correct English sentences sometimes score only ~71%
MIN_LATIN_LETTERS = 12  # short Latin-script text is unreliable ("Hi" -> Dutch, "Ciao" -> Portuguese)

# langdetect and Google use different codes for a few languages
LANGDETECT_TO_GOOGLE = {"zh-cn": "zh-CN", "zh-tw": "zh-TW", "he": "iw"}


@dataclass(frozen=True)
class Detection:
    code: str          # Google-style code, e.g. "fr"
    name: str          # e.g. "French"
    confidence: float  # 0.0 - 1.0
    reliable: bool     # True -> safe to use as the source language

    @property
    def percent(self):
        """Confidence as a whole-number percentage for display, e.g. 0.9999 -> 100."""
        return round(self.confidence * 100)


def _letters(text):
    """Generator expression: yields only the alphabetic characters of the text."""
    return (ch for ch in text if ch.isalpha())


def _uses_non_latin_script(text):
    """True if any letter is outside the Latin alphabet (Devanagari, Chinese, Arabic, ...).

    Those scripts are distinctive, so even very short text is detected correctly.
    Latin letters (including accented ones like é, ü) end at code point U+024F.
    """
    return any(ord(ch) > 0x024F for ch in _letters(text))


def detect_language(text):
    """Detect the language of `text`. Returns a Detection, or None if nothing could be detected."""
    try:
        best = detect_langs(text)[0]  # results are sorted, most likely first
    except LangDetectException:
        # Raised for text with no letters at all: numbers, emoji, punctuation
        return None

    code = LANGDETECT_TO_GOOGLE.get(best.lang, best.lang)
    if not is_supported(code):
        return None

    long_enough = sum(1 for _ in _letters(text)) >= MIN_LATIN_LETTERS or _uses_non_latin_script(text)
    reliable = best.prob >= MIN_CONFIDENCE and long_enough

    return Detection(code=code, name=get_language_name(code), confidence=best.prob, reliable=reliable)
