from django.db import IntegrityError, transaction

from api.models import Regularisation_GM

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


class RegularisationGMValidationExpiredError(Exception):
    """Validation does not exist or has expired."""

    pass


class RegularisationGMImportError(Exception):
    """Unexpected database error during Regularisation_GM import."""

    pass


class RegularisationGMCsvImporter:

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

        payload = ValidationCache.get(
            self.validation_id
        )

        if payload is None:
            raise RegularisationGMValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        filiale = payload.get("filiale")
        summary = payload.get("summary", {})
        filename = payload.get("filename", "")

        objects = [
            Regularisation_GM(
                **row,
                status='PENDING',
                imported_by=self.user,
                import_batch_id=self.import_batch_id or payload.get('import_batch_id'),
            )
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
                "import_batch_id": self.import_batch_id or payload.get('import_batch_id'),
            }

        try:
            with transaction.atomic():
                Regularisation_GM.objects.bulk_create(
                    objects,
                    batch_size=BATCH_SIZE,
                )

        except IntegrityError as exc:
            raise RegularisationGMImportError(
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
            "import_batch_id": self.import_batch_id or payload.get('import_batch_id'),
        }
