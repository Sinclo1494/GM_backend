from api.models import Journal
from api.models.journal import JournalActions, JournalModules


SENSITIVE_FIELDS = frozenset({
    "password",
    "password_hash",
    "token",
    "access",
    "refresh",
    "api_key",
    "secret",
    "secret_key",
    "credentials",
    "authorization",
    "token_refresh",
})


def sanitize_values(data):
    """
    Remove sensitive fields from a values dict before writing
    it to the journal.  Handles nested dicts and lists.
    """

    if data is None:
        return None

    if isinstance(data, dict):
        return {
            key: ("***" if _is_sensitive(key) else sanitize_values(value))
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [sanitize_values(item) for item in data]

    return data


def _is_sensitive(field_name):
    lowered = field_name.lower()
    return any(sensitive in lowered for sensitive in SENSITIVE_FIELDS)


def get_client_ip(request):
    """
    Extract the client IP address from a Django request,
    respecting the standard ``X-Forwarded-For`` header chain.
    """

    if request is None:
        return None

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
        if ip:
            return ip

    return request.META.get("REMOTE_ADDR")


def serialize_for_journal(instance, serializer_class):
    """
    Convert a model instance into a plain (sanitised) dict
    suitable for JSON storage in the journal.
    """

    data = serializer_class(instance).data
    data = dict(data)

    for key, value in list(data.items()):
        if value is None:
            data[key] = None
        elif hasattr(value, "isoformat"):
            data[key] = value.isoformat()

    return sanitize_values(data)


def log_action(
    user=None,
    action=None,
    module=None,
    objet_type=None,
    objet_id=None,
    description="",
    ancienne_valeur=None,
    nouvelle_valeur=None,
    request=None,
    code_filiale=None,
    code_site=None,
):
    """
    Create a journal (audit-trail) entry.

    This is the single, reusable entry-point used throughout
    the application to record business actions.
    """

    ip_address = get_client_ip(request)

    ancienne_valeur = sanitize_values(ancienne_valeur)
    nouvelle_valeur = sanitize_values(nouvelle_valeur)

    Journal.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        module=module,
        objet_type=str(objet_type) if objet_type else "",
        objet_id=str(objet_id) if objet_id is not None else "",
        description=description,
        ancienne_valeur=ancienne_valeur,
        nouvelle_valeur=nouvelle_valeur,
        ip_address=ip_address,
        code_filiale=code_filiale,
        code_site=code_site,
    )


def log_csv_import(
    request,
    result,
    module,
):
    """
    Create a summary journal entry for a CSV import operation.

    ``result`` is the dict returned by the importer's
    ``import_data()`` method.
    """

    summary = result.get("validation_summary", {})
    filiale = result.get("filiale", "")
    filename = result.get("filename", "")
    imported_rows = result.get("imported_rows", 0)

    total_rows = summary.get("total_rows", 0)
    errors = summary.get("errors", 0)

    if errors == 0 and imported_rows > 0:
        import_result = "SUCCESS"
    elif imported_rows == 0:
        import_result = "FAILED"
    else:
        import_result = "PARTIAL_SUCCESS"

    description = (
        f"Import CSV: {filename} — "
        f"{imported_rows}/{total_rows} lignes importées, "
        f"{errors} erreur(s)"
    )

    nouvelle_valeur = {
        "fichier": filename,
        "lignes_totales": total_rows,
        "lignes_importees": imported_rows,
        "erreurs": errors,
        "resultat": import_result,
        "filiale": filiale,
    }

    log_action(
        user=request.user,
        action=JournalActions.IMPORT,
        module=module,
        objet_type="ImportCSV",
        objet_id=filename,
        description=description,
        nouvelle_valeur=nouvelle_valeur,
        request=request,
        code_filiale=filiale,
    )
