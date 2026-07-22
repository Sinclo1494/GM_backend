from django.db import IntegrityError, transaction

from api.models import Grand_Materiel

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


# ---------------------------------------------------------
# Import exceptions
# ---------------------------------------------------------


class GMValidationExpiredError(Exception):
    """Validation does not exist or has expired."""

    pass


class GrandMaterielImportError(Exception):
    """Unexpected database error during Grand_Materiel import."""

    pass


# ---------------------------------------------------------
# CSV Importer
# ---------------------------------------------------------


class GMCsvImporter:

    def __init__(
        self,
        validation_id: str,
    ):
        self.validation_id = validation_id

    # ---------------------------------------------------------
    # Import validated rows
    # ---------------------------------------------------------

    def import_data(self):

        # -----------------------------------------------------
        # 1. Retrieve validation payload
        # -----------------------------------------------------

        payload = ValidationCache.get(
            self.validation_id
        )

        if payload is None:

            raise GMValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        filiale = payload.get("filiale")
        summary = payload.get("summary", {})

        # -----------------------------------------------------
        # 2. Build Django objects
        #
        # Rows have already been validated and converted
        # to the final model structure.
        # -----------------------------------------------------

        objects = [
            Grand_Materiel(**row)
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
                "validation_summary": summary,
            }

        # -----------------------------------------------------
        # 4. Bulk insert
        # -----------------------------------------------------

        try:

            with transaction.atomic():

                Grand_Materiel.objects.bulk_create(
                    objects,
                    batch_size=BATCH_SIZE,
                )

        except IntegrityError as exc:

            # Keep the validation cache.
            # The user can retry if the failure was caused
            # by a temporary database issue.

            raise GrandMaterielImportError(
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
            "validation_summary": summary,
        }