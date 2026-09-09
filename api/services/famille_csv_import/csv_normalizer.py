import csv
import io


class CsvNormalizationError(Exception):
    pass


class CsvNormalizer:

    @staticmethod
    def normalize(uploaded_file, schema, mapping):

        if not isinstance(mapping, dict):
            raise CsvNormalizationError("Le mapping des colonnes est invalide.")

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
                    f"L'index de colonne ne peut pas être négatif : {index}."
                )

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

        try:
            uploaded_file.seek(0)
            raw_content = uploaded_file.read()
        except Exception as exc:
            raise CsvNormalizationError("Impossible de lire le fichier CSV.") from exc

        if not raw_content:
            raise CsvNormalizationError("Le fichier CSV est vide.")

        try:
            text = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CsvNormalizationError(
                "Impossible de lire l'encodage du fichier. "
                "Le fichier doit être encodé en UTF-8."
            ) from exc

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

        writer.writerow(expected_headers)

        try:
            for source_row in reader:
                if not source_row or not any(cell.strip() for cell in source_row):
                    continue

                source_row = [cell.strip() for cell in source_row]

                if source_row == list(expected_headers):
                    continue

                normalized_row = []

                for field in expected_headers:
                    value = ""

                    if field in reverse_mapping:
                        index = reverse_mapping[field]
                        if index < len(source_row):
                            value = source_row[index]

                    if field == "libelle_famille" and not value.strip():
                        value = "(Information manquante)"

                    normalized_row.append(value)

                writer.writerow(normalized_row)

        except csv.Error as exc:
            raise CsvNormalizationError(
                f"CSV mal formé à proximité de la ligne "
                f"{reader.line_num} : {exc}"
            ) from exc

        output.seek(0)
        return output
