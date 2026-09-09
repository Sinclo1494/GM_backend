from django.db import IntegrityError, transaction

from api.models import (
    Categorie_GM,
)

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


class CategorieGMValidationExpiredError(Exception):
    pass


class CategorieGMImportError(Exception):
    pass


class CategorieGMCsvImporter:

    def __init__(
        self,
        validation_id: str,
    ):
        self.validation_id = validation_id

    def import_data(self):

        payload = ValidationCache.get(
            self.validation_id
        )

        if payload is None:
            raise CategorieGMValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        filiale = payload.get("filiale")
        summary = payload.get("summary", {})
        filename = payload.get("filename", "")

        objects = [
            Categorie_GM(**row)
            for row in rows
        ]

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

        try:
            with transaction.atomic():
                Categorie_GM.objects.bulk_create(
                    objects,
                    batch_size=BATCH_SIZE,
                )
        except IntegrityError as exc:
            raise CategorieGMImportError(
                "L'import a échoué en raison d'une contrainte "
                "d'intégrité en base de données. "
                "Les données ont peut-être été modifiées "
                "depuis la validation."
            ) from exc

        ValidationCache.delete(
            self.validation_id
        )

        return {
            "success": True,
            "imported_rows": len(objects),
            "filiale": filiale,
            "filename": filename,
            "validation_summary": summary,
        }
