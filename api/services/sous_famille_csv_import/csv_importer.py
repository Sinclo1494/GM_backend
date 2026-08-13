from django.db import IntegrityError, transaction

from api.models import (
    Sous_Famille_Materiel,
)

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


# ---------------------------------------------------------
# Import exceptions
# ---------------------------------------------------------


class SousFamilleValidationExpiredError(Exception):
    """Validation does not exist or has expired."""

    pass


class SousFamilleImportError(Exception):
    """Unexpected database error during Sous_Famille_Materiel import."""

    pass


# ---------------------------------------------------------
# CSV Importer
# ---------------------------------------------------------


class SousFamilleCsvImporter:

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

            raise SousFamilleValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        summary = payload.get("summary", {})
        filename = payload.get("filename", "")

        # -----------------------------------------------------
        # 2. Build Django objects
        #
        # Rows have already been validated and converted
        # to the final model structure.
        # -----------------------------------------------------

        objects = [
            Sous_Famille_Materiel(**row)
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
                "filename": filename,
                "validation_summary": summary,
            }

        # -----------------------------------------------------
        # 4. Bulk insert
        # -----------------------------------------------------

        try:

            with transaction.atomic():

                Sous_Famille_Materiel.objects.bulk_create(
                    objects,
                    batch_size=BATCH_SIZE,
                )

        except IntegrityError as exc:

            # Keep the validation cache.
            # The user can retry if the failure was caused
            # by a temporary database issue.

            raise SousFamilleImportError(
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
            "filename": filename,
            "validation_summary": summary,
        }