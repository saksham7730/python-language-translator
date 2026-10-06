"""Source-language detection with langdetect (offline, no API key).

Why not just let Google auto-detect? deep-translator's GoogleTranslator translates
with source="auto" but does not tell us WHICH language it detected. We need the
actual language to show it to the user and to store it in the history/stats.
"""
import re
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
    romanized: bool = False  # True for Hindi typed in English letters ("Hinglish")
    detector: str = "langdetect"  # who detected it: "langdetect", "rules" or a translation engine

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


# --- Romanized Hindi ("Hinglish") ------------------------------------------
# langdetect only learned Hindi in Devanagari script, so "ye kya ho raha hai" looks
# like Swahili to it. This small rule-based check runs first and catches the common case.
# Words that are also common English words ("the", "me", "is", "to") are left out on purpose.
HINGLISH_WORDS = {
    "hai", "hain", "kya", "kyu", "kyun", "kyon", "nahi", "nahin", "nhi", "mein", "mai", "mujhe",
    "mera", "meri", "mere", "tum", "tumhe", "tumhara", "aap", "aapka", "aapki", "apna", "hum",
    "humein", "hamara", "ye", "yeh", "wo", "woh", "vo", "kaise", "kaisa", "kaisi", "kab", "kahan",
    "kidhar", "kaun", "kitna", "kitne", "raha", "rahi", "rahe", "rha", "rhi", "rhe", "horha",
    "hora", "hoga", "hogi", "tha", "thi", "ho", "hu", "hoon", "hun", "karo", "karna", "kar",
    "kiya", "gaya", "gayi", "aaya", "jao", "jana", "chalo", "accha", "acha", "achha", "theek",
    "thik", "bhai", "yaar", "abhi", "phir", "bahut", "bohot", "bhi", "sab", "kuch", "koi",
    "aur", "lekin", "haan", "ji", "matlab", "pata", "dekho", "bolo", "batao", "khana", "ghar",
    "aaj", "subah", "raat", "kal", "kaha", "suno", "chahiye", "sakta", "sakti",
}
MIN_HINGLISH_WORDS = 2    # at least 2 DIFFERENT Hinglish words...
MIN_HINGLISH_SHARE = 0.4  # ...making up at least 40% of all the words


def detect_romanized_hindi(text):
    """Return a Detection for Hindi in Roman script, or None if the text doesn't look like it."""
    if _uses_non_latin_script(text):
        return None
    words = re.findall(r"[a-z]+", text.lower())          # split into lowercase words
    if not words:
        return None
    hits = [word for word in words if word in HINGLISH_WORDS]   # list comprehension + set lookup
    share = len(hits) / len(words)
    if len(set(hits)) >= MIN_HINGLISH_WORDS and share >= MIN_HINGLISH_SHARE:
        return Detection(code="hi", name="Hindi (Roman script)", confidence=share,
                         reliable=True, romanized=True, detector="rules")
    return None


def detect_language(text):
    """Detect the language of `text`. Returns a Detection, or None if nothing could be detected."""
    hinglish = detect_romanized_hindi(text)
    if hinglish:
        return hinglish

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
