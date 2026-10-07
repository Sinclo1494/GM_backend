import csv

from api.models import (
    Grand_Materiel,
    Filiale,
)

from .csv_normalizer import CsvNormalizer
from .materiel_filiale_schema import MATERIEL_FILIALE_SCHEMA
from .validation import ValidationReport


class MaterielFilialeValidator:
    """
    Validate a CSV used to reassign the `code_filiale_g` column
    of materials that already exist in the database.

    Unlike GMCsvValidator, no row is ever created here: every row
    must reference an existing Grand_Materiel, and the import only
    updates its filiale.
    """

    def __init__(
        self,
        uploaded_file,
        mapping,
        delimiter=";",
        encoding="utf-8",
    ):

        self.schema = MATERIEL_FILIALE_SCHEMA
        self.delimiter = delimiter
        self.encoding = encoding

        # ---------------------------------------------------------
        # Normalize the uploaded CSV into the schema order.
        # ---------------------------------------------------------

        self.file = CsvNormalizer.normalize(
            uploaded_file=uploaded_file,
            schema=self.schema,
            mapping=mapping,
            allow_empty_code_filiale_g=True,
        )

        # ---------------------------------------------------------
        # Validation caches
        # ---------------------------------------------------------

        # Existing Filiale codes
        self.filiales = set()

        # Existing Grand_Materiel codes
        self.existing_materials = set()

        # Materials already encountered inside the current CSV
        # code_materiel -> first CSV line
        self.seen_materials = {}

    # ---------------------------------------------------------
    # Cache loading
    # ---------------------------------------------------------

    def load_cache(self):
        """
        Load the reference data required to validate the CSV.

        These collections allow business validation without
        querying the database for every CSV row.
        """

        self.filiales = set(
            Filiale.objects.values_list(
                "code_filiale",
                flat=True,
            )
        )

        self.existing_materials = set(
            Grand_Materiel.objects.values_list(
                "code_materiel",
                flat=True,
            )
        )

    # ---------------------------------------------------------
    # CSV validation
    # ---------------------------------------------------------

    def validate(self):

        report = ValidationReport()

        self.load_cache()

        self.file.seek(0)

        reader = csv.reader(
            self.file,
            delimiter=self.delimiter,
        )

        # -----------------------------------------------------
        # Validate headers
        # -----------------------------------------------------

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

            # Ignore completely empty rows
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
            # Primitive validation
            # -------------------------------------------------

            cleaned = self.schema.validate_row(
                row=row,
                line_number=line_number,
                report=report,
            )

            # Primitive validation failed.
            if len(report.errors) > errors_before:
                report.increment_invalid()
                continue

            # -------------------------------------------------
            # Ignore materials already encountered earlier
            # in the current CSV file.
            # -------------------------------------------------

            code_materiel = cleaned.get("code_materiel")

            if code_materiel in self.seen_materials:

                report.increment_skipped()

                report.add_warning(
                    line=line_number,
                    field="code_materiel",
                    value=code_materiel,
                    message=(
                        "Doublon dans le fichier CSV. "
                        f"Première occurrence ligne "
                        f"{self.seen_materials[code_materiel]}. "
                        "Ligne ignorée."
                    ),
                )

                continue

            self.seen_materials[code_materiel] = line_number

            # -------------------------------------------------
            # Business validation
            # -------------------------------------------------

            self.validate_business_rules(
                row=cleaned,
                report=report,
                line_number=line_number,
            )

            # -------------------------------------------------
            # Final row decision
            # -------------------------------------------------

            if len(report.errors) > errors_before:
                report.increment_invalid()
                continue

            report.add_row(cleaned)

        return report

    # ---------------------------------------------------------
    # Business validation
    # ---------------------------------------------------------

    def validate_business_rules(
        self,
        row,
        report,
        line_number,
    ):
        """
        Validate that the material already exists and that the
        target filiale exists.

        Only existing materials can be updated, so an unknown
        material is a blocking error instead of a new record.
        """

        # -----------------------------------------------------
        # 1. Validate Grand_Materiel
        # -----------------------------------------------------

        code_materiel = row.get("code_materiel")

        if code_materiel not in self.existing_materials:

            report.add_error(
                line=line_number,
                field="code_materiel",
                value=code_materiel,
                message="Matériel inexistant.",
            )

        # -----------------------------------------------------
        # 2. Validate Filiale
        # -----------------------------------------------------

        code_filiale = row.get("code_filiale_g")

        if (
            code_filiale is not None
            and code_filiale not in self.filiales
        ):

            report.add_error(
                line=line_number,
                field="code_filiale_g",
                value=code_filiale,
                message="Filiale inexistante.",
            )