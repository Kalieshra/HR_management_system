"""Role-based permissions.

Three roles from the spec:
  platform_admin  -> every company (User.is_platform_admin)
  company_admin   -> one company, everything within it
  branch_entry    -> one company, data entry for its assigned branches only
"""

from rest_framework.permissions import BasePermission

from accounts.models import Role


class IsPlatformAdmin(BasePermission):
    message = "Platform administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_platform_admin)


class HasCompanyAccess(BasePermission):
    """The request carries a valid X-Company-Id the user belongs to."""

    message = "Select a company you have access to."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return getattr(request, "company", None) is not None


class IsCompanyAdmin(BasePermission):
    message = "Company administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_platform_admin:
            return True
        membership = getattr(request, "membership", None)
        return bool(membership and membership.role == Role.COMPANY_ADMIN)


class CanEnterBranchData(BasePermission):
    """Company admins may enter data anywhere; branch_entry only in their branches."""

    message = "You cannot enter data for this branch."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_platform_admin:
            return True
        membership = getattr(request, "membership", None)
        return membership is not None

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_platform_admin:
            return True
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        if membership.role == Role.COMPANY_ADMIN:
            return True

        branch_id = _branch_id_of(obj)
        if branch_id is None:
            return True
        return branch_id in set(membership.branches.values_list("id", flat=True))


def _branch_id_of(obj):
    if hasattr(obj, "branch_id"):
        return obj.branch_id
    employee = getattr(obj, "employee", None)
    return getattr(employee, "branch_id", None)


def allowed_branch_ids(request):
    """Branch ids this request may touch, or None for 'all of them'."""
    user = request.user
    if user.is_platform_admin:
        return None
    membership = getattr(request, "membership", None)
    if membership is None:
        return []
    if membership.role == Role.COMPANY_ADMIN:
        return None
    return list(membership.branches.values_list("id", flat=True))
