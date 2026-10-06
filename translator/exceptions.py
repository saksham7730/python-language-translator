"""Custom exceptions for the translator.

Every class has a friendly default message that is safe to show to the user.
Views and the CLI only ever catch TranslationError (the base class), so a new
error type can be added without changing them.

    TranslationError
    ├── EmptyTextError
    ├── SameLanguageError
    ├── UnsupportedLanguageError
    ├── NetworkError
    ├── RateLimitError
    └── ServiceError
        └── ServiceTimeoutError
"""


class TranslationError(Exception):
    """Base class for every translation problem we report to the user."""

    default_message = "Sorry, the translation failed. Please try again."

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


class EmptyTextError(TranslationError):
    default_message = "Please enter some text to translate."


class SameLanguageError(TranslationError):
    default_message = "The source and target languages are the same. Choose a different target language."


class UnsupportedLanguageError(TranslationError):
    default_message = "That language isn't supported. Please choose one from the list."


class NetworkError(TranslationError):
    default_message = "No internet connection. Check your connection and try again."


class RateLimitError(TranslationError):
    default_message = (
        "The translation service is busy (too many requests). "
        "Please wait a minute and try again."
    )


class ServiceError(TranslationError):
    default_message = "The translation service had a problem. Please try again in a moment."


class ServiceTimeoutError(ServiceError):
    default_message = "The translation service took too long to respond. Please try again."
