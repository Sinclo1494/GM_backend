from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
    boolean,
)

CATEGORIE_GM_SCHEMA = CsvSchema([
    CsvField(
        index=0,
        name="code_categorie",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),
    CsvField(
        index=1,
        name="libelle_categorie",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),
    CsvField(
        index=2,
        name="est_bloque",
        required=False,
        validator=boolean(),
    ),
])
