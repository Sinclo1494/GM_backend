from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
)


MATERIEL_FILIALE_SCHEMA = CsvSchema([

    # ---------------------------------------------------------
    # Material code
    #
    # Must already exist in the database.
    # ---------------------------------------------------------

    CsvField(
        index=0,
        name="code_materiel",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Filiale
    #
    # Target filiale of the existing material.
    # ---------------------------------------------------------

    CsvField(
        index=1,
        name="code_filiale_g",
        required=True,
        validator=combine(
            string(),
            max_length(50),
        ),
    ),

])