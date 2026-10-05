"""ASGI entry point, the async alternative to wsgi.py (not used in this project, kept for completeness)."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "translator_project.settings")

application = get_asgi_application()
