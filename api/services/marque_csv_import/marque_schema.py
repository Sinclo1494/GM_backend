from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
    boolean,
)


MARQUE_MATERIEL_SCHEMA = CsvSchema([

    # ---------------------------------------------------------
    # Code Marque
    # ---------------------------------------------------------

    CsvField(
        index=0,
        name="code_marque",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Libelle Marque
    # ---------------------------------------------------------

    CsvField(
        index=1,
        name="libelle_marque",
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
        index=2,
        name="est_bloque",
        required=False,
        validator=boolean(),
    ),

    

])