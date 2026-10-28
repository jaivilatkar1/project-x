"""Django settings for the Paylane support agent take-home."""

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-paylane-takehome-dev-only-change-me",
)

DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "agent",
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

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# Fixed UTC clock for deterministic refund age checks (clarification: fixed test clock).
FIXED_NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
REFUND_MAX_AMOUNT = 75.0
REFUND_MAX_AGE_DAYS = 30  # strictly less than 30 elapsed days; exactly 30 escalates
MAX_FAILED_VERIFICATIONS = 3

# Azure OpenAI — canonical names, with aliases from other NexaByte projects.
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = (
    os.getenv("AZURE_OPENAI_ENDPOINT")
    or os.getenv("LE_OPENAI_BASE")
    or ""
)
AZURE_OPENAI_API_VERSION = (
    os.getenv("AZURE_OPENAI_API_VERSION")
    or os.getenv("OPENAI_API_VERSION")
    or "2025-01-01-preview"
)
AZURE_OPENAI_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_DEPLOYMENT")
    or os.getenv("AZURE_OPENAI_GPT4O_MINI")
    or os.getenv("AZURE_OPEN_AI_MODEL")
    or os.getenv("LE_OPENAI_GPT4_TURBO")
    or "gpt-4o-mini"
)

AGENT_SEED_PATH = BASE_DIR / "agent" / "data" / "seed.json"
CONVERSATIONS_PATH = BASE_DIR / "conversations" / "cases.yaml"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
# Mode-separated folders so reviewers can tell live model vs rule-based harness apart.
TRANSCRIPTS_AZURE_DIR = TRANSCRIPTS_DIR / "azure"
TRANSCRIPTS_DETERMINISTIC_DIR = TRANSCRIPTS_DIR / "deterministic"
EVAL_REPORT_PATH = TRANSCRIPTS_DIR / "eval_report.json"
