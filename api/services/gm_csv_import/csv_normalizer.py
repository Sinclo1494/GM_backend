import csv
import io
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

INVALID_DATE_VALUES = {
    "0-00-00",
    "0000-00-00",
    "00/00/0000",
    "0000/00/00",
}

class CsvNormalizationError(Exception):
    """Raised when the raw CSV cannot be normalized safely."""

    pass


class CsvNormalizer:

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

        expected_headers = schema.input_headers

        reverse_mapping = {}

        for csv_index, field_name in mapping.items():

            # -----------------------------------------------------
            # Validate CSV index
            # -----------------------------------------------------

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

            # -----------------------------------------------------
            # Validate target field
            # -----------------------------------------------------

            if field_name not in expected_headers:

                raise CsvNormalizationError(
                    f"Le champ '{field_name}' n'existe pas "
                    "dans les champs attendus."
                )

            if field_name in reverse_mapping:

                raise CsvNormalizationError(
                    f"Le champ '{field_name}' est associé "
                    "à plusieurs colonnes CSV."
                )

            reverse_mapping[field_name] = index

        # ---------------------------------------------------------
        # 2. Ensure all required fields are mapped
        # ---------------------------------------------------------

        required_headers = {
            field.name
            for field in schema.fields
            if field.required
        }

        missing = required_headers - set(reverse_mapping)

        # code_filiale_g can be supplied by the UI
        if "code_filiale_g" in missing and filiale:
            missing.remove("code_filiale_g")

        if missing:

            raise CsvNormalizationError(
                "Les champs obligatoires suivants ne sont pas mappés : "
                f"{', '.join(sorted(missing))}."
            )

        if filiale:
            filiale = filiale.strip()

        # ---------------------------------------------------------
        # 3. Read uploaded file
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
        # 4. Decode CSV
        # ---------------------------------------------------------

        try:

            text = raw_content.decode("utf-8-sig")

        except UnicodeDecodeError as exc:

            raise CsvNormalizationError(
                "Impossible de lire l'encodage du fichier. "
                "Le fichier doit être encodé en UTF-8."
            ) from exc

        # ---------------------------------------------------------
        # 5. Prepare CSV reader / writer
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

        # Write canonical headers

        writer.writerow(expected_headers)

        # ---------------------------------------------------------
        # 6. Normalize rows
        # ---------------------------------------------------------

        try:

            for source_row in reader:

                # Ignore completely empty rows

                if (
                    not source_row
                    or not any(cell.strip() for cell in source_row)
                ):
                    continue

                source_row = [
                    cell.strip()
                    for cell in source_row
                ]

                normalized_row = []

                for field in expected_headers:

                    value = ""

                    if field in reverse_mapping:

                        index = reverse_mapping[field]

                        if index < len(source_row):
                            value = source_row[index]

                    # ---------------------------------------------
                    # Handle code_filiale_g
                    # ---------------------------------------------

                    if field == "code_filiale_g":

                        # If the CSV provides a value, keep it.
                        if value:
                            normalized_row.append(value)

                        # Otherwise use the UI value.
                        elif filiale:
                            normalized_row.append(filiale)

                        # Neither CSV nor UI provided a value.
                        else:
                            raise CsvNormalizationError(
                                "Le champ 'code_filiale_g' est obligatoire. "
                                "Il doit être présent dans le fichier CSV "
                                "ou une filiale doit être sélectionnée."
                            )

                        continue
                    
                    # Normalize date fields
                    if field in {"date_acquisition", "date_modification"}:
                        value = value.replace('"', "").strip()

                        if value in INVALID_DATE_VALUES:
                            value = ""

                    normalized_row.append(value)
                
                # -------------------------------------------------
                # Normalize decimal amounts
                # -------------------------------------------------

                for field_name in (
                    "valeur_acquisition",
                    "valeur_remplacement",
                    "taux_amortissement",
                ):
                    if field_name in expected_headers:
                        index = expected_headers.index(field_name)
                        normalized_row[index] = CsvNormalizer.normalize_decimal(
                            normalized_row[index]
                        )

                # -------------------------------------------------
                # Normalize "NULL" values
                # -------------------------------------------------

                for header in expected_headers:
                    index = expected_headers.index(header)
                    if (normalized_row[index] == 'NULL'):
                        normalized_row[index] = None

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