# urls.py
from django.urls import path

from .views import ProtectedTestView, RegisterView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path(
        "auth/protected-test/", ProtectedTestView.as_view(), name="auth-protected-test"
    ),
]
