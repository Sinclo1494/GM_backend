import csv
import io


class CsvNormalizer:

    @staticmethod
    def normalize(uploaded_file, schema, mapping, filiale=None):

        text = uploaded_file.read().decode("utf-8")

        reader = csv.reader(
            io.StringIO(text),
            delimiter=";"
        )

        rows = list(reader)

        expected_headers = [
            field.name
            for field in schema.fields
        ]

        reverse_mapping = {
            value: int(key)
            for key, value in mapping.items()
        }

        filiale = filiale.strip() if filiale else None

        code_site_index = (
            expected_headers.index("code_site")
            if "code_site" in expected_headers
            else None
        )
        output = io.StringIO()

        writer = csv.writer(
            output,
            delimiter=";"
        )

        writer.writerow(expected_headers)

        for row in rows:
            normalized_row = [
                row[reverse_mapping[field]]
                if field in reverse_mapping
                else ""
                for field in expected_headers
            ]
            if filiale and code_site_index is not None:
                code_site = normalized_row[code_site_index]

                if code_site:
                    code_site = code_site.strip()
                    code_site = "/".join(
                        part.strip()
                        for part in code_site.split("/")
                    )
                    if "/" not in code_site:
                        code_site = f"{filiale}/{code_site}"

                    normalized_row[code_site_index] = code_site
            
            writer.writerow(normalized_row)

        output.seek(0)

        return output