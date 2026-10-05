"""Supported languages, built from deep-translator's Google language table.

deep-translator gives us {"english": "en", "hindi": "hi", ...}. We flip it to
{code: "Display Name"} because the rest of the app works with codes
("en", "hi") and only shows names to the user.
"""
from functools import lru_cache

from deep_translator import GoogleTranslator

AUTO = "auto"  # special source value meaning "detect the language for me"


@lru_cache(maxsize=1)
def get_languages():
    """Return {code: display name} for every supported language.

    The table ships with the library (no internet needed). lru_cache means it is
    built once and reused, instead of being rebuilt on every request.
    """
    name_to_code = GoogleTranslator().get_supported_languages(as_dict=True)
    # Dict comprehension: swap key/value and tidy the name ("chinese (simplified)" -> "Chinese (Simplified)")
    return {code: name.title() for name, code in name_to_code.items()}


def get_language_name(code):
    """'hi' -> 'Hindi'. Unknown codes are returned unchanged."""
    if code == AUTO:
        return "Auto-detect"
    return get_languages().get(code, code)


def supported_codes():
    """A set of all valid codes; set lookups ('hi' in codes) are O(1)."""
    return set(get_languages())


def is_supported(code):
    return code in supported_codes()


def language_choices():
    """List of (code, name) tuples sorted by name, ready for a <select> dropdown."""
    return sorted(get_languages().items(), key=lambda item: item[1])
