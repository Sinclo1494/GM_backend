import csv

from django.core.exceptions import ValidationError as DjangoValidationError

from api.models import (
    Regularisation_GM,
    Site,
)

from .csv_normalizer import CsvNormalizer
from .validation import CsvSchema, ValidationReport


class RegularisationGMCsvValidator:

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

        self.sites = set()
        self.existing_regularisations = set()
        self.seen_regularisations = {}

    def load_cache(self):
        self.sites = set(
            Site.objects.values_list(
                "code_site",
                flat=True,
            )
        )

        self.existing_regularisations = set(
            Regularisation_GM.objects.values_list(
                "code_site",
                "mmaa",
            )
        )

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

        for line_number, row in enumerate(reader, start=2):

            if not row or all(
                value.strip() == ""
                for value in row
            ):
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
            mmaa = cleaned.get("mmaa")

            if (code_site, mmaa) in self.existing_regularisations:
                report.increment_skipped()
                report.add_warning(
                    line=line_number,
                    field="code_site",
                    value=code_site,
                    message="Cette régularisation existe déjà dans la base de données. Ligne ignorée.",
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

        code_site = row.get("code_site")
        mmaa = row.get("mmaa")

        if (code_site, mmaa) in self.seen_regularisations:
            report.add_error(
                line=line_number,
                field="code_site",
                value=code_site,
                message=(
                    "Doublon dans le fichier CSV. "
                    f"Première occurrence ligne "
                    f"{self.seen_regularisations[(code_site, mmaa)]}."
                ),
            )
        else:
            self.seen_regularisations[(code_site, mmaa)] = line_number

        if code_site is not None and code_site not in self.sites:
            report.add_error(
                line=line_number,
                field="code_site",
                value=code_site,
                message="Site inexistant.",
            )

        if "code_site" in row:
            row["code_site_id"] = row.pop("code_site")

        self.validate_model(
            row=row,
            report=report,
            line_number=line_number,
        )

    @staticmethod
    def add_warnings(row, report, line_number):

        if row.get("observation") in ("", None):
            report.add_warning(
                line=line_number,
                field="observation",
                value=None,
                message="L'observation n'est pas renseignée.",
            )

        if row.get("est_bloque") is None:
            report.add_warning(
                line=line_number,
                field="est_bloque",
                value=None,
                message="La valeur est_bloque n'est pas renseignée.",
            )

        if row.get("date_modification") is None:
            report.add_warning(
                line=line_number,
                field="date_modification",
                value=None,
                message="La date de modification n'est pas renseignée.",
            )

    @staticmethod
    def validate_model(row, report, line_number):

        try:
            obj = Regularisation_GM(**row)
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
