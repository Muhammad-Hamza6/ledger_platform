from .base import *

# Fast password hashing for tests — real hashing (Argon2/bcrypt) is
# deliberately slow, which needlessly slows down every test that creates a user.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Celery: run tasks synchronously/eagerly in tests instead of needing
# a real broker — relevant once Sprint 4 adds Celery.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable throttling in tests unless a specific test is checking it —
# otherwise your rate-limit tests from Sprint 3 can bleed into unrelated
# tests that happen to run many requests.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
}
