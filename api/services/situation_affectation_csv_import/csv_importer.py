import re

from django.db import IntegrityError, transaction
from django.db.models import Max

from api.models import (
    Affectation_Materiel,
    Grand_Materiel,
    Situation_Materiel,
    Type_Etat_Materiel,
    Type_Situation,
)

from ..validation_cache import ValidationCache


BATCH_SIZE = 5000


# ---------------------------------------------------------
# Import exceptions
# ---------------------------------------------------------


class SituationAffectationValidationExpiredError(Exception):
    """Validation does not exist or has expired."""
    pass


class SituationAffectationImportError(Exception):
    """Unexpected database error during SituationAffectation import."""
    pass


# ---------------------------------------------------------
# CSV Importer
# ---------------------------------------------------------


class SituationAffectationCsvImporter:

    def __init__(
        self,
        validation_id: str,
    ):
        self.validation_id = validation_id
        self.filiale = None

        # Existing data
        self.materials = {}
        self.affectations = {}
        self.last_situations = {}

        # Reference tables
        self.type_situations = {}
        self.type_etats = {}

        # Sequences
        self.last_affectation_numbers = {}
        self.last_situation_number = 0

    # ---------------------------------------------------------
    # Cache loading
    # ---------------------------------------------------------

    def load_cache(self):

        # -----------------------------------------------------
        # Grand matériel
        # -----------------------------------------------------

        self.materials = {
            gm.code_materiel: gm
            for gm in Grand_Materiel.objects.all()
        }

        # -----------------------------------------------------
        # Type Situation
        # (code_type_affectation, code_type_situation)
        # -----------------------------------------------------

        self.type_situations = {
            (
                obj.code_type_affectation_id,
                obj.code_type_situation,
            ): obj
            for obj in Type_Situation.objects.select_related(
                "code_type_affectation"
            )
        }

        # -----------------------------------------------------
        # Etat matériel
        # -----------------------------------------------------

        self.type_etats = {
            obj.code_type_etat_materiel: obj
            for obj in Type_Etat_Materiel.objects.all()
        }

        # -----------------------------------------------------
        # Existing affectations
        # -----------------------------------------------------

        self.affectations.clear()
        self.last_affectation_numbers.clear()

        queryset = (
            Affectation_Materiel.objects
            .select_related("code_materiel")
            .only(
                "id",
                "code_affectation",
                "date_affectation",
                "code_site_id",
                "code_materiel__code_materiel",
            )
        )

        for aff in queryset:

            material = aff.code_materiel.code_materiel

            self.affectations[
                (
                    material,
                    aff.code_site_id,
                    aff.date_affectation,
                )
            ] = aff

            match = re.search(
                r"\.(\d+)$",
                aff.code_affectation or "",
            )

            if not match:
                continue

            number = int(match.group(1))

            if number > self.last_affectation_numbers.get(material, 0):
                self.last_affectation_numbers[material] = number

        # -----------------------------------------------------
        # Latest situation for every affectation
        # -----------------------------------------------------

        self.last_situations.clear()

        queryset = (
            Situation_Materiel.objects
            .select_related(
                "affectation_id",
                "type_situation_id",
                "type_situation_id__code_type_affectation",
                "code_type_etat_materiel",
            )
            .order_by(
                "affectation_id",
                "-date_situation",
                "-id",
            )
        )

        for situation in queryset:

            affectation_id = situation.affectation_id_id

            if affectation_id not in self.last_situations:
                self.last_situations[affectation_id] = situation

        # -----------------------------------------------------
        # Last situation sequence
        # -----------------------------------------------------

        latest = (
            Situation_Materiel.objects.aggregate(
                value=Max("id_situation")
            )["value"]
        )

        self.last_situation_number = 0

        if latest:
            match = re.search(r"(\d+)$", str(latest))
            if match:
                self.last_situation_number = int(match.group(1))

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def next_code_affectation(
        self,
        code_materiel,
    ):
        number = self.last_affectation_numbers.get(
            code_materiel,
            0,
        ) + 1

        self.last_affectation_numbers[code_materiel] = number

        return f"{code_materiel}.{number:03d}"

    def next_id_situation(self):

        self.last_situation_number += 1

        return f"{self.last_situation_number:06d}"

    # ---------------------------------------------------------
    # Affectation
    # ---------------------------------------------------------

    def get_or_create_affectation(
        self,
        row,
    ):

        key = (
            row["code_materiel"],
            row["code_site"],
            row["date_affectation"],
        )

        affectation = self.affectations.get(key)

        if affectation:
            return affectation

        affectation = self.create_affectation(row)

        self.affectations[key] = affectation

        return affectation

    def create_affectation(
        self,
        row,
    ):

        affectation = Affectation_Materiel(
            code_affectation=self.next_code_affectation(
                row["code_materiel"]
            ),
            code_materiel=self.materials[
                row["code_materiel"]
            ],
            code_site_id=row["code_site"],
            code_filiale_mere_id=self.filiale,
            date_affectation=row["date_affectation"],
            est_bloque=row.get("est_bloque", False),
        )

        affectation.full_clean(
            validate_unique=False,
        )

        affectation.save()

        return affectation

    # ---------------------------------------------------------
    # Situation
    # ---------------------------------------------------------

    @staticmethod
    def same_situation(
        last,
        row,
    ):
        """
        Returns True when the last recorded situation already matches
        the CSV row.
        """

        if last is None:
            return False

        return (
            last.type_situation_id.code_type_affectation_id
            == row["code_type_affectation"]
            and
            last.type_situation_id.code_type_situation
            == row["code_type_situation"]
            and
            last.code_type_etat_materiel_id
            == row["code_type_etat_materiel"]
        )

    def create_situation(
        self,
        affectation,
        row,
    ):

        type_situation = self.type_situations[
            (
                row["code_type_affectation"],
                row["code_type_situation"],
            )
        ]

        etat = self.type_etats[
            row["code_type_etat_materiel"]
        ]

        situation = Situation_Materiel(
            id_situation=self.next_id_situation(),
            affectation_id=affectation,
            type_situation_id=type_situation,
            code_type_etat_materiel=etat,
            date_situation=(
                row.get("date_situation")
                or row["date_affectation"]
            ),
            est_bloque=row.get("est_bloque", False),
            date_modification=row.get(
                "date_modification"
            ),
        )

        situation.full_clean(
            validate_unique=False,
        )

        situation.save()

        self.last_situations[
            affectation.id
        ] = situation

        return situation

    # ---------------------------------------------------------
    # Import
    # ---------------------------------------------------------

    def import_data(self):

        payload = ValidationCache.get(
            self.validation_id
        )

        if payload is None:
            raise SituationAffectationValidationExpiredError(
                "La validation est introuvable ou a expiré. "
                "Veuillez valider le fichier à nouveau."
            )

        rows = payload.get("rows", [])
        summary = payload.get("summary", {})
        self.filiale = payload.get("filiale")

        if self.filiale is None:
            raise SituationAffectationImportError(
                "La filiale est absente des données de validation."
            )

        if not rows:

            ValidationCache.delete(
                self.validation_id
            )

            return {
                "success": True,
                "imported_affectations": 0,
                "imported_situations": 0,
                "validation_summary": summary,
            }

        self.load_cache()

        imported_affectations = 0
        imported_situations = 0

        try:

            with transaction.atomic():

                batch = []

                for row in rows:

                    affectation_key = (
                        row["code_materiel"],
                        row["code_site"],
                        row["date_affectation"],
                    )

                    is_new_affectation = (
                        affectation_key
                        not in self.affectations
                    )

                    affectation = (
                        self.get_or_create_affectation(
                            row
                        )
                    )

                    if is_new_affectation:
                        imported_affectations += 1

                    last = self.last_situations.get(
                        affectation.id
                    )

                    if self.same_situation(
                        last,
                        row,
                    ):
                        continue

                    type_situation = self.type_situations[
                        (
                            row["code_type_affectation"],
                            row["code_type_situation"],
                        )
                    ]

                    etat = self.type_etats[
                        row["code_type_etat_materiel"]
                    ]

                    situation = Situation_Materiel(
                        id_situation=self.next_id_situation(),
                        affectation_id=affectation,
                        type_situation_id=type_situation,
                        code_type_etat_materiel=etat,
                        date_situation=(
                            row.get("date_situation")
                            or row["date_affectation"]
                        ),
                        est_bloque=row.get(
                            "est_bloque",
                            False,
                        ),
                        date_modification=row.get(
                            "date_modification"
                        ),
                    )

                    situation.full_clean(
                        validate_unique=False
                    )

                    batch.append(situation)

                    self.last_situations[
                        affectation.id
                    ] = situation

                    imported_situations += 1

                    if len(batch) >= BATCH_SIZE:

                        Situation_Materiel.objects.bulk_create(
                            batch,
                            batch_size=BATCH_SIZE,
                        )

                        batch.clear()

                if batch:

                    Situation_Materiel.objects.bulk_create(
                        batch,
                        batch_size=BATCH_SIZE,
                    )

        except IntegrityError as exc:

            raise SituationAffectationImportError(
                "L'import a échoué en raison d'une contrainte "
                "d'intégrité en base de données."
            ) from exc

        except Exception as exc:

            raise SituationAffectationImportError(
                f"Erreur pendant l'import : {exc}"
            ) from exc

        ValidationCache.delete(
            self.validation_id
        )

        return {
            "success": True,
            "imported_affectations": imported_affectations,
            "imported_situations": imported_situations,
            "validation_summary": summary,
        }