"""Django admin: browse and manage translations at /admin/ (after `createsuperuser`)."""
from django.contrib import admin

from .models import Translation


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source_lang", "target_lang", "short_text", "engine", "origin", "char_count")
    list_filter = ("origin", "engine", "was_auto_detected", "target_lang")
    search_fields = ("source_text", "translated_text")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)

    @admin.display(description="Text")
    def short_text(self, obj):
        return obj.source_text[:60]
