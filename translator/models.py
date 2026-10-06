"""Database models (the M in MVT).

One table, translator_translation, stores every successful translation.
Django creates it from this class with `python manage.py makemigrations` + `migrate`.
"""
from django.db import models
from django.utils import timezone

from .services.engine import ENGINE_NAMES
from .services.languages import AUTO, get_language_name


class TranslationQuerySet(models.QuerySet):
    """Reusable queries, available as Translation.objects.<method>()."""

    def summary(self):
        """Numbers for the home-page stat tiles: total, languages used, translations today."""
        sources = set(self.values_list("source_lang", flat=True))
        targets = set(self.values_list("target_lang", flat=True))
        languages = (sources | targets) - {AUTO}          # set union, then remove "auto"
        today = timezone.localdate()                       # today's date in IST (TIME_ZONE)
        return {
            "total": self.count(),
            "languages": len(languages),
            "today": self.filter(created_at__date=today).count(),
        }


class Translation(models.Model):
    class Origin(models.TextChoices):
        """Where the translation came from. Stored as the short value, shown as the label."""
        WEB = "web", "Web"
        CLI = "cli", "Command line"
        FILE = "file", "File upload"

    source_text = models.TextField()
    translated_text = models.TextField()
    source_lang = models.CharField(max_length=15, help_text='Language code, or "auto" if it could not be detected')
    target_lang = models.CharField(max_length=15)
    was_auto_detected = models.BooleanField(default=False)
    char_count = models.PositiveIntegerField(default=0)
    engine = models.CharField(max_length=20, default="google")
    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.WEB)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # indexed: we sort/filter by it

    objects = TranslationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]  # newest first everywhere by default
        indexes = [models.Index(fields=["source_lang", "target_lang"])]  # speeds up language filters

    def __str__(self):
        return f"{self.source_lang} -> {self.target_lang}: {self.source_text[:40]}"

    @property
    def source_name(self):
        return get_language_name(self.source_lang) if self.source_lang != AUTO else "Unknown"

    @property
    def target_name(self):
        return get_language_name(self.target_lang)

    @property
    def engine_name(self):
        return ENGINE_NAMES.get(self.engine, self.engine)

    @classmethod
    def from_result(cls, result, origin=Origin.WEB):
        """Save a TranslationResult (from services/engine.py) as a new row."""
        return cls.objects.create(
            source_text=result.source_text,
            translated_text=result.translated_text,
            source_lang=result.source_lang,
            target_lang=result.target_lang,
            was_auto_detected=result.was_auto_detected,
            char_count=len(result.source_text),
            engine=result.engine,
            origin=origin,
        )
