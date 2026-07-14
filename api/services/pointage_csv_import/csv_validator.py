import csv
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError

from api.models import Affectation_Materiel, Pointage

from .csv_normalizer import CsvNormalizer
from .validation import ValidationReport, CsvSchema


class CsvValidator:

    def __init__(
        self,
        uploaded_file,
        schema: CsvSchema,
        mapping,
        filiale,
        delimiter=";",
        encoding="utf-8",
    ):

        self.schema = schema
        self.delimiter = delimiter
        self.encoding = encoding
        self.filiale = filiale

        self.file = CsvNormalizer.normalize(
            uploaded_file=uploaded_file,
            schema=schema,
            mapping=mapping,
            filiale=filiale,
        )

        # Affectation business key -> affectation id
        self.affectations = {}

        # Existing Pointage keys already stored in DB
        self.existing_pointages = set()

        # Pointage keys encountered inside the current CSV
        # unique_key -> first CSV line
        self.seen_pointages = {}

    # ---------------------------------------------------------
    # Cache
    # ---------------------------------------------------------

    def load_cache(self):

        self.affectations = {
            (
                a.code_materiel.code_materiel,
                self.normalize_affectation_date(a.date_affectation),
                a.code_site.code_site,
            ): a.id
            for a in Affectation_Materiel.objects.filter(
                code_filiale_mere=self.filiale
            ).select_related(
                "code_materiel",
                "code_site",
            )
        }

        self.existing_pointages = set(
            Pointage.objects.values_list(
                "affectation_id",
                "mmaa",
            )
        )

    # ---------------------------------------------------------
    # Date normalization for cache keys
    # ---------------------------------------------------------

    @staticmethod
    def normalize_affectation_date(value):

        if value is None:
            return None

        # DateTimeField
        if hasattr(value, "date"):
            return value.date()

        # Already a date
        return value

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    def validate(self):

        report = ValidationReport()

        self.load_cache()

        self.file.seek(0)

        reader = csv.reader(
            self.file,
            delimiter=self.delimiter,
        )

        try:
            headers = next(reader)
        except StopIteration:

            report.add_error(
                message="Le fichier CSV est vide.",
            )

            return report

        if headers != self.schema.headers:

            report.add_error(
                message="Les en-têtes du fichier sont invalides.",
            )

            return report

        # -----------------------------------------------------
        # Validate every CSV row
        # -----------------------------------------------------

        for line_number, row in enumerate(reader, start=2):

            if not row or all(
                value.strip() == ""
                for value in row
            ):
                continue

            report.increment_total()

            errors_before = len(report.errors)

            # -------------------------------------------------
            # Structural validation
            # -------------------------------------------------

            if len(row) != self.schema.column_count:

                report.add_error(
                    line=line_number,
                    message=(
                        f"{len(row)} colonnes détectées "
                        f"({self.schema.column_count} attendues)."
                    ),
                )

            # -------------------------------------------------
            # Primitive/schema validation
            #
            # validate_row() must be defensive against missing
            # indexes and return all successfully cleaned fields.
            # -------------------------------------------------

            cleaned = self.schema.validate_row(
                row=row,
                line_number=line_number,
                report=report,
            )

            # -------------------------------------------------
            # Business validation
            #
            # Continue all checks that can safely run from the
            # successfully parsed values.
            # -------------------------------------------------

            self.validate_business_rules(
                row=cleaned,
                report=report,
                line_number=line_number,
            )

            # -------------------------------------------------
            # Final row decision
            # Count validity ONCE per CSV row.
            # -------------------------------------------------

            if len(report.errors) > errors_before:
                report.increment_invalid()
                continue

            report.add_row(cleaned)

        return report

    # ---------------------------------------------------------
    # Business Validation
    # ---------------------------------------------------------

    def validate_business_rules(
        self,
        row,
        report,
        line_number,
    ):

        # -----------------------------------------------------
        # 1. Generate non-blocking warnings
        # -----------------------------------------------------

        self.add_warnings(
            row=row,
            report=report,
            line_number=line_number,
        )

        # -----------------------------------------------------
        # 2. Affectation lookup
        #
        # Only possible when all parts of the affectation
        # business key were successfully parsed.
        # -----------------------------------------------------

        affectation_id = None

        code_materiel = row.get("code_materiel")
        code_site = row.get("code_site")
        date_affectation = row.get("date_affectation")

        if (
            code_materiel is not None
            and code_site is not None
            and date_affectation is not None
        ):

            affectation_key = (
                code_materiel,
                self.normalize_affectation_date(
                    date_affectation
                ),
                code_site,
            )

            affectation_id = self.affectations.get(
                affectation_key
            )

            if affectation_id is None:

                report.add_error(
                    line=line_number,
                    field="affectation",
                    value=str(affectation_key),
                    message="Affectation introuvable.",
                )

            else:
                row["affectation_id_id"] = affectation_id

        # -----------------------------------------------------
        # 3. Duplicate detection
        #
        # Requires affectation_id and mmaa.
        # -----------------------------------------------------

        mmaa = row.get("mmaa")

        if (
            affectation_id is not None
            and mmaa is not None
        ):

            unique_key = (
                affectation_id,
                mmaa,
            )

            # Existing database duplicate
            if unique_key in self.existing_pointages:

                report.add_error(
                    line=line_number,
                    field="mmaa",
                    value=mmaa,
                    message=(
                        "Le pointage existe déjà "
                        "dans la base de données."
                    ),
                )

            # Duplicate inside current CSV
            if unique_key in self.seen_pointages:

                first_line = self.seen_pointages[
                    unique_key
                ]

                report.add_error(
                    line=line_number,
                    field="mmaa",
                    value=mmaa,
                    message=(
                        "Doublon dans le fichier CSV. "
                        f"Première occurrence ligne "
                        f"{first_line}."
                    ),
                )

            else:
                # Track the first occurrence even if another
                # validation error exists on the current row.
                self.seen_pointages[
                    unique_key
                ] = line_number

        # -----------------------------------------------------
        # 4. Calculate derived fields
        #
        # Each calculation runs independently when its inputs
        # are valid.
        # -----------------------------------------------------

        self.calculate_amounts(row)

        # -----------------------------------------------------
        # 5. Remove CSV lookup-only fields
        #
        # Pointage(**row) should receive model fields only.
        # -----------------------------------------------------

        if affectation_id is not None:

            row.pop("code_materiel", None)
            row.pop("code_site", None)
            row.pop("date_affectation", None)

        # -----------------------------------------------------
        # 6. Model-level validation
        #
        # Only run when the row can actually construct a
        # Pointage instance.
        # -----------------------------------------------------

        self.validate_model(
            row=row,
            report=report,
            line_number=line_number,
        )

    # ---------------------------------------------------------
    # Calculated amounts
    # ---------------------------------------------------------

    @staticmethod
    def calculate_amounts(row):

        taux_location = row.get("taux_location")

        if taux_location is None:
            return

        heures_service = row.get("heures_service")
        heures_chomage = row.get("heures_chomage")
        heures_panne = row.get("heures_panne")

        if heures_service is not None:
            row["montant_service"] = (
                heures_service * taux_location
            )

        if heures_chomage is not None:
            row["montant_chomage"] = (
                heures_chomage * taux_location
            )

        if heures_panne is not None:
            row["montant_panne"] = (
                heures_panne * taux_location
            )

    # ---------------------------------------------------------
    # Warnings
    # ---------------------------------------------------------

    @staticmethod
    def add_warnings(
        row,
        report,
        line_number,
    ):

        heures_service = row.get("heures_service")
        heures_chomage = row.get("heures_chomage")
        heures_panne = row.get("heures_panne")
        potentiel = row.get("potentiel")

        # All hour values equal zero
        if (
            heures_service == Decimal("0")
            and heures_chomage == Decimal("0")
            and heures_panne == Decimal("0")
        ):

            report.add_warning(
                line=line_number,
                field="heures",
                value="0",
                message=(
                    "Toutes les valeurs d'heures "
                    "sont égales à zéro."
                ),
            )

        # Potential equal to zero
        if potentiel == Decimal("0"):

            report.add_warning(
                line=line_number,
                field="potentiel",
                value=potentiel,
                message="Le potentiel est égal à zéro.",
            )

        # Missing optional modification date
        if row.get("date_modification") is None:

            report.add_warning(
                line=line_number,
                field="date_modification",
                value=None,
                message=(
                    "La date de modification "
                    "n'est pas renseignée."
                ),
            )

        # Missing optional boolean
        if row.get("est_bloque") is None:

            report.add_warning(
                line=line_number,
                field="est_bloque",
                value=None,
                message=(
                    "La valeur est_bloque n'est pas "
                    "renseignée."
                ),
            )

    # ---------------------------------------------------------
    # Django model validation
    # ---------------------------------------------------------

    @staticmethod
    def validate_model(
        row,
        report,
        line_number,
    ):

        # Cannot construct the final model without affectation.
        if row.get("affectation_id_id") is None:
            return

        try:

            obj = Pointage(**row)

            obj.full_clean(
                validate_unique=False,
            )

        except DjangoValidationError as exc:

            if hasattr(exc, "message_dict"):

                for field_name, messages in (
                    exc.message_dict.items()
                ):

                    for message in messages:

                        report.add_error(
                            line=line_number,
                            field=field_name,
                            value=row.get(field_name),
                            message=str(message),
                        )

            else:

                for message in exc.messages:

                    report.add_error(
                        line=line_number,
                        field=None,
                        value=None,
                        message=str(message),
                    )