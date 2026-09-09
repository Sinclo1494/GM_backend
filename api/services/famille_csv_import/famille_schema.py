from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
    boolean,
)

FAMILLE_SCHEMA = CsvSchema([
    CsvField(
        index=0,
        name="code_famille",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),
    CsvField(
        index=1,
        name="libelle_famille",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),
    CsvField(
        index=2,
        name="code_categorie_gm",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),
    CsvField(
        index=3,
        name="est_bloque",
        required=False,
        validator=boolean(),
    ),
])
