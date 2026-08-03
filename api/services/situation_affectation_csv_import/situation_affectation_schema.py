from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
    date,
    datetime_value,
    boolean,
)


SITUATION_AFFECTATION_SCHEMA = CsvSchema([

    # ---------------------------------------------------------
    # Material
    # ---------------------------------------------------------

    CsvField(
        index=0,
        name="code_materiel",
        required=True,
        validator=combine(
            string(),
            max_length(50),
        ),
    ),

    # ---------------------------------------------------------
    # Affectation type
    # ---------------------------------------------------------

    CsvField(
        index=1,
        name="code_type_affectation",
        required=True,
        validator=combine(
            string(),
            max_length(50),
        ),
    ),

    # ---------------------------------------------------------
    # Situation type
    # ---------------------------------------------------------

    CsvField(
        index=2,
        name="code_type_situation",
        required=True,
        validator=combine(
            string(),
            max_length(50),
        ),
    ),

    # ---------------------------------------------------------
    # Site
    # ---------------------------------------------------------

    CsvField(
        index=3,
        name="code_site",
        required=True,
        validator=combine(
            string(),
            max_length(50),
        ),
    ),

    # ---------------------------------------------------------
    # Affectation date
    # ---------------------------------------------------------

    CsvField(
        index=4,
        name="date_affectation",
        required=True,
        validator=datetime_value(
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ),
    ),

    # ---------------------------------------------------------
    # Material state
    # ---------------------------------------------------------

    CsvField(
        index=5,
        name="code_type_etat_materiel",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Modification datetime
    # ---------------------------------------------------------

    CsvField(
        index=6,
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
        index=7,
        name="est_bloque",
        required=False,
        validator=boolean(),
    ),

    # ---------------------------------------------------------
    # Situation date
    # ---------------------------------------------------------

    CsvField(
        index=8,
        name="date_situation",
        required=True,
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

])