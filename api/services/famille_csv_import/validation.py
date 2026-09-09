from dataclasses import dataclass, asdict
from typing import Any, Callable


@dataclass(slots=True)
class ValidationError:
    line: int | None
    field: str | None
    value: Any
    message: str
    severity: str = "error"

    def to_dict(self):
        return asdict(self)


@dataclass(slots=True)
class ValidationResult:
    valid: bool = True
    value: Any = None
    message: str | None = None


@dataclass(slots=True)
class CsvField:
    index: int
    name: str
    required: bool = True
    validator: Callable[[Any], ValidationResult] | None = None


class CsvSchema:

    def __init__(self, fields: list[CsvField]):
        self.fields = fields

    @property
    def column_count(self):
        return len(self.fields)

    @property
    def headers(self):
        return [
            field.name
            for field in self.fields
        ]

    @property
    def input_headers(self):
        return self.headers

    def validate_row(
        self,
        row: list[str],
        line_number: int,
        report,
    ) -> dict | None:

        cleaned = {}

        for field in self.fields:

            if field.index >= len(row):
                raw = ""
            else:
                raw = row[field.index].strip()

            if field.required and raw == "":
                report.add_error(
                    line=line_number,
                    field=field.name,
                    value=raw,
                    message="Champ obligatoire.",
                )
                continue

            if raw == "":
                cleaned[field.name] = None
                continue

            if field.validator is None:
                cleaned[field.name] = raw
                continue

            result = field.validator(raw)

            if not result.valid:
                report.add_error(
                    line=line_number,
                    field=field.name,
                    value=raw,
                    message=result.message or "Valeur invalide.",
                )
                continue

            cleaned[field.name] = result.value

        return cleaned


class ValidationReport:

    def __init__(self, validation_id: str | None = None):
        self.validation_id = validation_id
        self.total_rows = 0
        self.valid_rows = 0
        self.invalid_rows = 0
        self.skipped = 0
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []
        self.rows: list[dict] = []

    @property
    def success(self):
        return len(self.errors) == 0

    def increment_total(self):
        self.total_rows += 1

    def increment_valid(self):
        self.valid_rows += 1

    def increment_invalid(self):
        self.invalid_rows += 1

    def increment_skipped(self):
        self.skipped += 1

    def add_row(self, row: dict):
        self.rows.append(row)
        self.increment_valid()

    def add_error(
        self,
        *,
        line=None,
        field=None,
        value=None,
        message,
    ):
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
        result = {
            "success": self.success,
            "summary": {
                "total_rows": self.total_rows,
                "valid_rows": self.valid_rows,
                "invalid_rows": self.invalid_rows,
                "skipped_rows": self.skipped,
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
            "errors": [
                error.to_dict()
                for error in self.errors
            ],
            "warnings": [
                warning.to_dict()
                for warning in self.warnings
            ],
        }

        if self.validation_id is not None:
            result["validation_id"] = self.validation_id

        return result
