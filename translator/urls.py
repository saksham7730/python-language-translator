"""URL patterns for the translator app."""
from django.urls import path

from . import views

app_name = "translator"  # lets templates use {% url 'translator:home' %}

urlpatterns = [
    path("", views.home, name="home"),
    path("history/", views.history, name="history"),
    path("history/<int:pk>/delete/", views.delete_translation, name="delete"),
    path("history/clear/", views.clear_history, name="clear"),
]
