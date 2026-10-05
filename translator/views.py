"""Views (the V in MVT): receive a request, return a response."""
from django.shortcuts import render

# A short preview list of (code, name) tuples for the dropdowns.
# US-01 replaces this with the full list from services/languages.py.
PREVIEW_LANGUAGES = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("mr", "Marathi"),
    ("fr", "French"),
    ("de", "German"),
    ("es", "Spanish"),
    ("ja", "Japanese"),
]


def home(request):
    """Home page: hero banner, translator card and stat tiles."""
    # (label, value) tuples. Real numbers arrive in US-03 when translations are saved.
    stats = [
        ("Total translations", "—"),
        ("Languages used", "—"),
        ("Today", "—"),
    ]
    context = {"languages": PREVIEW_LANGUAGES, "stats": stats}
    return render(request, "translator/home.html", context)
