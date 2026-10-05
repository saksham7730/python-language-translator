"""Forms: validate what the user submitted before we use it."""
from django import forms

from .services.engine import MAX_CHARS
from .services.languages import AUTO, language_choices


class TranslateForm(forms.Form):
    text = forms.CharField(
        max_length=MAX_CHARS,
        strip=True,  # remove leading/trailing spaces
        widget=forms.Textarea(attrs={
            "id": "source-text",
            "class": "form-control translate-box",
            "placeholder": "Type or paste text here…",
            "maxlength": MAX_CHARS,
            "rows": 8,  # same height as the output box
        }),
        error_messages={
            "required": "Please enter some text to translate.",
            "max_length": f"Text is too long. The limit is {MAX_CHARS} characters.",
        },
    )
    source_lang = forms.ChoiceField(widget=forms.Select(attrs={"id": "source-lang", "class": "form-select"}))
    target_lang = forms.ChoiceField(widget=forms.Select(attrs={"id": "target-lang", "class": "form-select"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Choices are filled in here (not at class level) so the language table is
        # loaded when a form is created, not when Django imports this file.
        # ChoiceField also rejects any value that isn't in its choices,
        # so an unsupported language code can't get through.
        choices = language_choices()
        self.fields["source_lang"].choices = [(AUTO, "Auto-detect"), *choices]
        self.fields["target_lang"].choices = choices
