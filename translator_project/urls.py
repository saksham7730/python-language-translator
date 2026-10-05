"""Root URL configuration: sends each URL to the right app."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("translator.urls")),  # everything else is handled by our app
]
