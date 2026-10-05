"""Custom exceptions for the translator.

Views catch TranslationError and show its message to the user, so every
message raised here must be friendly and safe to display.
More specific subclasses (no internet, unsupported language, ...) are added in US-07.
"""


class TranslationError(Exception):
    """Base class for every translation problem we report to the user."""
