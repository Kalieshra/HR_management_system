"""Authentication endpoints. Tokens live in HttpOnly cookies."""

import contextlib

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.serializers import (
    AcceptInviteSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserSerializer,
)
from core.authentication import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies


def _issue(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer}, tags=["auth"])
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        access, refresh = _issue(user)
        payload = UserSerializer(user).data
        return set_auth_cookies(Response(payload), access, refresh)


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=None, responses={200: dict}, tags=["auth"])
    def post(self, request):
        raw = request.COOKIES.get(REFRESH_COOKIE) or request.data.get("refresh")
        if not raw:
            return Response(
                {"detail": _("No refresh token was supplied.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(raw)
        except TokenError:
            return Response(
                {"detail": _("Your session has expired. Please sign in again.")},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({"detail": _("Token refreshed.")})
        return set_auth_cookies(response, str(refresh.access_token))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={200: dict}, tags=["auth"])
    def post(self, request):
        raw = request.COOKIES.get(REFRESH_COOKIE)
        if raw:
            # Blacklisting is best-effort: a already-expired or malformed token
            # should still sign the user out cleanly.
            with contextlib.suppress(TokenError, AttributeError):
                RefreshToken(raw).blacklist()
        return clear_auth_cookies(Response({"detail": _("Signed out.")}))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer}, tags=["auth"])
    def get(self, request):
        user = User.objects.prefetch_related("memberships__company", "memberships__branches").get(
            pk=request.user.pk
        )
        return Response(UserSerializer(user).data)

    @extend_schema(request=UserSerializer, responses={200: UserSerializer}, tags=["auth"])
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AcceptInviteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=AcceptInviteSerializer, responses={200: UserSerializer}, tags=["auth"])
    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        access, refresh = _issue(user)
        return set_auth_cookies(Response(UserSerializer(user).data), access, refresh)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={200: dict}, tags=["auth"])
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": _("Password updated.")})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=PasswordResetRequestSerializer, responses={200: dict}, tags=["auth"])
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_ORIGIN}/reset-password?uid={uid}&token={token}"
            send_mail(
                subject=_("Reset your password"),
                message=_("Open this link to choose a new password: %(link)s") % {"link": link},
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

        # Always the same answer, so the endpoint cannot be used to discover
        # which email addresses have accounts.
        return Response({"detail": _("If that email exists, a reset link has been sent.")})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: dict}, tags=["auth"])
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            pk = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=pk)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": _("This reset link is not valid.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, data["token"]):
            return Response(
                {"detail": _("This reset link has expired.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": _("Password updated. You can sign in now.")})
