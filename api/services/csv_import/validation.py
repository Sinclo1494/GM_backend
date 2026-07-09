from dataclasses import dataclass, asdict
from typing import Callable


@dataclass(slots=True)
class ValidationError:
    line: int | None
    field: str | None
    value: str | None
    message: str
    severity: str = "error"

    def to_dict(self):
        return asdict(self)


@dataclass(slots=True)
class CsvField:
    index: int
    name: str
    required: bool = True
    validator: Callable[[str], str | None] | None = None


class CsvSchema:
    """
    Describes the structure and validation rules of a CSV.
    """

    def __init__(self, fields: list[CsvField]):
        self.fields = fields

    @property
    def column_count(self):
        return len(self.fields)

    def validate_row(
        self,
        row: list[str],
        line_number: int,
        report,
    ) -> bool:

        valid = True

        for field in self.fields:

            value = row[field.index].strip()

            if field.required and value == "":
                report.add_error(
                    line=line_number,
                    field=field.name,
                    value=value,
                    message="Champ obligatoire.",
                )
                valid = False
                continue

            if value == "":
                continue

            if field.validator:

                error = field.validator(value)

                if error:
                    report.add_error(
                        line=line_number,
                        field=field.name,
                        value=value,
                        message=error,
                    )
                    valid = False

        return valid


class ValidationReport:

    def __init__(self):
        self.total_rows = 0
        self.valid_rows = 0
        self.invalid_rows = 0

        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    @property
    def success(self):
        return len(self.errors) == 0

    def increment_total(self):
        self.total_rows += 1

    def increment_valid(self):
        self.valid_rows += 1

    def increment_invalid(self):
        self.invalid_rows += 1

    def add_error(
        self,
        *,
        line=None,
        field=None,
        value=None,
        message,
    ):
        self.increment_invalid()

        self.errors.append(
            ValidationError(
                line=line,
                field=field,
                value=value,
                message=message,
            )
        )

    def add_warning(
        self,
        *,
        line=None,
        field=None,
        value=None,
        message,
    ):
        self.warnings.append(
            ValidationError(
                line=line,
                field=field,
                value=value,
                message=message,
                severity="warning",
            )
        )

    def to_dict(self):
        return {
            "success": self.success,
            "summary": {
                "total_rows": self.total_rows,
                "valid_rows": self.valid_rows,
                "invalid_rows": self.invalid_rows,
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }