import csv
import io

from .csv_normalizer import CsvNormalizer
from .validation import ValidationReport, CsvSchema


class CsvValidator:
    """
    Generic CSV validator.

    Responsibilities:
    - Decode the uploaded file
    - Parse the CSV
    - Ignore empty rows
    - Validate the number of columns
    - Validate each field according to the schema
    """

    def __init__(
        self,
        uploaded_file,
        schema: CsvSchema,
        mapping=None,
        delimiter=";",
        encoding="utf-8",
    ):
        if not isinstance(schema, CsvSchema):
            raise TypeError("schema must be an instance of CsvSchema")

        self.schema = schema
        self.encoding = encoding
        self.delimiter = delimiter

        if mapping is not None:
            self.file = CsvNormalizer.normalize(
                uploaded_file=uploaded_file,
                schema=schema,
                mapping=mapping,
            )
        else:
            uploaded_file.seek(0)
            self.file = uploaded_file

    def validate(self):

        report = ValidationReport()

        try:

            # CsvNormalizer returns a StringIO,
            # uploaded files are binary streams.
            if isinstance(self.file, io.StringIO):
                text_stream = self.file
                text_stream.seek(0)
            else:
                self.file.seek(0)

                text_stream = io.TextIOWrapper(
                    self.file,
                    encoding=self.encoding,
                    newline="",
                )

            reader = csv.reader(
                text_stream,
                delimiter=self.delimiter,
            )

            expected_headers = [
                field.name
                for field in self.schema.fields
            ]

            headers = next(reader, None)

            if headers != expected_headers:

                report.add_error(
                    message="Les en-têtes du fichier sont invalides."
                )

                return report

            for line_number, row in enumerate(reader, start=1):

                # Ignore empty rows
                if not row or all(cell.strip() == "" for cell in row):
                    continue

                report.increment_total()

                # Validate column count
                if len(row) != self.schema.column_count:

                    report.add_error(
                        line=line_number,
                        message=(
                            f"{len(row)} colonnes détectées "
                            f"({self.schema.column_count} attendues)."
                        ),
                    )

                    continue

                # Validate row
                if self.schema.validate_row(
                    row=row,
                    line_number=line_number,
                    report=report,
                ):
                    report.increment_valid()

        except UnicodeDecodeError:

            report.add_error(
                message="Le fichier n'est pas encodé en UTF-8.",
            )

        except csv.Error as e:

            report.add_error(
                message=f"Erreur de lecture du fichier CSV : {e}",
            )

        return report