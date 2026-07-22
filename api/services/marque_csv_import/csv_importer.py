from django.db import IntegrityError, transaction

from api.models import Marque_Materiel

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


# ---------------------------------------------------------
# Import exceptions
# ---------------------------------------------------------


class MarqueValidationExpiredError(Exception):
    """Validation does not exist or has expired."""

    pass


class MarqueImportError(Exception):
    """Unexpected database error during Marque_Materiel import."""

    pass


# ---------------------------------------------------------
# CSV Importer
# ---------------------------------------------------------


class MarqueCsvImporter:

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

            raise MarqueValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        summary = payload.get("summary", {})

        # -----------------------------------------------------
        # 2. Build Django objects
        #
        # Rows have already been validated and converted
        # to the final model structure.
        # -----------------------------------------------------

        objects = [
            Marque_Materiel(**row)
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
                "validation_summary": summary,
            }

        # -----------------------------------------------------
        # 4. Bulk insert
        # -----------------------------------------------------

        try:

            with transaction.atomic():

                Marque_Materiel.objects.bulk_create(
                    objects,
                    batch_size=BATCH_SIZE,
                )

        except IntegrityError as exc:

            # Keep the validation cache.
            # The user can retry if the failure was caused
            # by a temporary database issue.

            raise MarqueImportError(
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
            "validation_summary": summary,
        }