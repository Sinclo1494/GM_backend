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


GRAND_MATERIEL_SCHEMA = CsvSchema([

    # ---------------------------------------------------------
    # Material code
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
    # Designation
    # ---------------------------------------------------------

    CsvField(
        index=1,
        name="designation",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Serial number
    # ---------------------------------------------------------

    CsvField(
        index=2,
        name="num_serie",
        required=False,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------

    CsvField(
        index=3,
        name="immatriculation",
        required=False,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Acquisition date
    # ---------------------------------------------------------

    CsvField(
        index=4,
        name="date_acquisition",
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

    # ---------------------------------------------------------
    # Acquisition value
    # ---------------------------------------------------------

    CsvField(
        index=5,
        name="valeur_acquisition",
        required=True,
        validator=decimal(
            max_digits=20,
            decimal_places=6,
            positive=True,
        ),
    ),

    # ---------------------------------------------------------
    # Replacement value
    # ---------------------------------------------------------

    CsvField(
        index=6,
        name="valeur_remplacement",
        required=False,
        validator=decimal(
            max_digits=20,
            decimal_places=6,
            positive=True,
        ),
    ),

    # ---------------------------------------------------------
    # Depreciation rate
    # ---------------------------------------------------------

    CsvField(
        index=7,
        name="taux_amortissement",
        required=False,
        validator=decimal(
            max_digits=20,
            decimal_places=6,
            positive=True,
        ),
    ),

    # ---------------------------------------------------------
    # Power
    # ---------------------------------------------------------

    CsvField(
        index=8,
        name="puissance_materiel",
        required=False,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Sub-family
    # ---------------------------------------------------------

    CsvField(
        index=9,
        name="code_sous_famille_materiel",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Brand / Type
    # ---------------------------------------------------------

    CsvField(
        index=10,
        name="code_type_marque",
        required=False,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    # ---------------------------------------------------------
    # Blocked
    # ---------------------------------------------------------

    CsvField(
        index=11,
        name="est_bloque",
        required=False,
        validator=boolean(),
    ),

    # ---------------------------------------------------------
    # Filiale
    # ---------------------------------------------------------

    CsvField(
        index=12,
        name="code_filiale_g",
        required=True,
        validator=combine(
            string(),
            max_length(50),
        ),
    ),

    # ---------------------------------------------------------
    # Modification date
    # ---------------------------------------------------------

    CsvField(
        index=13,
        name="date_modification",
        required=False,
        validator=datetime_value(
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ),
    ),

])