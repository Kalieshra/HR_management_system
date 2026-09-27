"""Base viewsets that make tenant scoping automatic.

Every tenant-owned endpoint inherits `TenantViewSet`, whose queryset is scoped
to `request.company` before anything else runs. A user of company A asking for
company B's object gets a 404, because the object is simply not in the
queryset — there is no code path that can forget the filter.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from core.middleware import resolve_company
from core.permissions import HasCompanyAccess


class TenantViewSet(viewsets.ModelViewSet):
    """ModelViewSet scoped to the active company."""

    permission_classes = [HasCompanyAccess]
    #: Set to False for endpoints whose rows are not branch-restricted.
    branch_scoped = False

    def initial(self, request, *args, **kwargs):
        # Resolve the tenant before permissions run, since they depend on it.
        resolve_company(request)
        super().initial(request, *args, **kwargs)

    @property
    def company(self):
        return getattr(self.request, "company", None)

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.company
        if company is None:
            return queryset.none()
        scoped = queryset.for_company(company)
        return self.apply_branch_scope(scoped)

    def apply_branch_scope(self, queryset):
        """Narrow to the branches a `branch_entry` user may see."""
        if not self.branch_scoped:
            return queryset

        from core.permissions import allowed_branch_ids

        branch_ids = allowed_branch_ids(self.request)
        if branch_ids is None:
            return queryset
        return queryset.filter(**{f"{self.branch_lookup}__in": branch_ids})

    #: Path from the model to its branch, for branch-scoped viewsets.
    branch_lookup = "branch_id"

    def perform_create(self, serializer):
        if self.company is None:
            raise PermissionDenied(_("Select a company first."))
        serializer.save(company=self.company)


class ReadOnlyTenantViewSet(TenantViewSet):
    http_method_names = ["get", "head", "options"]
