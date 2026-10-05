"""App configuration: registers the 'translator' app with Django."""
from django.apps import AppConfig


class TranslatorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "translator"
    verbose_name = "Language Translator"
