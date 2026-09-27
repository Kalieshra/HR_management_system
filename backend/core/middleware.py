"""Resolves the active tenant for each request.

The frontend sends `X-Company-Id`; this middleware validates that the
authenticated user actually belongs to that company and attaches
`request.company` / `request.membership`. Everything downstream — viewsets,
permissions, caching — reads those two attributes and never trusts the header
on its own.
"""

from django.utils.deprecation import MiddlewareMixin

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


class CompanyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.company = None
        request.membership = None

        raw = request.META.get(COMPANY_HEADER)
        if not raw:
            return None

        try:
            company_id = int(raw)
        except (TypeError, ValueError):
            return None

        # DRF authenticates inside the view, so the user is usually anonymous
        # here; the viewset re-resolves through `resolve_company` once the
        # request is authenticated. We only stash the requested id.
        request.requested_company_id = company_id
        return None


def resolve_company(request):
    """Attach `request.company`/`request.membership` for an authenticated request.

    Returns the membership, or None when the user has no access to the
    requested company. A platform admin gets access to any company with a
    `None` membership.
    """
    from accounts.models import Membership
    from companies.models import Company

    company_id = getattr(request, "requested_company_id", None)
    if company_id is None:
        raw = request.META.get(COMPANY_HEADER)
        if not raw:
            return None
        try:
            company_id = int(raw)
        except (TypeError, ValueError):
            return None

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None

    company = Company.objects.filter(pk=company_id, is_active=True).first()
    if company is None:
        return None

    membership = (
        Membership.objects.filter(user=user, company=company).prefetch_related("branches").first()
    )
    if membership is None and not user.is_platform_admin:
        return None

    request.company = company
    request.membership = membership
    return membership
