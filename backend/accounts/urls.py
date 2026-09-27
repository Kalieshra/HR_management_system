from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("login", views.LoginView.as_view(), name="login"),
    path("refresh", views.RefreshView.as_view(), name="refresh"),
    path("logout", views.LogoutView.as_view(), name="logout"),
    path("me", views.MeView.as_view(), name="me"),
    path("accept-invite", views.AcceptInviteView.as_view(), name="accept-invite"),
    path("password/change", views.PasswordChangeView.as_view(), name="password-change"),
    path("password/reset", views.PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password/reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]
