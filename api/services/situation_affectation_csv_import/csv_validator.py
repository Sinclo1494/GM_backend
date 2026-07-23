import csv

from api.models import (
    Grand_Materiel,
    Site,
    Type_Affectation,
    Type_Situation,
    Type_Etat_Materiel,
)

from .csv_normalizer import CsvNormalizer
from .validation import CsvSchema, ValidationReport


class SituationAffectationCsvValidator:

    def __init__(
        self,
        uploaded_file,
        schema: CsvSchema,
        mapping,
        delimiter=";",
        encoding="utf-8",
    ):
        self.schema = schema
        self.delimiter = delimiter
        self.encoding = encoding

        self.file = CsvNormalizer.normalize(
            uploaded_file=uploaded_file,
            schema=schema,
            mapping=mapping,
        )

        self.materials = set()
        self.sites = set()
        self.type_affectations = set()
        self.type_situations = {}
        self.etats = set()

        # duplicate_key -> first line
        self.seen_rows = {}

    # ---------------------------------------------------------
    # Cache
    # ---------------------------------------------------------

    def load_cache(self):

        self.materials = set(
            Grand_Materiel.objects.values_list(
                "code_materiel",
                flat=True,
            )
        )

        self.sites = set(
            Site.objects.values_list(
                "code_site",
                flat=True,
            )
        )

        self.type_affectations = set(
            Type_Affectation.objects.values_list(
                "code_type_affectation",
                flat=True,
            )
        )

        self.type_situations = {}

        for affectation, situation in Type_Situation.objects.values_list(
            "code_type_affectation",
            "code_type_situation",
        ):
            self.type_situations.setdefault(
                affectation,
                set(),
            ).add(situation)

        self.etats = set(
            Type_Etat_Materiel.objects.values_list(
                "code_type_etat_materiel",
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
        # Headers
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
        # Rows
        # -----------------------------------------------------

        for line_number, row in enumerate(reader, start=2):

            if not row or all(value.strip() == "" for value in row):
                continue

            report.increment_total()

            errors_before = len(report.errors)

            if len(row) != self.schema.column_count:

                report.add_error(
                    line=line_number,
                    message=(
                        f"{len(row)} colonnes détectées "
                        f"({self.schema.column_count} attendues)."
                    ),
                )

            cleaned = self.schema.validate_row(
                row=row,
                line_number=line_number,
                report=report,
            )

            if len(report.errors) > errors_before:
                report.increment_invalid()
                continue

            self.validate_business_rules(
                row=cleaned,
                report=report,
                line_number=line_number,
            )

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

        self.add_warnings(
            row=row,
            report=report,
            line_number=line_number,
        )

        # -----------------------------------------------------
        # Material
        # -----------------------------------------------------

        if row["code_materiel"] not in self.materials:

            report.add_error(
                line=line_number,
                field="code_materiel",
                value=row["code_materiel"],
                message=(
                    f"Le matériel '{row['code_materiel']}' n'existe pas."
                ),
            )

        # -----------------------------------------------------
        # Site
        # -----------------------------------------------------

        if row["code_site"] not in self.sites:

            report.add_error(
                line=line_number,
                field="code_site",
                value=row["code_site"],
                message=(
                    f"Le site '{row['code_site']}' n'existe pas."
                ),
            )

        # -----------------------------------------------------
        # Affectation type
        # -----------------------------------------------------

        if row["code_type_affectation"] not in self.type_affectations:

            report.add_error(
                line=line_number,
                field="code_type_affectation",
                value=row["code_type_affectation"],
                message=(
                    f"Le type d'affectation "
                    f"'{row['code_type_affectation']}' n'existe pas."
                ),
            )

        # -----------------------------------------------------
        # Situation type
        # -----------------------------------------------------

        allowed = self.type_situations.get(
            row["code_type_affectation"]
        )

        if (
            allowed is not None
            and row["code_type_situation"] not in allowed
        ):

            report.add_error(
                line=line_number,
                field="code_type_situation",
                value=row["code_type_situation"],
                message=(
                    f"Le type de situation "
                    f"'{row['code_type_situation']}' "
                    f"n'est pas autorisé pour le type "
                    f"d'affectation "
                    f"'{row['code_type_affectation']}'."
                ),
            )

        # -----------------------------------------------------
        # Material state
        # -----------------------------------------------------

        if (
            row["code_type_etat_materiel"]
            not in self.etats
        ):

            report.add_error(
                line=line_number,
                field="code_type_etat_materiel",
                value=row["code_type_etat_materiel"],
                message=(
                    f"L'état matériel "
                    f"'{row['code_type_etat_materiel']}' "
                    f"n'existe pas."
                ),
            )

        # -----------------------------------------------------
        # Duplicate
        # -----------------------------------------------------

        duplicate_key = (
            row["code_materiel"],
            row["code_site"],
            row["date_affectation"],
            row["code_type_affectation"],
            row["code_type_situation"],
            row["code_type_etat_materiel"],
            row["date_situation"],
        )

        if duplicate_key in self.seen_rows:

            report.add_error(
                line=line_number,
                message=(
                    "Doublon dans le fichier CSV. "
                    f"Première occurrence ligne "
                    f"{self.seen_rows[duplicate_key]}."
                ),
            )

        else:

            self.seen_rows[duplicate_key] = line_number

    # ---------------------------------------------------------
    # Warnings
    # ---------------------------------------------------------

    @staticmethod
    def add_warnings(
        row,
        report,
        line_number,
    ):

        if row.get("est_bloque") is None:

            report.add_warning(
                line=line_number,
                field="est_bloque",
                value=None,
                message="La valeur est_bloque n'est pas renseignée.",
            )