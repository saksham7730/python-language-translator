"""Views (the V in MVT): receive a request, return a response."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .exceptions import TranslationError
from .forms import HistoryFilterForm, TranslateForm
from .models import Translation
from .services.engine import translate_text
from .services.languages import AUTO, get_language_name, is_supported

DEFAULT_TARGET = "hi"
HISTORY_PAGE_SIZE = 10
LAST_RESULT_KEY = "last_translation"  # session key used to carry the result across the redirect


# ---------------------------------------------------------------------------
# Home / translate
# ---------------------------------------------------------------------------

def _result_to_dict(result, chosen_source):
    """Turn a TranslationResult into plain data that can be stored in the session (JSON)."""
    detection = result.detection
    return {
        "source_text": result.source_text,
        "translated_text": result.translated_text,
        "chosen_source": chosen_source,          # what the user picked in "From" (to refill the form)
        "target_lang": result.target_lang,
        "target_name": get_language_name(result.target_lang),
        "engine_name": result.engine_name,
        "used_fallback": result.used_fallback,
        "was_auto_detected": result.was_auto_detected,
        "detection": {
            "name": detection.name,
            "percent": detection.percent,
            "reliable": detection.reliable,
            "romanized": detection.romanized,
        } if detection else None,
    }


def _initial_form_values(request, result):
    """Pre-fill the form: from the last result, from a 'Translate again' link, or defaults."""
    if result:
        return {"text": result["source_text"], "source_lang": result["chosen_source"],
                "target_lang": result["target_lang"]}
    source, target = request.GET.get("from", AUTO), request.GET.get("to", DEFAULT_TARGET)
    return {
        "text": request.GET.get("text", ""),
        "source_lang": source if source == AUTO or is_supported(source) else AUTO,
        "target_lang": target if is_supported(target) else DEFAULT_TARGET,
    }


def home(request):
    """GET shows the form (and the last result); POST translates, saves and redirects.

    Post/Redirect/Get: after a successful POST we redirect, so refreshing the page
    doesn't submit the form again and save a duplicate translation.
    """
    result = None
    if request.method == "POST":
        form = TranslateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                translation = translate_text(data["text"], data["target_lang"], data["source_lang"])
            except TranslationError as exc:
                messages.error(request, str(exc))
            else:
                Translation.from_result(translation)  # US-03: save every successful translation
                request.session[LAST_RESULT_KEY] = _result_to_dict(translation, data["source_lang"])
                return redirect("translator:home")
    else:
        result = request.session.pop(LAST_RESULT_KEY, None)  # pop: show it once, then forget it
        form = TranslateForm(initial=_initial_form_values(request, result))

    summary = Translation.objects.summary()
    stats = [("Total translations", summary["total"]),
             ("Languages used", summary["languages"]),
             ("Today", summary["today"])]
    return render(request, "translator/home.html", {"form": form, "result": result, "stats": stats})


# ---------------------------------------------------------------------------
# History (US-04 list, US-05 search/filter, US-06 delete)
# ---------------------------------------------------------------------------

def history(request):
    form = HistoryFilterForm(request.GET or None)
    translations = form.apply(Translation.objects.all())
    page_obj = Paginator(translations, HISTORY_PAGE_SIZE).get_page(request.GET.get("page"))
    context = {
        "form": form,
        "page_obj": page_obj,
        "is_filtered": form.is_bound and form.has_filters(),
        "has_any": Translation.objects.exists(),
    }
    return render(request, "translator/history.html", context)


def _safe_next_url(request):
    """Where to go after deleting. Only allow links to our own site (prevents open redirects)."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                                    require_https=request.is_secure()):
        return next_url
    return reverse("translator:history")


@require_http_methods(["GET", "POST"])
def delete_translation(request, pk):
    """GET shows a confirmation page; only POST actually deletes."""
    translation = get_object_or_404(Translation, pk=pk)
    next_url = _safe_next_url(request)
    if request.method == "POST":
        translation.delete()
        messages.success(request, "Translation deleted.")
        return redirect(next_url)
    return render(request, "translator/confirm_delete.html",
                  {"translation": translation, "count": 1, "next": next_url})


@require_http_methods(["GET", "POST"])
def clear_history(request):
    """Delete every translation, after a confirmation page."""
    count = Translation.objects.count()
    if request.method == "POST":
        deleted, _ = Translation.objects.all().delete()
        messages.success(request, f"Deleted {deleted} translation{'s' if deleted != 1 else ''}.")
        return redirect("translator:history")
    return render(request, "translator/confirm_delete.html",
                  {"translation": None, "count": count, "next": reverse("translator:history")})
