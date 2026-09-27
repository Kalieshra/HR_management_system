"""Authentication: cookie JWT, roles, and the company switcher header."""

import pytest
from django.urls import reverse

from accounts.models import Role
from core.authentication import ACCESS_COOKIE, REFRESH_COOKIE
from core.factories import (
    BranchFactory,
    CompanyFactory,
    MembershipFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass!2026"


@pytest.fixture
def company():
    return CompanyFactory()


@pytest.fixture
def admin_user(company):
    user = UserFactory(password=PASSWORD)
    MembershipFactory(user=user, company=company, role=Role.COMPANY_ADMIN)
    return user


def login(api, user, password=PASSWORD):
    return api.post(
        reverse("core:accounts:login"),
        {"email": user.email, "password": password},
        format="json",
    )


def test_login_sets_httponly_cookies(api, admin_user):
    response = login(api, admin_user)

    assert response.status_code == 200
    assert ACCESS_COOKIE in response.cookies
    assert REFRESH_COOKIE in response.cookies
    assert response.cookies[ACCESS_COOKIE]["httponly"] is True
    # The token must never appear in the JSON body.
    assert "access" not in response.json()
    assert "token" not in response.json()


def test_login_returns_memberships_for_the_company_switcher(api, admin_user, company):
    response = login(api, admin_user)

    memberships = response.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["company_id"] == company.pk
    assert memberships[0]["role"] == Role.COMPANY_ADMIN


def test_login_with_a_wrong_password_fails(api, admin_user):
    response = api.post(
        reverse("core:accounts:login"),
        {"email": admin_user.email, "password": "not-the-password"},
        format="json",
    )

    assert response.status_code == 400
    assert ACCESS_COOKIE not in response.cookies


def test_inactive_account_cannot_sign_in(api, admin_user):
    admin_user.is_active = False
    admin_user.save()

    assert login(api, admin_user).status_code == 400


def test_me_requires_authentication(api):
    assert api.get(reverse("core:accounts:me")).status_code == 401


def test_me_works_from_the_cookie_alone(api, admin_user):
    login(api, admin_user)

    response = api.get(reverse("core:accounts:me"))

    assert response.status_code == 200
    assert response.json()["email"] == admin_user.email


def test_refresh_issues_a_new_access_cookie(api, admin_user):
    login(api, admin_user)

    response = api.post(reverse("core:accounts:refresh"))

    assert response.status_code == 200
    assert ACCESS_COOKIE in response.cookies


def test_refresh_without_a_token_is_unauthorised(api):
    assert api.post(reverse("core:accounts:refresh")).status_code == 401


def test_logout_clears_the_cookies(api, admin_user):
    login(api, admin_user)

    response = api.post(reverse("core:accounts:logout"))

    assert response.status_code == 200
    assert response.cookies[ACCESS_COOKIE].value == ""


def test_endpoints_need_a_company_header(api, admin_user):
    login(api, admin_user)

    response = api.get(reverse("core:employee-list"))

    assert response.status_code == 403


def test_company_header_grants_access(api, admin_user, company):
    login(api, admin_user)

    response = api.get(reverse("core:employee-list"), HTTP_X_COMPANY_ID=str(company.pk))

    assert response.status_code == 200


def test_company_header_for_a_company_you_do_not_belong_to_is_refused(api, admin_user):
    other = CompanyFactory()
    login(api, admin_user)

    response = api.get(reverse("core:employee-list"), HTTP_X_COMPANY_ID=str(other.pk))

    assert response.status_code == 403


def test_a_suspended_company_cannot_be_selected(api, admin_user, company):
    company.is_active = False
    company.save()
    login(api, admin_user)

    response = api.get(reverse("core:employee-list"), HTTP_X_COMPANY_ID=str(company.pk))

    assert response.status_code == 403


def test_branch_entry_user_cannot_create_employees(api, company):
    branch = BranchFactory(company=company)
    user = UserFactory(password=PASSWORD)
    membership = MembershipFactory(user=user, company=company, role=Role.BRANCH_ENTRY)
    membership.branches.set([branch])
    login(api, user)

    response = api.post(
        reverse("core:employee-list"),
        {"code": "X1", "name_ar": "اختبار", "branch": branch.pk, "base_salary": "5000"},
        format="json",
        HTTP_X_COMPANY_ID=str(company.pk),
    )

    assert response.status_code == 403


def test_platform_endpoints_are_closed_to_company_admins(api, admin_user):
    login(api, admin_user)

    assert api.get(reverse("core:platform-company-list")).status_code == 403


def test_platform_admin_sees_every_company(api):
    CompanyFactory.create_batch(3)
    owner = UserFactory(password=PASSWORD, is_platform_admin=True)
    login(api, owner)

    response = api.get(reverse("core:platform-company-list"))

    assert response.status_code == 200
    assert response.json()["count"] == 3


def test_password_reset_does_not_reveal_whether_an_email_exists(api, admin_user):
    known = api.post(
        reverse("core:accounts:password-reset"), {"email": admin_user.email}, format="json"
    )
    unknown = api.post(
        reverse("core:accounts:password-reset"), {"email": "nobody@example.test"}, format="json"
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_platform_admin_without_a_membership_can_read_a_company(api, company):
    """A platform owner belongs to no company, so `X-Company-Id` alone has to be
    enough — the frontend's company switcher for that role depends on it."""
    owner = UserFactory(password=PASSWORD, is_platform_admin=True)
    assert not owner.memberships.exists()
    login(api, owner)

    response = api.get(reverse("core:employee-list"), HTTP_X_COMPANY_ID=str(company.pk))

    assert response.status_code == 200


def test_platform_admin_is_refused_a_suspended_company(api, company):
    company.is_active = False
    company.save(update_fields=["is_active"])
    owner = UserFactory(password=PASSWORD, is_platform_admin=True)
    login(api, owner)

    response = api.get(reverse("core:employee-list"), HTTP_X_COMPANY_ID=str(company.pk))

    assert response.status_code == 403
