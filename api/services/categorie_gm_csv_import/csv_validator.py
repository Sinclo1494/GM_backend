import csv

from django.core.exceptions import ValidationError as DjangoValidationError

from api.models import (
    Categorie_GM,
)

from .csv_normalizer import CsvNormalizer
from .validation import CsvSchema, ValidationReport


class CategorieGMCsvValidator:

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

        self.existing_categories = set()
        self.seen_categories = {}

    def load_cache(self):

        self.existing_categories = set(
            Categorie_GM.objects.values_list(
                "code_categorie",
                flat=True,
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

            code_categorie = cleaned.get("code_categorie")

            if code_categorie in self.existing_categories:
                report.increment_skipped()
                report.add_warning(
                    line=line_number,
                    field="code_categorie",
                    value=code_categorie,
                    message="Cette Catégorie GM existe déjà dans la base de données. Ligne ignorée.",
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

        code_categorie = row.get("code_categorie")
        if code_categorie is not None:
            if code_categorie in self.seen_categories:
                report.add_error(
                    line=line_number,
                    field="code_categorie",
                    value=code_categorie,
                    message=(
                        "Doublon dans le fichier CSV. "
                        f"Première occurrence ligne "
                        f"{self.seen_categories[code_categorie]}."
                    ),
                )
            else:
                self.seen_categories[code_categorie] = line_number

        self.validate_model(
            row=row,
            report=report,
            line_number=line_number,
        )

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

    @staticmethod
    def validate_model(
        row,
        report,
        line_number,
    ):

        try:
            obj = Categorie_GM(**row)
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
