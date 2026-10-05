"""URL patterns for the translator app."""
from django.urls import path

from . import views

app_name = "translator"  # lets templates use {% url 'translator:home' %}

urlpatterns = [
    path("", views.home, name="home"),
]
