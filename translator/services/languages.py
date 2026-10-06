"""Supported languages, built from deep-translator's Google language table.

deep-translator gives us {"english": "en", "hindi": "hi", ...}. We flip it to
{code: "Display Name"} because the rest of the app works with codes
("en", "hi") and only shows names to the user.
"""
from functools import lru_cache

from deep_translator import GoogleTranslator
from deep_translator.constants import MY_MEMORY_LANGUAGES_TO_CODES

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


# --- Backup engine (MyMemory) language codes --------------------------------
# MyMemory uses locale codes ("hi-IN", "en-GB") instead of Google's ("hi", "en").
GOOGLE_TO_ISO = {"iw": "he", "jw": "jv", "no": "nb", "ku": "kmr"}  # old or differing codes


@lru_cache(maxsize=1)
def _mymemory_codes():
    """Return {google code: mymemory code} for every language both engines support."""
    by_name = MY_MEMORY_LANGUAGES_TO_CODES          # {"hindi": "hi-IN", ...}
    all_mm_codes = sorted(set(by_name.values()))

    def match(code, name):
        # 1) identical code, e.g. "zh-CN" -> "zh-CN"
        if code in all_mm_codes:
            return code
        # 2) same language name, e.g. "hindi" -> "hi-IN" (MyMemory writes names without brackets)
        for candidate in (name.lower(), name.lower().replace("(", "").replace(")", "")):
            if candidate in by_name:
                return by_name[candidate]
        # 3) same base code, e.g. "iw" -> "he" -> "he-IL"
        base = GOOGLE_TO_ISO.get(code, code).split("-")[0].lower()
        return next((mm for mm in all_mm_codes if mm.lower().split("-")[0] == base), None)

    pairs = {code: match(code, name) for code, name in get_languages().items()}
    return {code: mm for code, mm in pairs.items() if mm}  # drop languages MyMemory lacks


def mymemory_code(code):
    """'hi' -> 'hi-IN'. Returns None if MyMemory doesn't support the language."""
    return _mymemory_codes().get(code)
