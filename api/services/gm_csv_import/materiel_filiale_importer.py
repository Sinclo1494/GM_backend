from django.db import transaction

from api.models import Grand_Materiel

from ..validation_cache import ValidationCache


# ---------------------------------------------------------
# Import exceptions
# ---------------------------------------------------------


class MaterielFilialeValidationExpiredError(Exception):
    """Validation does not exist or has expired."""

    pass


class MaterielFilialeImportError(Exception):
    """Unexpected database error during the filiale update."""

    pass


# ---------------------------------------------------------
# CSV Importer
# ---------------------------------------------------------


class MaterielFilialeCsvImporter:
    """
    Reassign the `code_filiale_g` column of existing materials.

    No material is created or deleted here: each validated row
    only changes the filiale of the matching Grand_Materiel.
    """

    def __init__(
        self,
        validation_id: str,
    ):
        self.validation_id = validation_id

    # ---------------------------------------------------------
    # Update validated rows
    # ---------------------------------------------------------

    def import_data(self):

        # -----------------------------------------------------
        # 1. Retrieve validation payload
        # -----------------------------------------------------

        payload = ValidationCache.get(
            self.validation_id
        )

        if payload is None:

            raise MaterielFilialeValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        filiale = payload.get("filiale")
        summary = payload.get("summary", {})
        filename = payload.get("filename", "")

        # -----------------------------------------------------
        # 2. Nothing to update
        # -----------------------------------------------------

        if not rows:

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
        # 3. Update the filiale of each material
        # -----------------------------------------------------

        try:

            with transaction.atomic():

                for row in rows:

                    Grand_Materiel.objects.filter(
                        code_materiel=row["code_materiel"]
                    ).update(
                        code_filiale_g_id=row["code_filiale_g"]
                    )

        except Exception as exc:

            # Keep the validation cache so the user can retry
            # if the failure was caused by a temporary
            # database issue.

            raise MaterielFilialeImportError(
                "La mise à jour des filiales a échoué. "
                "Les données ont peut-être été modifiées "
                "depuis la validation."
            ) from exc

        # -----------------------------------------------------
        # 4. Consume validation cache
        # -----------------------------------------------------

        ValidationCache.delete(
            self.validation_id
        )

        # -----------------------------------------------------
        # 5. Return import summary
        # -----------------------------------------------------

        return {
            "success": True,
            "imported_rows": len(rows),
            "filiale": filiale,
            "filename": filename,
            "validation_summary": summary,
        }