from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
    boolean,
)

SOUS_FAMILLE_SCHEMA = CsvSchema(
    [
        # ---------------------------------------------------------
        # Code Type Marque
        # ---------------------------------------------------------
        CsvField(
            index=0,
            name="code_sous_famille",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),
        # ---------------------------------------------------------
        # Libelle Type Marque
        # ---------------------------------------------------------
        CsvField(
            index=1,
            name="libelle_sous_famille",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),
        # ---------------------------------------------------------
        # Code Marque
        # ---------------------------------------------------------
        CsvField(
            index=2,
            name="code_famille_materiel",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),
        # ---------------------------------------------------------
        # Blocked
        # ---------------------------------------------------------
        CsvField(
            index=3,
            name="est_bloque",
            required=False,
            validator=boolean(),
        ),
    ]
)
