"""The translation engine: Google first, MyMemory as a backup.

Flow of translate_text():
  1. validate the input (empty text, supported languages)
  2. auto-detect the source language if needed (US-02)
  3. try each engine in order; if one fails, log it and try the next
  4. turn library/network errors into our own friendly exceptions

Nothing in this file imports Django, so the CLI (US-09) can reuse it.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass

import requests
from deep_translator import GoogleTranslator, MyMemoryTranslator
from deep_translator.exceptions import (
    InvalidSourceOrTargetLanguage,
    LanguageNotSupportedException,
    TooManyRequests,
)

from translator.exceptions import (
    EmptyTextError,
    NetworkError,
    RateLimitError,
    SameLanguageError,
    ServiceError,
    ServiceTimeoutError,
    TranslationError,
    UnsupportedLanguageError,
)

from .detection import Detection, detect_language
from .languages import AUTO, get_language_name, is_supported, mymemory_code

logger = logging.getLogger(__name__)

MAX_CHARS = 5000            # Google's limit per request; longer text is chunked in US-10
MYMEMORY_MAX_CHARS = 499    # MyMemory's free API accepts fewer than 500 characters
TIMEOUT_SECONDS = 10        # give up on an engine that hasn't answered by then
COOLDOWN_SECONDS = 60       # after "too many requests", skip that engine for a minute

ENGINE_NAMES = {"google": "Google", "mymemory": "MyMemory"}


@dataclass(frozen=True)
class TranslationResult:
    """Everything the caller needs to know about one translation (immutable record)."""
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

    @property
    def used_fallback(self):
        return self.engine != "google"

    @property
    def engine_name(self):
        return ENGINE_NAMES.get(self.engine, self.engine)


# ---------------------------------------------------------------------------
# Engines: each one is a plain function (text, source, target) -> translated text
# ---------------------------------------------------------------------------

def _google(text, source, target):
    return GoogleTranslator(source=source, target=target).translate(text)


def _mymemory(text, source, target):
    translated = MyMemoryTranslator(source=mymemory_code(source), target=mymemory_code(target)).translate(text)
    # When the free daily quota runs out, MyMemory still answers "200 OK" but puts a
    # warning where the translation should be, so we have to check the text itself.
    if translated and translated.upper().startswith("MYMEMORY WARNING"):
        raise RateLimitError()
    if translated and translated.upper().startswith(("INVALID", "PLEASE SELECT")):
        raise ServiceError()
    return translated


def _mymemory_can_handle(text, source, target):
    """MyMemory needs a real source language (no 'auto'), short text, and known codes."""
    return (
        source != AUTO
        and len(text) <= MYMEMORY_MAX_CHARS
        and mymemory_code(source) is not None
        and mymemory_code(target) is not None
    )


# ---------------------------------------------------------------------------
# Cool-down ("circuit breaker"): stop hammering an engine that said "too many requests"
# ---------------------------------------------------------------------------

_cooldown_until = {}  # engine name -> time.monotonic() value when it may be used again


def _in_cooldown(name):
    return time.monotonic() < _cooldown_until.get(name, 0)


def _start_cooldown(name):
    _cooldown_until[name] = time.monotonic() + COOLDOWN_SECONDS


def reset_cooldowns():
    """Forget all cool-downs (used by the tests)."""
    _cooldown_until.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# deep-translator calls the web APIs without a timeout, so a bad connection could make
# a request hang forever. We run the call in a worker thread and stop waiting after
# TIMEOUT_SECONDS. (The thread finishes in the background; the user isn't kept waiting.)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="translate")


def _run_with_timeout(func, *args):
    future = _executor.submit(func, *args)
    try:
        return future.result(timeout=TIMEOUT_SECONDS)
    except FutureTimeout as exc:
        raise ServiceTimeoutError() from exc


def _to_translation_error(exc):
    """Map any exception from an engine to one of our friendly TranslationError types."""
    if isinstance(exc, TranslationError):
        return exc
    if isinstance(exc, TooManyRequests):
        return RateLimitError()
    if isinstance(exc, (LanguageNotSupportedException, InvalidSourceOrTargetLanguage)):
        return UnsupportedLanguageError()
    if isinstance(exc, requests.exceptions.Timeout):          # check before ConnectionError:
        return ServiceTimeoutError()                          # ConnectTimeout is both
    if isinstance(exc, requests.exceptions.ConnectionError):
        return NetworkError()
    return ServiceError()


def _validate(text, source_lang, target_lang):
    if not text:
        raise EmptyTextError()
    if not is_supported(target_lang) or (source_lang != AUTO and not is_supported(source_lang)):
        raise UnsupportedLanguageError()


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def translate_text(text, target_lang, source_lang=AUTO):
    """Translate `text` into `target_lang`.

    Returns a TranslationResult. Raises a TranslationError subclass with a
    user-friendly message if the text can't be translated.
    """
    text = (text or "").strip()
    _validate(text, source_lang, target_lang)

    # Auto-detect (US-02): use the detected language if we're confident about it
    detection = None
    if source_lang == AUTO:
        detection = detect_language(text)
        if detection and detection.reliable:
            source_lang = detection.code

    if source_lang == target_lang:
        raise SameLanguageError(
            f"The text is already in {get_language_name(target_lang)}. Choose a different target language."
        )

    # The backup engine can't auto-detect, so give it langdetect's best guess
    backup_source = source_lang if source_lang != AUTO else (detection.code if detection else AUTO)

    # (name, function, source language to use) - tried in this order
    engines = [
        ("google", _google, source_lang),
        ("mymemory", _mymemory, backup_source),
    ]

    errors = []
    for name, engine, source in engines:
        if _in_cooldown(name):
            logger.info("Skipping %s: cooling down after too many requests", name)
            errors.append(RateLimitError())
            continue
        if name == "mymemory" and (not _mymemory_can_handle(text, source, target_lang) or source == target_lang):
            continue

        try:
            translated = _run_with_timeout(engine, text, source, target_lang)
            if not translated:
                raise ServiceError("The translator returned an empty result. Please try again.")
        except Exception as exc:  # noqa: BLE001 - any engine failure is turned into a friendly error
            error = _to_translation_error(exc)
            logger.warning("%s failed (%s -> %s): %r", name, source, target_lang, exc)
            if isinstance(error, RateLimitError):
                _start_cooldown(name)
            errors.append(error)
            continue

        if errors:
            logger.info("Translated with backup engine %s after: %s", name, errors)
        return TranslationResult(
            source_text=text,
            translated_text=translated,
            source_lang=source,
            target_lang=target_lang,
            engine=name,
            detection=detection,
        )

    # Every engine failed (or was skipped): report the first, most relevant problem
    logger.error("All translation engines failed (%s -> %s): %s", source_lang, target_lang, errors)
    raise errors[0] if errors else ServiceError()
