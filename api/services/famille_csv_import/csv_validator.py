import csv

from django.core.exceptions import ValidationError as DjangoValidationError

from api.models import (
    Categorie_GM,
    Famille_Materiel,
)

from .csv_normalizer import CsvNormalizer
from .validation import CsvSchema, ValidationReport


class FamilleCsvValidator:

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

        self.categories = set()
        self.existing_familles = set()
        self.seen_familles = {}

    def load_cache(self):

        self.categories = set(
            Categorie_GM.objects.values_list(
                "code_categorie",
                flat=True,
            )
        )

        self.existing_familles = set(
            Famille_Materiel.objects.values_list(
                "code_famille",
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

            code_famille = cleaned.get("code_famille")

            if code_famille in self.existing_familles:
                report.increment_skipped()
                report.add_warning(
                    line=line_number,
                    field="code_famille",
                    value=code_famille,
                    message="Cette Famille Matériel existe déjà dans la base de données. Ligne ignorée.",
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

        code_famille = row.get("code_famille")
        if code_famille is not None:
            if code_famille in self.seen_familles:
                report.add_error(
                    line=line_number,
                    field="code_famille",
                    value=code_famille,
                    message=(
                        "Doublon dans le fichier CSV. "
                        f"Première occurrence ligne "
                        f"{self.seen_familles[code_famille]}."
                    ),
                )
            else:
                self.seen_familles[code_famille] = line_number

        code_categorie = row.get("code_categorie_gm")

        if (
            code_categorie is not None
            and code_categorie not in self.categories
        ):
            report.add_error(
                line=line_number,
                field="code_categorie_gm",
                value=code_categorie,
                message="Catégorie GM inexistante.",
            )

        if "code_categorie_gm" in row:
            row["code_categorie_gm_id"] = row.pop("code_categorie_gm")

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
            obj = Famille_Materiel(**row)
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
