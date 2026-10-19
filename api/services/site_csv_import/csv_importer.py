from django.db import IntegrityError, transaction

from api.models import (
    Site,
)

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


# ---------------------------------------------------------
# Import exceptions
# ---------------------------------------------------------


class SiteValidationExpiredError(Exception):
    """Validation does not exist or has expired."""

    pass


class SiteImportError(Exception):
    """Unexpected database error during Site import."""

    pass


# ---------------------------------------------------------
# CSV Importer
# ---------------------------------------------------------


class SiteCsvImporter:

    def __init__(
        self,
        validation_id: str,
        user=None,
        import_batch_id: str | None = None,
    ):
        self.validation_id = validation_id
        self.user = user
        self.import_batch_id = import_batch_id

    def import_data(self):

        # -----------------------------------------------------
        # 1. Retrieve validation payload
        # -----------------------------------------------------

        payload = ValidationCache.get(
            self.validation_id
        )

        if payload is None:

            raise SiteValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        filiale = payload.get("filiale")
        summary = payload.get("summary", {})
        filename = payload.get("filename", "")

        # -----------------------------------------------------
        # 2. Build Django objects
        # -----------------------------------------------------

        objects = [
            Site(
                **row,
                status='PENDING',
                imported_by=self.user,
                import_batch_id=self.import_batch_id or payload.get('import_batch_id'),
            )
            for row in rows
        ]

        # -----------------------------------------------------
        # 3. Nothing to import
        # -----------------------------------------------------

        if not objects:

            ValidationCache.delete(
                self.validation_id
            )

            return {
                "success": True,
                "imported_rows": 0,
                "filiale": filiale,
                "filename": filename,
                "validation_summary": summary,
            }

        # -----------------------------------------------------
        # 4. Bulk insert
        # -----------------------------------------------------

        try:

            with transaction.atomic():

                Site.objects.bulk_create(
                    objects,
                    batch_size=BATCH_SIZE,
                )

        except IntegrityError as exc:

            raise SiteImportError(
                "L'import a échoué en raison d'une contrainte "
                "d'intégrité en base de données. "
                "Les données ont peut-être été modifiées "
                "depuis la validation."
            ) from exc

        # -----------------------------------------------------
        # 5. Consume validation cache
        # -----------------------------------------------------

        ValidationCache.delete(
            self.validation_id
        )

        # -----------------------------------------------------
        # 6. Return import summary
        # -----------------------------------------------------

        return {
            "success": True,
            "imported_rows": len(objects),
            "filiale": filiale,
            "filename": filename,
            "validation_summary": summary,
            "import_batch_id": self.import_batch_id or payload.get('import_batch_id'),
        }
