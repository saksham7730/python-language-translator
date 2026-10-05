"""WSGI entry point, used when the project is deployed on a real web server."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "translator_project.settings")

application = get_wsgi_application()
