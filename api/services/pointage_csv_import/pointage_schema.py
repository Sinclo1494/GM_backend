from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
    date,
    datetime_value,
    decimal,
    boolean,
)


POINTAGE_SCHEMA = CsvSchema([

    # ---------------------------------------------------------
    # Material
    # ---------------------------------------------------------

    CsvField(
        index=0,
        name="code_materiel",
        required=True,
        validator=combine(
            string(),
            max_length(50),  # Match Pointage/Affectation model max_length
        ),
    ),

    # ---------------------------------------------------------
    # Site
    # ---------------------------------------------------------

    CsvField(
        index=1,
        name="code_site",
        required=True,
        validator=combine(
            string(),
            max_length(50),  # Match actual model max_length
        ),
    ),

    # ---------------------------------------------------------
    # Affectation date
    # ---------------------------------------------------------

    CsvField(
        index=2,
        name="date_affectation",
        required=True,
        validator=date(
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ),
    ),

    # ---------------------------------------------------------
    # Rental rate
    # ---------------------------------------------------------

    CsvField(
        index=3,
        name="taux_location",
        required=True,
        validator=decimal(
            max_digits=20,
            decimal_places=6,
            positive=True,
        ),
    ),

    # ---------------------------------------------------------
    # Hours
    # ---------------------------------------------------------

    CsvField(
        index=4,
        name="heures_service",
        required=True,
        validator=decimal(
            max_digits=10,
            decimal_places=1,
            positive=True,
        ),
    ),

    CsvField(
        index=5,
        name="heures_chomage",
        required=True,
        validator=decimal(
            max_digits=10,
            decimal_places=1,
            positive=True,
        ),
    ),

    CsvField(
        index=6,
        name="heures_panne",
        required=True,
        validator=decimal(
            max_digits=10,
            decimal_places=1,
            positive=True,
        ),
    ),

    # ---------------------------------------------------------
    # Potential
    # ---------------------------------------------------------

    CsvField(
        index=7,
        name="potentiel",
        required=True,
        validator=decimal(
            max_digits=5,
            decimal_places=1,
            positive=True,
        ),
    ),

    # ---------------------------------------------------------
    # Month / accounting date
    # ---------------------------------------------------------

    CsvField(
        index=8,
        name="mmaa",
        required=True,
        validator=date(
            "%Y%m%d",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ),
    ),

    # ---------------------------------------------------------
    # Modification datetime
    # ---------------------------------------------------------

    CsvField(
        index=9,
        name="date_modification",
        required=False,
        validator=datetime_value(
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ),
    ),

    # ---------------------------------------------------------
    # Blocked
    # ---------------------------------------------------------

    CsvField(
        index=10,
        name="est_bloque",
        required=False,
        validator=boolean(),
    ),

    CsvField(
        index=11,
        name="montant_service",
        required=False,
        validator=decimal(
            max_digits=20,
            decimal_places=6,
            positive=True,
        ),
    ),
    CsvField(
        index=12,
        name="montant_chomage",
        required=False,
        validator=decimal(
            max_digits=20,
            decimal_places=6,
            positive=True,
        ),
    ),
    CsvField(
        index=13,
        name="montant_panne",
        required=False,
        validator=decimal(
            max_digits=20,
            decimal_places=6,
            positive=True,
        ),
    ),
])