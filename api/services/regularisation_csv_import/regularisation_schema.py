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


REGULARISATION_GM_SCHEMA = CsvSchema([

    CsvField(
        index=0,
        name="code_site",
        required=True,
        validator=combine(
            string(),
            max_length(100),
        ),
    ),

    CsvField(
        index=1,
        name="mmaa",
        required=True,
        validator=date(
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ),
    ),

    CsvField(
        index=2,
        name="montant_regularisation",
        required=True,
        validator=decimal(
            max_digits=20,
            decimal_places=4,
            positive=True,
        ),
    ),

    CsvField(
        index=3,
        name="observation",
        required=False,
        validator=combine(
            string(),
            max_length(1000),
        ),
    ),

    CsvField(
        index=4,
        name="est_bloque",
        required=False,
        validator=boolean(),
    ),

    CsvField(
        index=5,
        name="date_modification",
        required=False,
        validator=datetime_value(
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ),
    ),

])
