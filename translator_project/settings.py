"""
Project settings for the Python Language Translator.

Secrets and machine-specific values (secret key, debug flag, database login)
are read from a .env file, so the same code runs on any machine and no
password is ever committed to GitHub.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root: the folder that contains manage.py
BASE_DIR = Path(__file__).resolve().parent.parent

# Load key=value pairs from .env into os.environ (does nothing if .env is missing)
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    """Read an environment variable as a boolean ('True', '1', 'yes' -> True)."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# --- Security ---------------------------------------------------------------
# The fallback key is only for local development; a real key belongs in .env
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


# --- Applications -----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Our app
    "translator.apps.TranslatorConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "translator_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,  # look for templates inside each app's templates/ folder
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "translator_project.wsgi.application"


# --- Database ---------------------------------------------------------------
# DB_ENGINE=sqlite (default, zero setup) or DB_ENGINE=mysql (uses the DB_* values)
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()

if DB_ENGINE == "mysql":
    # PyMySQL is a pure-Python MySQL driver. install_as_MySQLdb() makes it
    # pretend to be "MySQLdb", the module name Django's MySQL backend imports.
    import pymysql

    pymysql.install_as_MySQLdb()

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "translator_db"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            # utf8mb4 = full Unicode: Hindi, Chinese, Arabic and emoji all store correctly
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --- Password validation (used by the admin user) ---------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Language and time ------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"  # timestamps are shown in IST
USE_I18N = True
USE_TZ = True               # store times in UTC, convert to TIME_ZONE for display


# --- Static files (CSS, JS, images) -----------------------------------------
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Logging ----------------------------------------------------------------
# Errors from our app are printed to the terminal running the server.
# Users see friendly messages; developers see the details here.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {
        "translator": {"handlers": ["console"], "level": "INFO"},
    },
}
