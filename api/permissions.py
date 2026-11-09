from rest_framework import permissions

ALL_FILIALES_PERMISSION = "administration.all_filiales"


def can_access_all_filiales(user) -> bool:
    """
    Return True if the user may query every filiale database.

    Superusers always qualify.  Non-superusers qualify only when their
    UserProfile carries the ``administration.all_filiales`` permission
    (stored as ``administration.all_filiales``, ``administration.all_filiales.read``
    or ``administration.all_filiales.write`` by the frontend permission editor).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    
    if getattr(user, "is_external_service", False):
        return True
    
    if getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    perms = profile.permissions or []
    return (
        ALL_FILIALES_PERMISSION in perms
        or f"{ALL_FILIALES_PERMISSION}.read" in perms
        or f"{ALL_FILIALES_PERMISSION}.write" in perms
    )


def can_access_filiale(user, code_filiale) -> bool:
    """
    Return True if the user may access the given filiale database.

    - Superusers and users with ``administration.all_filiales`` always pass
      (as long as the code is a known affiliate).
    - Otherwise the user must belong to that filiale (profile.filiale).
    """
    if not code_filiale:
        return False
    if can_access_all_filiales(user):
        from django.conf import settings

        return code_filiale in settings.FILIALE_DATABASES
    profile = getattr(user, "profile", None)
    if profile is None or profile.filiale is None:
        return False
    return profile.filiale.code_filiale == code_filiale


def resolve_filiale_code(user, request=None):
    """
    Return the affiliate code the request must be routed to, or None.

    Resolution order:

    1. An explicit affiliate parameter on the request, but only when the user
       is allowed to access that affiliate.  Two parameter names are read:
       ``filiale`` (import endpoints, generic CRUD) and ``code_filiale``
       (analysis and dashboard endpoints, where it is also used as a data
       filter).  This is how a user with ``administration.all_filiales``
       targets a single affiliate database; a request for a forbidden
       affiliate is ignored (the views answer 403 on their own
       ``code_filiale`` parameter).
    2. The affiliate linked to the user's profile (assigned from the
       "Utilisateurs" page).
    3. None -> the caller decides (central database fallback).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None

    requested = None
    if request is not None:
        raw = (
            request.GET.get("filiale")
            or request.GET.get("code_filiale")
            or request.GET.get("libelle_filiale")
            or request.POST.get("filiale")
            or request.POST.get("code_filiale")
            or request.POST.get("libelle_filiale")
        )
        if raw:
            # Frontend searchable dropdowns send "CODE - LABEL"; keep only the code.
            requested = raw.split(" - ")[0].strip() if " - " in raw else raw.strip()
    if requested and can_access_filiale(user, requested):
        return requested

    profile = getattr(user, "profile", None)
    if profile is not None:
        filiale = getattr(profile, "filiale", None)
        if filiale is not None:
            return filiale.code_filiale

    return None


def can_include_pending_data(user) -> bool:
    """
    Return True if the user may include pending data in analysis/Journal.

    Admins (superusers) always qualify. Non-admins qualify when they have
    at least one import permission AND at least one analyse permission.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    perms = profile.permissions or []
    has_import = any(p == "import" or p.startswith("import.") for p in perms)
    has_analyse = any(p == "analyse" or p.startswith("analyse.") for p in perms)
    return has_import and has_analyse


def get_allowed_filiale_codes(user):
    """
    Return the list of filiale codes the given principal may read.

    - External services: the codes assigned to their
      ``ExternalServiceClient.allowed_filiales``. An empty set means NO
      access (not unrestricted access), so ``[]`` is returned. Codes are
      intersected with ``settings.FILIALE_DATABASES`` so only configured,
      routable filiales are ever returned.
    - Human users: the existing behaviour -- every configured filiale for
      superusers / ``all_filiales`` users, otherwise just their own.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return []

    if getattr(user, "is_external_service", False):
        from django.conf import settings

        from api.models import ExternalServiceClient

        try:
            client = ExternalServiceClient.objects.using("default").get(
                id=user.service_client_id
            )
        except ExternalServiceClient.DoesNotExist:
            return []
        if not client.is_active:
            return []
        configured = set(getattr(settings, "FILIALE_DATABASES", {}).keys())
        return [
            f.code_filiale
            for f in client.allowed_filiales.all()
            if f.code_filiale in configured
        ]

    if can_access_all_filiales(user):
        from django.conf import settings

        return list(getattr(settings, "FILIALE_DATABASES", {}).keys())

    profile = getattr(user, "profile", None)
    if profile is None or profile.filiale is None:
        return []
    return [profile.filiale.code_filiale]


class ExternalServiceDashboardPermission(permissions.BasePermission):
    def __init__(self, *permission_required: str):
        self.permission_required = permission_required

    def __call__(self):
        return self

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return False

        # External services: read-only access.
        if getattr(user, "is_external_service", False):
            return request.method == "GET"

        # Existing human-user permission logic.
        if user.is_superuser:
            return True

        profile = getattr(user, "profile", None)
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
                if (
                    f"{required}.read" in user_perms
                    or f"{required}.write" in user_perms
                ):
                    return True

        return False


class HasPagePermission(permissions.BasePermission):
    def __init__(self, *permission_required: str):
        self.permission_required = permission_required

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True
        if getattr(user, "is_external_service", False):
            return request.method == "GET"
        profile = getattr(user, "profile", None)
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
                if (
                    f"{required}.read" in user_perms
                    or f"{required}.write" in user_perms
                ):
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
class CanModifyEntityWhilePending(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        is_write = request.method in ('PUT', 'PATCH', 'DELETE')
        if not is_write:
            return True
        status = getattr(obj, 'status', 'CONFIRMED')
        if status == 'PENDING':
            imported_by = getattr(obj, 'imported_by', None)
            if imported_by and imported_by.id == user.id:
                return True
            return True
        else:
            return user.is_superuser
