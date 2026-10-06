"""Views (the V in MVT): receive a request, return a response."""
from django.contrib import messages
from django.shortcuts import render

from .exceptions import TranslationError
from .forms import TranslateForm
from .services.engine import translate_text
from .services.languages import AUTO, get_language_name

DEFAULT_TARGET = "hi"


def home(request):
    """Home page: GET shows an empty form, POST translates the submitted text."""
    result = None

    if request.method == "POST":
        form = TranslateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                result = translate_text(data["text"], data["target_lang"], data["source_lang"])
            except TranslationError as exc:
                messages.error(request, str(exc))
    else:
        form = TranslateForm(initial={"source_lang": AUTO, "target_lang": DEFAULT_TARGET})

    # (label, value) tuples. Real numbers arrive in US-03 when translations are saved.
    stats = [("Total translations", "—"), ("Languages used", "—"), ("Today", "—")]

    context = {
        "form": form,
        "result": result,
        "target_name": get_language_name(result.target_lang) if result else "",
        "stats": stats,
    }
    return render(request, "translator/home.html", context)
