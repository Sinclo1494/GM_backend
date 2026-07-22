import csv

from django.core.exceptions import ValidationError as DjangoValidationError

from api.models import (
    Famille_Materiel,
    Sous_Famille_Materiel,
)

from .csv_normalizer import CsvNormalizer
from .validation import CsvSchema, ValidationReport


class SousFamilleCsvValidator:

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

        # ---------------------------------------------------------
        # Normalize the uploaded CSV into the schema order.
        # ---------------------------------------------------------

        self.file = CsvNormalizer.normalize(
            uploaded_file=uploaded_file,
            schema=schema,
            mapping=mapping,
        )

        # ---------------------------------------------------------
        # Validation caches
        # ---------------------------------------------------------

        # Existing reference data
        self.familles = set()

        # Existing Sous_Famille_Materiel codes
        self.existing_sous_familles = set()

        # code_sous_famille already encountered inside the current CSV
        # code_sous_famille -> first CSV line
        self.seen_sous_familles = {}

    # ---------------------------------------------------------
    # Cache loading
    # ---------------------------------------------------------

    def load_cache(self):
        """
        Load all reference data required to validate the CSV.

        These collections allow business validation without
        querying the database for every CSV row.
        """

        

        self.familles = set(
            Famille_Materiel.objects.values_list(
                "code_famille",
                flat=True,
            )
        )


        self.existing_sous_familles = set(
            Sous_Famille_Materiel.objects.values_list(
                "code_sous_famille",
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
            #
            # Validate field types, lengths, dates,
            # decimals, booleans...
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

            # Ignore materials already present in the database.
            code_sous_famille = cleaned.get("code_sous_famille")

            if code_sous_famille in self.existing_sous_familles:
                report.increment_skipped()
                report.add_warning(
                    line=line_number,
                    field="code_sous_famille",
                    value=code_sous_famille,
                    message="Cette Sous Famille Matériel existe déjà dans la base de données. Ligne ignorée.",
                )
                continue

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
        Validate business rules that cannot be expressed by the
        primitive CSV schema.

        This includes:

        - Duplicate material detection
        - Foreign key existence
        - CSV duplicate detection
        - Preparing foreign keys for Django model validation
        """

        # -----------------------------------------------------
        # 1. Generate non-blocking warnings
        # -----------------------------------------------------

        self.add_warnings(
            row=row,
            report=report,
            line_number=line_number,
        )

        

        # -----------------------------------------------------
        # 2. Duplicate inside current CSV
        # -----------------------------------------------------
        code_sous_famille = row.get("code_sous_famille")
        if code_sous_famille is not None:

            if code_sous_famille in self.seen_sous_familles:

                report.add_error(
                    line=line_number,
                    field="code_sous_famille",
                    value=code_sous_famille,
                    message=(
                        "Doublon dans le fichier CSV. "
                        f"Première occurrence ligne "
                        f"{self.seen_sous_familles[code_sous_famille]}."
                    ),
                )

            else:

                self.seen_sous_familles[
                    code_sous_famille
                ] = line_number

        # -----------------------------------------------------
        # 3. Validate Marque
        # -----------------------------------------------------

        code_famille = row.get(
            "code_famille"
        )

        if (
            code_famille is not None
            and code_famille not in self.familles
        ):

            report.add_error(
                line=line_number,
                field="code_famille",
                value=code_famille,
                message="Marque inexistante.",
            )

        

        # -----------------------------------------------------
        # 4. Prepare foreign keys
        #
        # Django accepts assigning the foreign key value
        # directly through the "_id" attribute because each
        # foreign key uses a custom "to_field".
        # -----------------------------------------------------

        if "code_famille" in row:

            row[
                "code_famille_id"
            ] = row.pop(
                "code_famille"
            )

        # -----------------------------------------------------
        # 8. Django model validation
        # -----------------------------------------------------

        self.validate_model(
            row=row,
            report=report,
            line_number=line_number,
        )

    # ---------------------------------------------------------
    # Non-blocking warnings
    # ---------------------------------------------------------

    @staticmethod
    def add_warnings(
        row,
        report,
        line_number,
    ):
        """
        Generate informational warnings without rejecting the row.
        """

        # Optional blocked flag

        if row.get("est_bloque") is None:

            report.add_warning(
                line=line_number,
                field="est_bloque",
                value=None,
                message="La valeur est_bloque n'est pas renseignée.",
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
        """
        Validate the row using Django's built-in model validation.

        At this stage:

        - Primitive values have already been validated.
        - Business rules have already been checked.
        - Foreign keys have been converted to their *_id fields.

        This final validation ensures that the row satisfies all
        model constraints before it is imported.
        """

        try:

            obj = Sous_Famille_Materiel(**row)

            obj.full_clean(
                validate_unique=False,
            )

        except DjangoValidationError as exc:

            # Field-specific validation errors
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

            # Non-field validation errors
            else:

                for message in exc.messages:

                    report.add_error(
                        line=line_number,
                        field=None,
                        value=None,
                        message=str(message),
                    )