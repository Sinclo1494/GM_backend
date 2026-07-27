from .validation import CsvField, CsvSchema
from .validators import (
    combine,
    string,
    max_length,
    boolean,
    integer,
    date,
)

SITE_SCHEMA = CsvSchema(
    [
        # ---------------------------------------------------------
        # Code Site
        # ---------------------------------------------------------
        CsvField(
            index=0,
            name="code_site",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Code Filiale
        # ---------------------------------------------------------
        CsvField(
            index=1,
            name="code_filiale",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Code Region
        # ---------------------------------------------------------
        CsvField(
            index=2,
            name="code_region",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Libelle Site
        # ---------------------------------------------------------
        CsvField(
            index=3,
            name="libelle_site",
            required=True,
            validator=combine(
                string(),
                max_length(200),
            ),
        ),

        # ---------------------------------------------------------
        # Code Agence
        # ---------------------------------------------------------
        CsvField(
            index=4,
            name="code_agence",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Type Site
        # ---------------------------------------------------------
        CsvField(
            index=5,
            name="type_site",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Code Division
        # ---------------------------------------------------------
        CsvField(
            index=6,
            name="code_division",
            required=False,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Numero SS Employeur
        # ---------------------------------------------------------
        CsvField(
            index=7,
            name="numero_ss_employeur",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Code Commune Site
        # ---------------------------------------------------------
        CsvField(
            index=8,
            name="code_commune_site",
            required=True,
            validator=combine(
                string(),
                max_length(100),
            ),
        ),

        # ---------------------------------------------------------
        # Jour Cloture Mouv RH Paie
        # ---------------------------------------------------------
        CsvField(
            index=9,
            name="jour_cloture_mouv_RH_paie",
            required=False,
            validator=integer(
                min_value=1,
                max_value=31,
            ),
        ),

        # ---------------------------------------------------------
        # Date Ouverture Site
        # ---------------------------------------------------------
        CsvField(
            index=10,
            name="date_ouverture_site",
            required=False,
            validator=date(),
        ),

        # ---------------------------------------------------------
        # Date Cloture Site
        # ---------------------------------------------------------
        CsvField(
            index=11,
            name="date_cloture_site",
            required=False,
            validator=date(),
        ),

        # ---------------------------------------------------------
        # Est Bloque
        # ---------------------------------------------------------
        CsvField(
            index=12,
            name="est_bloque",
            required=False,
            validator=boolean(),
        ),
    ]
)