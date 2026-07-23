import csv
import io


class CsvNormalizationError(Exception):
    """Raised when the raw CSV cannot be normalized safely."""
    pass


class CsvNormalizer:

    @staticmethod
    def normalize_datetime(value: str) -> str:
        """
        Normalize SQL Server date/datetime strings.

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
    def normalize(uploaded_file, schema, mapping, filiale=None):

        # ---------------------------------------------------------
        # 1. Validate mapping
        # ---------------------------------------------------------

        if not isinstance(mapping, dict):
            raise CsvNormalizationError(
                "Le mapping des colonnes est invalide."
            )

        expected_headers = schema.input_headers

        reverse_mapping = {}

        for csv_index, field_name in mapping.items():

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

            if field_name not in expected_headers:
                raise CsvNormalizationError(
                    f"Le champ '{field_name}' n'existe pas dans le schéma."
                )

            if field_name in reverse_mapping:
                raise CsvNormalizationError(
                    f"Le champ '{field_name}' est associé à plusieurs colonnes CSV."
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
        # 3. Decode
        # ---------------------------------------------------------

        try:
            text = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CsvNormalizationError(
                "Impossible de lire l'encodage du fichier. "
                "Le fichier doit être encodé en UTF-8."
            ) from exc

        # ---------------------------------------------------------
        # 4. CSV reader / writer
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

        # Canonical headers
        writer.writerow(expected_headers)

        # ---------------------------------------------------------
        # 5. Metadata
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

            for source_row in reader:

                # Skip empty rows
                if not source_row or not any(
                    cell.strip() for cell in source_row
                ):
                    continue

                normalized_row = []

                for field in expected_headers:

                    value = ""

                    if field in reverse_mapping:

                        csv_index = reverse_mapping[field]

                        if csv_index < len(source_row):
                            value = source_row[csv_index].strip()

                    normalized_row.append(value)

                # -------------------------------------------------
                # Normalize code_site
                # -------------------------------------------------

                if (
                    filiale
                    and code_site_index is not None
                    and normalized_row[code_site_index]
                ):

                    site = normalized_row[code_site_index].strip()

                    # Clean duplicate slashes/spaces
                    site = "/".join(
                        part.strip()
                        for part in site.split("/")
                        if part.strip()
                    )

                    # Prepend filiale only if missing
                    if "/" not in site:
                        site = f"{filiale}/{site}"

                    normalized_row[code_site_index] = site

                # -------------------------------------------------
                # Normalize dates / datetimes
                # -------------------------------------------------

                for field_name in (
                    "date_affectation",
                    "date_modification",
                    "date_situation",
                ):
                    if field_name in expected_headers:
                        index = expected_headers.index(field_name)
                        normalized_row[index] = (
                            CsvNormalizer.normalize_datetime(
                                normalized_row[index]
                            )
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