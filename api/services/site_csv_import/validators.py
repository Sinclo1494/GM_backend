from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from .validation import ValidationResult


# ---------------------------------------------------------
# Combine validators
# ---------------------------------------------------------

def combine(*validators):

    def validate(value):

        current = value

        for validator in validators:

            result = validator(current)

            if not result.valid:
                return result

            current = result.value

        return ValidationResult(
            valid=True,
            value=current,
        )

    return validate


# ---------------------------------------------------------
# String
# ---------------------------------------------------------

def string(strip=True):

    def validate(value):

        if value is None:
            value = ""

        value = str(value)

        if strip:
            value = value.strip()

        return ValidationResult(
            valid=True,
            value=value,
        )

    return validate


# ---------------------------------------------------------
# Maximum string length
# ---------------------------------------------------------

def max_length(length):

    def validate(value):

        if value is None:
            return ValidationResult(
                valid=True,
                value=value,
            )

        if len(value) > length:
            return ValidationResult(
                valid=False,
                message=f"Maximum {length} caractère(s).",
            )

        return ValidationResult(
            valid=True,
            value=value,
        )

    return validate


# ---------------------------------------------------------
# Choice
# ---------------------------------------------------------

def choice(*choices, case_sensitive=True):

    allowed_values = set(choices)

    if not case_sensitive:
        normalized_choices = {
            str(value).lower(): value
            for value in choices
        }

    def validate(value):

        if case_sensitive:

            if value not in allowed_values:
                return ValidationResult(
                    valid=False,
                    message=(
                        "Valeur invalide. "
                        f"Valeurs autorisées : {', '.join(map(str, choices))}."
                    ),
                )

            return ValidationResult(
                valid=True,
                value=value,
            )

        normalized_value = str(value).lower()

        if normalized_value not in normalized_choices:
            return ValidationResult(
                valid=False,
                message=(
                    "Valeur invalide. "
                    f"Valeurs autorisées : {', '.join(map(str, choices))}."
                ),
            )

        return ValidationResult(
            valid=True,
            value=normalized_choices[normalized_value],
        )

    return validate


# ---------------------------------------------------------
# Datetime
# ---------------------------------------------------------

def datetime_value(*formats):

    def validate(value):

        if value is None:
            return ValidationResult(
                valid=False,
                message="Date et heure invalides.",
            )

        value = str(value).strip()

        for fmt in formats:

            try:
                parsed = datetime.strptime(value, fmt)

                return ValidationResult(
                    valid=True,
                    value=parsed,
                )

            except ValueError:
                continue

        return ValidationResult(
            valid=False,
            message="Date et heure invalides.",
        )

    return validate


# ---------------------------------------------------------
# Date only
# ---------------------------------------------------------

def date(*formats):

    def validate(value):

        if value is None:
            return ValidationResult(
                valid=False,
                message="Date invalide.",
            )

        value = str(value).strip()

        for fmt in formats:

            try:
                parsed = datetime.strptime(value, fmt).date()

                return ValidationResult(
                    valid=True,
                    value=parsed,
                )

            except ValueError:
                continue

        return ValidationResult(
            valid=False,
            message="Date invalide.",
        )

    return validate

# ---------------------------------------------------------
# Integer
# ---------------------------------------------------------

def integer(
    positive=True,
    min_value=None,
    max_value=None,
):

    def validate(value):

        if value is None:

            return ValidationResult(
                valid=False,
                message="Nombre entier invalide.",
            )

        value = str(value).strip()

        try:

            number = int(value)

        except (TypeError, ValueError):

            return ValidationResult(
                valid=False,
                message="Nombre entier invalide.",
            )

        if positive and number < 0:

            return ValidationResult(
                valid=False,
                message="La valeur doit être positive.",
            )

        if (
            min_value is not None
            and number < min_value
        ):

            return ValidationResult(
                valid=False,
                message=(
                    f"La valeur minimale autorisée est "
                    f"{min_value}."
                ),
            )

        if (
            max_value is not None
            and number > max_value
        ):

            return ValidationResult(
                valid=False,
                message=(
                    f"La valeur maximale autorisée est "
                    f"{max_value}."
                ),
            )

        return ValidationResult(
            valid=True,
            value=number,
        )

    return validate

# ---------------------------------------------------------
# Decimal
# ---------------------------------------------------------

def decimal(
    max_digits,
    decimal_places,
    positive=True,
    min_value=None,
    max_value=None,
):

    min_decimal = (
        Decimal(str(min_value))
        if min_value is not None
        else None
    )

    max_decimal = (
        Decimal(str(max_value))
        if max_value is not None
        else None
    )

    def validate(value):

        if value is None:
            return ValidationResult(
                valid=False,
                message="Nombre décimal invalide.",
            )

        value = str(value).strip().replace(",", ".")

        try:
            d = Decimal(value)

        except (InvalidOperation, ValueError):

            return ValidationResult(
                valid=False,
                message="Nombre décimal invalide.",
            )

        # Reject NaN, Infinity and -Infinity
        if not d.is_finite():

            return ValidationResult(
                valid=False,
                message="Le nombre doit être une valeur finie.",
            )

        if positive and d < 0:

            return ValidationResult(
                valid=False,
                message="La valeur doit être positive.",
            )

        if min_decimal is not None and d < min_decimal:

            return ValidationResult(
                valid=False,
                message=(
                    f"La valeur minimale autorisée est "
                    f"{min_decimal}."
                ),
            )

        if max_decimal is not None and d > max_decimal:

            return ValidationResult(
                valid=False,
                message=(
                    f"La valeur maximale autorisée est "
                    f"{max_decimal}."
                ),
            )

        # DecimalField-compatible precision validation
        sign, digits, exponent = d.as_tuple()

        if exponent >= 0:
            decimal_count = 0
            integer_count = len(digits) + exponent
        else:
            decimal_count = -exponent
            integer_count = max(
                len(digits) - decimal_count,
                0,
            )

        if decimal_count > decimal_places:

            return ValidationResult(
                valid=False,
                message=(
                    f"Maximum {decimal_places} "
                    f"décimale(s)."
                ),
            )

        if integer_count > max_digits - decimal_places:

            return ValidationResult(
                valid=False,
                message=(
                    f"Maximum "
                    f"{max_digits - decimal_places} "
                    f"chiffre(s) avant la virgule."
                ),
            )

        if integer_count + decimal_count > max_digits:

            return ValidationResult(
                valid=False,
                message=f"Maximum {max_digits} chiffres.",
            )

        return ValidationResult(
            valid=True,
            value=d,
        )

    return validate


# ---------------------------------------------------------
# Boolean
# ---------------------------------------------------------

def boolean():

    mapping = {
        "1": True,
        "true": True,
        "oui": True,

        "0": False,
        "false": False,
        "non": False,

        "": False,
    }

    def validate(value):

        if value is None:
            value = ""

        value = str(value).strip().lower()

        if value not in mapping:

            return ValidationResult(
                valid=False,
                message="Booléen invalide.",
            )

        return ValidationResult(
            valid=True,
            value=mapping[value],
        )

    return validate


# ---------------------------------------------------------
# Regex
# ---------------------------------------------------------

def regex(pattern, message):

    compiled = re.compile(pattern)

    def validate(value):

        if value is None:
            value = ""

        value = str(value).strip()

        if not compiled.fullmatch(value):

            return ValidationResult(
                valid=False,
                message=message,
            )

        return ValidationResult(
            valid=True,
            value=value,
        )

    return validate