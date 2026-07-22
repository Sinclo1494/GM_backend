import csv
import io
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class CsvNormalizationError(Exception):
    """Raised when the raw CSV cannot be normalized safely."""
    pass


class CsvNormalizer:
    
    @staticmethod
    def normalize_datetime(value: str) -> str:
        """
        Normalize SQL Server datetime strings.

        Examples:
            "2025-09-01 00:00:00.000" -> "2025-09-01 00:00:00"
            "2025-09-01 12:34:56.123" -> "2025-09-01 12:34:56"
            "2025-09-01"             -> "2025-09-01"
            ""                       -> ""
        """

        if not value:
            return ""

        value = value.strip()

        # Remove SQL Server milliseconds
        if "." in value:
            value = value.split(".", 1)[0]

        return value

    @staticmethod
    def normalize_decimal(value: str) -> str:
        """
        Normalize decimal values coming from CSV.

        Examples:
            "1 234,56"  -> "1234.56"
            "12,5"      -> "12.5"
            " 45 "      -> "45"
            "-"         -> "0.0"
            ""          -> ""
        """

        if not value:
            return ""
        value = (value.replace("\xa0", "")  # non-breaking spaces
                 .replace(" ", "")
                 .replace("-","0")
                 .replace(",", ".")
                 .strip())
        try:
            return str(
                Decimal(value).quantize(
                    Decimal("0.000001"),
                    rounding=ROUND_HALF_UP,
                )
            )
        except InvalidOperation:
            return value

        
    
    @staticmethod
    def normalize(uploaded_file, schema, mapping, filiale=None):

        # ---------------------------------------------------------
        # 1. Validate mapping
        # ---------------------------------------------------------

        if not isinstance(mapping, dict):
            raise CsvNormalizationError(
                "Le mapping des colonnes est invalide."
            )

        # IMPORTANT:
        # Use only fields that are actually expected from the CSV.
        # Calculated fields such as montant_service, montant_chomage,
        # montant_panne must NOT be included here.
        expected_headers = schema.input_headers

        reverse_mapping = {}

        for csv_index, field_name in mapping.items():

            # Validate CSV index
            try:
                index = int(csv_index)
            except (TypeError, ValueError):
                raise CsvNormalizationError(
                    f"Index de colonne CSV invalide : {csv_index!r}."
                )

            if index < 0:
                raise CsvNormalizationError(
                    f"L'index de colonne CSV ne peut pas être négatif : {index}."
                )

            # Validate target field
            if field_name not in expected_headers:
                raise CsvNormalizationError(
                    f"Le champ '{field_name}' n'existe pas "
                    f"dans les champs d'entrée du schéma."
                )

            # Detect duplicated mapping targets
            if field_name in reverse_mapping:
                raise CsvNormalizationError(
                    f"Le champ '{field_name}' est associé à plusieurs "
                    f"colonnes CSV."
                )

            reverse_mapping[field_name] = index

        # ---------------------------------------------------------
        # 2. Read uploaded file
        # ---------------------------------------------------------

        try:
            uploaded_file.seek(0)
            raw_content = uploaded_file.read()
        except Exception as exc:
            raise CsvNormalizationError(
                "Impossible de lire le fichier CSV."
            ) from exc

        if not raw_content:
            raise CsvNormalizationError(
                "Le fichier CSV est vide."
            )

        # ---------------------------------------------------------
        # 3. Decode CSV
        # ---------------------------------------------------------

        try:
            text = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CsvNormalizationError(
                "Impossible de lire l'encodage du fichier. "
                "Le fichier doit être encodé en UTF-8."
            ) from exc

        # ---------------------------------------------------------
        # 4. Prepare CSV reader
        # ---------------------------------------------------------

        reader = csv.reader(
            io.StringIO(text),
            delimiter=";",
            strict=True,
        )

        output = io.StringIO()

        writer = csv.writer(
            output,
            delimiter=";",
            lineterminator="\n",
        )

        # Write canonical CSV headers
        writer.writerow(expected_headers)

        # ---------------------------------------------------------
        # 5. Prepare normalization metadata
        # ---------------------------------------------------------

        filiale = filiale.strip() if filiale else None

        code_site_index = (
            expected_headers.index("code_site")
            if "code_site" in expected_headers
            else None
        )

        # ---------------------------------------------------------
        # 6. Normalize rows
        # ---------------------------------------------------------

        try:

            for row_number, source_row in enumerate(reader, start=1):

                # Ignore completely empty rows
                if not source_row or not any(
                    value.strip() for value in source_row
                ):
                    continue

                normalized_row = []

                for field in expected_headers:

                    value = ""

                    if field in reverse_mapping:

                        index = reverse_mapping[field]

                        if index < len(source_row):
                            value = source_row[index].strip()

                    normalized_row.append(value)

                # -------------------------------------------------
                # Normalize code_site
                # -------------------------------------------------

                if (
                    filiale
                    and code_site_index is not None
                    and normalized_row[code_site_index]
                ):

                    site = normalized_row[code_site_index]

                    site = "/".join(
                        part.strip()
                        for part in site.split("/")
                        if part.strip()
                    )

                    if site and "/" not in site:
                        site = f"{filiale}/{site}"

                    normalized_row[code_site_index] = site
                
                # -------------------------------------------------
                # Normalize decimal amounts
                # -------------------------------------------------

                for field_name in (
                    "montant_service",
                    "montant_chomage",
                    "montant_panne",
                    "taux_location",
                ):
                    if field_name in expected_headers:
                        index = expected_headers.index(field_name)
                        normalized_row[index] = CsvNormalizer.normalize_decimal(
                            normalized_row[index]
                        )

                # -------------------------------------------------
                # Normalize datetimes
                # -------------------------------------------------

                for field_name in (
                    "mmaa",
                    "date_affectation",
                    "date_modification",
                ):
                    if field_name in expected_headers:
                        index = expected_headers.index(field_name)
                        normalized_row[index] = CsvNormalizer.normalize_datetime(
                            normalized_row[index]
                        )

                writer.writerow(normalized_row)

        except csv.Error as exc:
            raise CsvNormalizationError(
                f"CSV mal formé à proximité de la ligne "
                f"{reader.line_num} : {exc}"
            ) from exc

        # ---------------------------------------------------------
        # 7. Return normalized CSV
        # ---------------------------------------------------------

        output.seek(0)

        return output