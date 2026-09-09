from rest_framework import permissions


class HasPagePermission(permissions.BasePermission):
    def __init__(self, *permission_required: str):
        self.permission_required = permission_required

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, "profile", None)
        if not profile:
            return False
        user_perms = profile.permissions or []
        is_write = request.method in ("POST", "PUT", "PATCH", "DELETE")
        for required in self.permission_required:
            if required in user_perms:
                return True
            if is_write:
                if f"{required}.write" in user_perms:
                    return True
            else:
                if f"{required}.read" in user_perms or f"{required}.write" in user_perms:
                    return True
        return False


class PagePermissionRequiredMixin:
    permission_required = None

    def get_permissions(self):
        if self.permission_required:
            perms = self.permission_required
            if isinstance(perms, str):
                perms = (perms,)
            return [HasPagePermission(*perms), permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
