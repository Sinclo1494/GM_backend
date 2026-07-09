# pointage_schema.py

from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    date,
    datetime_format,
    decimal,
    boolean,
)
from datetime import datetime


def date(*formats: str):
    """
    Accept one or more date/datetime formats.

    Example:
        date("%Y-%m-%d", "%d/%m/%Y")
        date("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
    """

    def validate(value: str):
        value = value.strip()

        for fmt in formats:
            try:
                datetime.strptime(value, fmt)
                return None
            except ValueError:
                pass

        accepted = ", ".join(formats)
        return f"Date invalide. Formats acceptés : {accepted}."

    return validate


POINTAGE_SCHEMA = CsvSchema(
    [
        CsvField(
            0,
            "code_materiel",
        ),
        CsvField(
            1,
            "code_site",
        ),
        CsvField(
            2,
            "date_affectation",
            validator=date(
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
            ),
        ),
        CsvField(
            3,
            "taux_location",
            validator=combine(
                decimal(max_digits=20, decimal_places=6),
            ),
        ),
        CsvField(
            4,
            "heures_service",
            validator=combine(
                decimal(max_digits=10, decimal_places=1),
            ),
        ),
        CsvField(
            5,
            "heures_chomage",
            validator=combine(
                decimal(max_digits=10, decimal_places=1),
            ),
        ),
        CsvField(
            6,
            "heures_panne",
            validator=combine(
                decimal(max_digits=10, decimal_places=1),
            ),
        ),
        CsvField(
            7,
            "potentiel",
            validator=combine(
                decimal(max_digits=5, decimal_places=1),
            ),
        ),
        CsvField(
            8,
            "mmaa",
            validator=date(
                "%Y%m%d",
                "%Y-%m-%d",
                "%m/%Y",
                "%d/%m/%Y",
            ),
        ),
        CsvField(
            9,
            "date_modification",
            required=False,
            validator=date(
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
            ),
        ),
        CsvField(
            10,
            "est_bloque",
            validator=boolean(),
        ),
        CsvField(
            11,
            "montant_service",
            required=False,
            validator=combine(
                decimal(max_digits=20, decimal_places=6),
            ),
        ),
        CsvField(
            12,
            "montant_chomage",
            required=False,
            validator=combine(
                decimal(max_digits=20, decimal_places=6),
            ),
        ),
        CsvField(
            13,
            "montant_panne",
            required=False,
            validator=combine(
                decimal(max_digits=20, decimal_places=6),
            ),
        ),
    ]
)
