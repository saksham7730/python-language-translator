"""The translation engine: a thin wrapper around deep-translator's GoogleTranslator.

Keeping the library call in one place means the rest of the app never talks to
deep-translator directly. If we ever switch library, only this file changes.
"""
import logging
from dataclasses import dataclass

from deep_translator import GoogleTranslator

from translator.exceptions import TranslationError

from .detection import Detection, detect_language
from .languages import AUTO

logger = logging.getLogger(__name__)

MAX_CHARS = 5000  # Google's limit per request; longer text is chunked in US-10


@dataclass(frozen=True)
class TranslationResult:
    """Everything the caller needs to know about one translation.

    A frozen dataclass is an immutable record: fields can't be changed by accident.
    """
    source_text: str
    translated_text: str
    source_lang: str      # the language actually used: a code, or "auto" if detection wasn't confident
    target_lang: str
    engine: str = "google"
    detection: Detection | None = None   # set when the user chose Auto-detect

    @property
    def was_auto_detected(self):
        """True if the user picked Auto-detect (stored in the history in US-03)."""
        return self.detection is not None or self.source_lang == AUTO


def translate_text(text, target_lang, source_lang=AUTO):
    """Translate `text` into `target_lang`. Raises TranslationError on any failure."""
    text = (text or "").strip()
    if not text:
        raise TranslationError("Please enter some text to translate.")

    # Auto-detect: if we are confident about the language, translate FROM that language.
    # If not (very short or ambiguous text), keep "auto" and let Google decide.
    detection = None
    if source_lang == AUTO:
        detection = detect_language(text)
        if detection and detection.reliable:
            source_lang = detection.code

    try:
        translated = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
    except Exception as exc:
        # Log the technical details for the developer, show a friendly message to the user.
        # US-07 replaces this catch-all with specific messages and a fallback engine.
        logger.exception("Translation failed (%s -> %s)", source_lang, target_lang)
        raise TranslationError(
            "Sorry, the translation failed. Check your internet connection and try again."
        ) from exc

    if not translated:
        raise TranslationError("The translator returned an empty result. Please try again.")

    return TranslationResult(
        source_text=text,
        translated_text=translated,
        source_lang=source_lang,
        target_lang=target_lang,
        detection=detection,
    )
