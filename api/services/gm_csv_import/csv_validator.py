import csv

from django.core.exceptions import ValidationError as DjangoValidationError

from api.models import (
    Grand_Materiel,
    Sous_Famille_Materiel,
    Type_Marque,
    Filiale,
)

from .csv_normalizer import CsvNormalizer
from .validation import CsvSchema, ValidationReport


class GMCsvValidator:

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

        # ---------------------------------------------------------
        # Normalize the uploaded CSV into the schema order.
        # ---------------------------------------------------------

        self.file = CsvNormalizer.normalize(
            uploaded_file=uploaded_file,
            schema=schema,
            mapping=mapping,
            filiale=filiale,
        )

        # ---------------------------------------------------------
        # Validation caches
        # ---------------------------------------------------------

        # Existing reference data
        self.sous_familles = set()
        self.type_marques = set()
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
        Load all reference data required to validate the CSV.

        These collections allow business validation without
        querying the database for every CSV row.
        """

        self.sous_familles = set(
            Sous_Famille_Materiel.objects.values_list(
                "code_sous_famille",
                flat=True,
            )
        )

        self.type_marques = set(
            Type_Marque.objects.values_list(
                "code_type_marque",
                flat=True,
            )
        )

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
            code_materiel = cleaned.get("code_materiel")

            if code_materiel in self.existing_materials:
                report.increment_skipped()
                report.add_warning(
                    line=line_number,
                    field="code_materiel",
                    value=code_materiel,
                    message="Ce matériel existe déjà dans la base de données. Ligne ignorée.",
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
        code_materiel = row.get("code_materiel")
        if code_materiel is not None:

            if code_materiel in self.seen_materials:

                report.add_error(
                    line=line_number,
                    field="code_materiel",
                    value=code_materiel,
                    message=(
                        "Doublon dans le fichier CSV. "
                        f"Première occurrence ligne "
                        f"{self.seen_materials[code_materiel]}."
                    ),
                )

            else:

                self.seen_materials[
                    code_materiel
                ] = line_number

        # -----------------------------------------------------
        # 3. Validate Sous_Famille_Materiel
        # -----------------------------------------------------

        code_sous_famille = row.get(
            "code_sous_famille_materiel"
        )

        if (
            code_sous_famille is not None
            and code_sous_famille not in self.sous_familles
        ):

            report.add_error(
                line=line_number,
                field="code_sous_famille_materiel",
                value=code_sous_famille,
                message="Sous-famille inexistante.",
            )

        # -----------------------------------------------------
        # 4. Validate Type_Marque
        # -----------------------------------------------------

        code_type_marque = row.get(
            "code_type_marque"
        )

        if (
            code_type_marque
            and code_type_marque not in self.type_marques
        ):

            report.add_error(
                line=line_number,
                field="code_type_marque",
                value=code_type_marque,
                message="Type de marque inexistant.",
            )

        # -----------------------------------------------------
        # 5. Validate Filiale
        # -----------------------------------------------------

        code_filiale = row.get(
            "code_filiale_g"
        )

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

        # -----------------------------------------------------
        # 6. Prepare foreign keys
        #
        # Django accepts assigning the foreign key value
        # directly through the "_id" attribute because each
        # foreign key uses a custom "to_field".
        # -----------------------------------------------------

        if "code_sous_famille_materiel" in row:

            row[
                "code_sous_famille_materiel_id"
            ] = row.pop(
                "code_sous_famille_materiel"
            )

        if "code_type_marque" in row:

            value = row.pop("code_type_marque")

            if value not in ("", None):

                row["code_type_marque_id"] = value

        if "code_filiale_g" in row:

            row["code_filiale_g_id"] = row.pop(
                "code_filiale_g"
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

        # Optional serial number

        if row.get("num_serie") in ("", None):

            report.add_warning(
                line=line_number,
                field="num_serie",
                value=None,
                message="Le numéro de série n'est pas renseigné.",
            )

        # Optional registration

        if row.get("immatriculation") in ("", None):

            report.add_warning(
                line=line_number,
                field="immatriculation",
                value=None,
                message="L'immatriculation n'est pas renseignée.",
            )

        # Optional power

        if row.get("puissance_materiel") in ("", None):

            report.add_warning(
                line=line_number,
                field="puissance_materiel",
                value=None,
                message="La puissance du matériel n'est pas renseignée.",
            )

        # Optional acquisition date

        if row.get("date_acquisition") is None:

            report.add_warning(
                line=line_number,
                field="date_acquisition",
                value=None,
                message="La date d'acquisition n'est pas renseignée.",
            )

        # Optional modification date

        if row.get("date_modification") is None:

            report.add_warning(
                line=line_number,
                field="date_modification",
                value=None,
                message="La date de modification n'est pas renseignée.",
            )

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

            obj = Grand_Materiel(**row)

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