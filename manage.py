#!/usr/bin/env python
"""Django's command-line utility (runserver, migrate, test, createsuperuser, ...)."""
import os
import sys


def main():
    # Tell Django which settings module to use before anything else is loaded
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "translator_project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is it installed and is your virtual "
            "environment activated?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
