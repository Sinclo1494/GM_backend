from django.db import IntegrityError, transaction

from api.models import Pointage

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


# ---------------------------------------------------------
# Import exceptions
# ---------------------------------------------------------

class PointageValidationExpiredError(Exception):
    """Validation does not exist or has expired."""
    pass


class PointageImportError(Exception):
    """Unexpected database error during Pointage import."""
    pass


# ---------------------------------------------------------
# CSV Importer
# ---------------------------------------------------------

class PointageCsvImporter:

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
        # 1. Retrieve validated payload
        # -----------------------------------------------------

        payload = ValidationCache.get(
            self.validation_id
        )

        if payload is None:
            raise PointageValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        filiale = payload.get("filiale")
        summary = payload.get("summary", {})
        filename = payload.get("filename", "")

        # -----------------------------------------------------
        # 2. Build Pointage objects
        #
        # No validation here.

        # -----------------------------------------------------

        objects = [
            Pointage(
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
        # 4. Database import
        # -----------------------------------------------------

        try:

            with transaction.atomic():

                Pointage.objects.bulk_create(
                    objects,
                    batch_size=BATCH_SIZE,
                )

        except IntegrityError as exc:

            # Keep the validation cache.
            # The user may retry if the failure is temporary,
            # although a uniqueness race may require revalidation.

            raise PointageImportError(
                "L'import a échoué en raison d'une contrainte "
                "d'intégrité en base de données. "
                "Les données ont peut-être été modifiées depuis "
                "la validation."
            ) from exc

        # -----------------------------------------------------
        # 5. Consume validation only after successful import
        # -----------------------------------------------------

        ValidationCache.delete(
            self.validation_id
        )

        # -----------------------------------------------------
        # 6. Import result
        # -----------------------------------------------------

        return {
            "success": True,
            "imported_rows": len(objects),
            "filiale": filiale,
            "filename": filename,
            "validation_summary": summary,
            "import_batch_id": self.import_batch_id or payload.get('import_batch_id'),
        }
