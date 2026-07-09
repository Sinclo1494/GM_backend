

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


def required(value: str):
    if value.strip() == "":
        return "Champ obligatoire."


def date(format: str):
    def validate(value: str):
        try:
            datetime.strptime(value.strip(), format)
        except ValueError:
            return f"Date invalide (format attendu : {format})."

    return validate


def datetime_format(format: str):
    def validate(value: str):
        if value.strip() == "":
            return None

        try:
            datetime.strptime(value.strip(), format)
        except ValueError:
            return f"Date/heure invalide (format attendu : {format})."

    return validate


def decimal(max_digits: int, decimal_places: int):
    def validate(value: str):

        value = value.strip().replace(",", ".")

        try:
            d = Decimal(value)
        except InvalidOperation:
            return "Nombre décimal invalide."

        if d < 0:
            return "La valeur doit être positive."

        sign, digits, exponent = d.as_tuple()

        decimals = -exponent if exponent < 0 else 0
        integers = len(digits) - decimals

        if decimals > decimal_places:
            return f"Maximum {decimal_places} décimale(s)."

        if integers + decimals > max_digits:
            return f"Maximum {max_digits} chiffres."

    return validate


def boolean():
    def validate(value: str):

        value = value.strip().lower()

        allowed = {
            "0",
            "1",
            "true",
            "false",
            "oui",
            "non",
            "",
        }

        if value not in allowed:
            return "Booléen invalide."

    return validate


def regex(pattern: str, message: str):
    compiled = re.compile(pattern)

    def validate(value: str):
        if not compiled.fullmatch(value.strip()):
            return message

    return validate


def combine(*validators):
    def validate(value: str):

        for validator in validators:
            error = validator(value)

            if error:
                return error

    return validate