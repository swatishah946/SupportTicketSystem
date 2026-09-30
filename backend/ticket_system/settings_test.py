"""Settings for the test suite: fast, isolated, no network."""

import os

os.environ.setdefault("DEBUG", "True")
os.environ["GEMINI_API_KEY"] = ""  # never call a real LLM from tests
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")

from .settings import *  # noqa: E402,F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],  # noqa: F405
        "ai": "1000/min",
        "auth": "1000/min",
        "anon": "1000/min",
        "dj_rest_auth": "1000/min",
    },
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
