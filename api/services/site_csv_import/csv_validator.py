import csv

from django.core.exceptions import ValidationError as DjangoValidationError

from api.models import (
    Site,
    Filiale,
    Division,
)

from .csv_normalizer import CsvNormalizer
from .validation import CsvSchema, ValidationReport


class SiteCsvValidator:

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

        # ---------------------------------------------------------
        # Validation caches
        # ---------------------------------------------------------

        self.filiales = set()
        self.divisions = set()

        self.existing_sites = set()

        self.seen_sites = {}

    # ---------------------------------------------------------
    # Cache loading
    # ---------------------------------------------------------

    def load_cache(self):

        self.filiales = set(
            Filiale.objects.values_list(
                "code_filiale",
                flat=True,
            )
        )

        self.divisions = set(
            Division.objects.values_list(
                "code_division",
                flat=True,
            )
        )

        self.existing_sites = set(
            Site.objects.values_list(
                "code_site",
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

            code_site = cleaned.get("code_site")

            if code_site in self.existing_sites:

                report.increment_skipped()

                report.add_warning(
                    line=line_number,
                    field="code_site",
                    value=code_site,
                    message="Ce site existe déjà dans la base de données. Ligne ignorée.",
                )

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
        # Duplicate inside current CSV
        # -----------------------------------------------------

        code_site = row.get("code_site")

        if code_site is not None:

            if code_site in self.seen_sites:

                report.add_error(
                    line=line_number,
                    field="code_site",
                    value=code_site,
                    message=(
                        "Doublon dans le fichier CSV. "
                        f"Première occurrence ligne "
                        f"{self.seen_sites[code_site]}."
                    ),
                )

            else:

                self.seen_sites[code_site] = line_number

        # -----------------------------------------------------
        # Filiale
        # -----------------------------------------------------

        code_filiale = row.get("code_filiale")

        if (
            code_filiale is not None
            and code_filiale not in self.filiales
        ):

            report.add_error(
                line=line_number,
                field="code_filiale",
                value=code_filiale,
                message="Filiale inexistante.",
            )

        # -----------------------------------------------------
        # Division
        # -----------------------------------------------------

        code_division = row.get("code_division")

        if (
            code_division
            and code_division not in self.divisions
        ):

            report.add_error(
                line=line_number,
                field="code_division",
                value=code_division,
                message="Division inexistante.",
            )

        # -----------------------------------------------------
        # Prepare foreign keys
        # -----------------------------------------------------

        if "code_filiale" in row:
            row["code_filiale_id"] = row.pop("code_filiale")

        if row.get("code_division"):
            row["code_division_id"] = row.pop("code_division")
        else:
            row.pop("code_division", None)

        # -----------------------------------------------------
        # Django validation
        # -----------------------------------------------------

        self.validate_model(
            row=row,
            report=report,
            line_number=line_number,
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

        if row.get("est_bloque") is None:

            report.add_warning(
                line=line_number,
                field="est_bloque",
                value=None,
                message="La valeur est_bloque n'est pas renseignée.",
            )

        if row.get("jour_cloture_mouv_RH_paie") is None:

            report.add_warning(
                line=line_number,
                field="jour_cloture_mouv_RH_paie",
                value=None,
                message="Le jour de clôture RH/Paie n'est pas renseigné.",
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

        try:

            obj = Site(**row)

            obj.full_clean(
                validate_unique=False,
            )

        except DjangoValidationError as exc:

            if hasattr(exc, "message_dict"):

                for field_name, messages in exc.message_dict.items():

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