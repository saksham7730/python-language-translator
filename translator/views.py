"""Views (the V in MVT): receive a request, return a response."""
from django.shortcuts import render

# (title, description) tuples shown as cards on the home page
FEATURES = [
    ("Translate", "Translate text between 100+ languages using deep-translator."),
    ("Auto-detect", "Leave the source language on Auto and it will be detected for you."),
    ("History & stats", "Every translation is saved, searchable and summarised in charts."),
]


def home(request):
    """Landing page. Replaced by the translate form in US-01."""
    return render(request, "translator/home.html", {"features": FEATURES})
