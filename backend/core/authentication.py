"""JWT carried in HttpOnly cookies.

The browser never sees the token: Django sets it as an HttpOnly cookie on login
and the frontend simply sends `credentials: 'include'`. An `Authorization:
Bearer` header is still accepted so the OpenAPI page and scripts keep working.
"""

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework_simplejwt.authentication import JWTAuthentication

ACCESS_COOKIE = "hrms_access"
REFRESH_COOKIE = "hrms_refresh"


class CookieJWTAuthentication(JWTAuthentication):
    """Reads the access token from the cookie, falling back to the header."""

    def authenticate(self, request):
        header_result = super().authenticate(request)
        if header_result is not None:
            return header_result

        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


def set_auth_cookies(response, access: str, refresh: str | None = None):
    """Attach the auth cookies to a response using the configured cookie policy."""
    common = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "domain": settings.AUTH_COOKIE_DOMAIN,
        "path": "/",
    }
    access_lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
    response.set_cookie(
        ACCESS_COOKIE, access, max_age=int(access_lifetime.total_seconds()), **common
    )
    if refresh:
        refresh_lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        response.set_cookie(
            REFRESH_COOKIE, refresh, max_age=int(refresh_lifetime.total_seconds()), **common
        )
    return response


def clear_auth_cookies(response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(
            name,
            path="/",
            domain=settings.AUTH_COOKIE_DOMAIN,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )
    return response


class CookieJWTScheme(OpenApiAuthenticationExtension):
    """Teaches drf-spectacular about the cookie-based JWT."""

    target_class = "core.authentication.CookieJWTAuthentication"
    name = "cookieJWT"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": ACCESS_COOKIE}
