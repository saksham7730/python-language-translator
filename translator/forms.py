"""Forms: validate what the user submitted before we use it."""
from django import forms
from django.db.models import Q

from .services.engine import MAX_CHARS, MAX_DOCUMENT_CHARS
from .services.languages import AUTO, language_choices


class LanguagePairForm(forms.Form):
    """Base form with the From/To dropdowns, shared by the text form and the file form."""

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

    def clean(self):
        """Checks that involve more than one field run here, after each field is validated."""
        cleaned = super().clean()
        source, target = cleaned.get("source_lang"), cleaned.get("target_lang")
        if source and source != AUTO and source == target:
            raise forms.ValidationError(
                "The source and target languages are the same. Choose a different target language."
            )
        return cleaned


class TranslateForm(LanguagePairForm):
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

    field_order = ["source_lang", "target_lang", "text"]


MAX_UPLOAD_BYTES = 200 * 1024  # 200 KB is plenty for 20,000 characters


class FileTranslateForm(LanguagePairForm):
    """Upload a .txt file (US-10). clean_file() returns the decoded TEXT, not the file object."""

    file = forms.FileField(
        label="Text file (.txt)",
        widget=forms.ClearableFileInput(attrs={"accept": ".txt,text/plain", "class": "form-control"}),
        error_messages={"required": "Please choose a .txt file."},
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".txt"):
            raise forms.ValidationError("Only .txt files are supported.")
        if upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(f"The file is too big ({upload.size // 1024} KB). The limit is 200 KB.")
        try:
            # utf-8-sig also removes the invisible "BOM" mark that Notepad sometimes adds
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise forms.ValidationError(
                "The file must be saved as UTF-8 text. In Notepad: File → Save As → Encoding: UTF-8."
            )
        text = text.strip()
        if not text:
            raise forms.ValidationError("The file is empty.")
        if len(text) > MAX_DOCUMENT_CHARS:
            raise forms.ValidationError(
                f"The file has {len(text):,} characters. The limit is {MAX_DOCUMENT_CHARS:,}."
            )
        return text


class HistoryFilterForm(forms.Form):
    """Search and filter box on the history page (US-05). Submitted with GET so the
    filters stay in the URL: they can be bookmarked and survive changing pages."""

    q = forms.CharField(
        required=False, label="Search",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Search text…", "type": "search"}),
    )
    source_lang = forms.ChoiceField(required=False, label="From", widget=forms.Select(attrs={"class": "form-select"}))
    target_lang = forms.ChoiceField(required=False, label="To", widget=forms.Select(attrs={"class": "form-select"}))
    date_from = forms.DateField(required=False, label="From date",
                                widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    date_to = forms.DateField(required=False, label="To date",
                              widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = language_choices()
        self.fields["source_lang"].choices = [("", "Any language"), (AUTO, "Unknown (auto)"), *choices]
        self.fields["target_lang"].choices = [("", "Any language"), *choices]

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_from"), cleaned.get("date_to")
        if start and end and start > end:
            raise forms.ValidationError("The 'from' date must be on or before the 'to' date.")
        return cleaned

    def has_filters(self):
        """True if the user filled in at least one filter."""
        return self.is_valid() and any(self.cleaned_data.values())

    def apply(self, queryset):
        """Return the queryset narrowed down by whichever filters were filled in."""
        if not self.is_valid():
            return queryset
        data = self.cleaned_data
        if data["q"]:
            # Q objects combine conditions with OR (|); icontains = case-insensitive "contains"
            queryset = queryset.filter(Q(source_text__icontains=data["q"]) | Q(translated_text__icontains=data["q"]))
        if data["source_lang"]:
            queryset = queryset.filter(source_lang=data["source_lang"])
        if data["target_lang"]:
            queryset = queryset.filter(target_lang=data["target_lang"])
        if data["date_from"]:
            queryset = queryset.filter(created_at__date__gte=data["date_from"])
        if data["date_to"]:
            queryset = queryset.filter(created_at__date__lte=data["date_to"])
        return queryset
