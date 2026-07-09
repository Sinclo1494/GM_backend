from datetime import timedelta,date
from collections import defaultdict

from django.db.models import (
    F,
    Window,
    Value,
    Case,
    When,
    DateField,
    ExpressionWrapper,
    Count,
    Avg,
    Sum,
    Q,
    IntegerField
)
from django.db.models.functions import Lead, Cast, Greatest, ExtractYear, Now, RowNumber
from api.models import Grand_Materiel, Situation_Materiel, Affectation_Materiel
from api.serializers import SituationMaterielSerializer


class AnalyseQuantitative:

    @staticmethod
    def get_situations(
        code_filiale,
        date_debut,
        date_fin,
    ):
        situations = Situation_Materiel.objects.filter(
            date_situation__date__lte=date_fin,
        )

        situations = situations.annotate(
            next_date=Window(
                expression=Lead("date_situation"),
                partition_by=[F("affectation_id__code_materiel")],
                order_by=[
                    F("date_situation").asc(),
                    F("id").asc(),
                ],
            )
        )

        situations = situations.annotate(
            date_deb_affectation=Greatest(
                Cast("date_situation", output_field=DateField()),
                Value(date_debut, output_field=DateField()),
                output_field=DateField(),
            )
        )

        situations = situations.annotate(
            date_fin_affectation=Case(
                When(
                    next_date__date__range=(date_debut, date_fin),
                    then=ExpressionWrapper(
                        Cast(F("next_date"), DateField()) - Value(timedelta(days=1)),
                        output_field=DateField(),
                    ),
                ),
                When(
                    next_date__isnull=True,
                    then=Value(date_fin, output_field=DateField()),
                ),
                default=F("date_deb_affectation"),
                output_field=DateField(),
            )
        )
        situations = situations.filter(
            Q(date_deb_affectation__lte=date_fin),
            Q(date_fin_affectation__gte=date_debut),
        )
        situations = situations.annotate(
            code_materiel=F("affectation_id__code_materiel__code_materiel"),
            code_filiale=F(
                "affectation_id__code_materiel__code_filiale_g__code_filiale"
            ),
            libelle_filiale=F(
                "affectation_id__code_materiel__code_filiale_g__libelle_filiale"
            ),
            code_sous_famille=F(
                "affectation_id__code_materiel__code_sous_famille_materiel"
            ),
            libelle_sous_famille=F(
                "affectation_id__code_materiel__code_sous_famille_materiel__libelle_sous_famille"
            ),
            code_categorie=F(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_categorie_gm__code_categorie"
            ),
            libelle_categorie=F(
                "affectation_id__code_materiel__code_sous_famille_materiel__code_famille_materiel__code_categorie_gm__libelle_categorie"
            ),
            date_acquisition=F("affectation_id__code_materiel__date_acquisition"),
            prenable=F("affectation_id__prenable"),
            code_type_situation=F("type_situation_id__code_type_situation"),
            libelle_type_situation=F("type_situation_id__libelle_type_situation"),
            code_type_affectation=F(
                "type_situation_id__code_type_affectation__code_type_affectation"
            ),
            libelle_type_affectation=F(
                "type_situation_id__code_type_affectation__libelle_type_affectation"
            ),
        )

        situations = situations.filter(
            prenable=True,
            code_filiale=code_filiale,
        ).exclude(code_type_affectation__in=["06", "07"])

        situations = situations.annotate(
            rn=Window(
                expression=RowNumber(),
                partition_by=[F("affectation_id__code_materiel")],
                order_by=[
                    F("date_deb_affectation").desc(),
                    F("date_situation").desc(),
                    F("id").desc(),
                ],
            )
        ).filter(rn=1)

        situations = situations.annotate(
            age=ExpressionWrapper(
                ExtractYear(Now()) - ExtractYear(F("date_acquisition")),
                output_field=IntegerField(),
            )
        )

        situations = situations.values(
            "code_sous_famille",
            "libelle_sous_famille",
            "code_categorie",
            "libelle_categorie",
            "code_filiale",
            "libelle_filiale",
            "code_type_affectation",
            "libelle_type_affectation",
            "code_type_situation",
            "libelle_type_situation",
            "code_materiel",
            "age",
        )

        result = {}

        for s in situations:
            key = (
                s["code_sous_famille"],
                s["libelle_sous_famille"],
            )

            if key not in result:
                result[key] = {
                    "code_sous_famille": s["code_sous_famille"],
                    "libelle_sous_famille": s["libelle_sous_famille"],
                    "code_categorie": s["code_categorie"],
                    "libelle_categorie": s["libelle_categorie"],

                    "nbr": 0,
                    "age_total": 0,

                    "exploitation": {
                        "en_service": 0,
                        "en_chomage": 0,
                        "en_panne": 0,
                    },

                    "immobilise": {
                        "en_chomage": 0,
                        "en_reparation": 0,
                        "autre": 0,
                    },
                    "reparation": {
                        "autre": 0,
                        "ALREM": 0,
                    },
                }

            row = result[key]

            row["nbr"] += 1
            row["age_total"] += s["age"] or 0

            affectation = s["code_type_affectation"]
            situation = s["code_type_situation"]

            # Exploitation
            if affectation == "01":
                if situation == "01":
                    row["exploitation"]["en_service"] += 1
                elif situation == "02":
                    row["exploitation"]["en_chomage"] += 1
                elif situation == "03":
                    row["exploitation"]["en_panne"] += 1

            # Immobilisé
            elif affectation == "04":
                if situation == "02":
                    row["immobilise"]["en_chomage"] += 1
                elif situation == "04":
                    row["immobilise"]["en_reparation"] += 1
                elif situation == "05":
                    row["immobilise"]["autre"] += 1
            #Réparation
            elif affectation == "02":
                if situation == "05":
                    row["reparation"]["autre"] += 1
                elif situation == "06":
                    row["reparation"]["ALREM"] += 1
        final_result = []

        for row in result.values():
            row["age_moyen"] = (
                row["age_total"] / row["nbr"]
                if row["nbr"]
                else 0
            )

            final_result.append(row)

        final_result.sort(key=lambda x: x["code_sous_famille"])
        return final_result

class AnalyseQuantitativeResume:

    @staticmethod
    def get_situations_resume(
        code_filiale,
        date_debut,
        date_fin,
    ):
        rows = AnalyseQuantitative.get_situations(
            code_filiale,
            date_debut,
            date_fin,
        )

        nbr_total = 0
        devider = 0
        age_total = 0

        exp_service = 0
        exp_chomage = 0
        exp_panne = 0

        imm_chomage = 0
        imm_reparation = 0
        imm_autre = 0

        rep_ALREM = 0
        rep_autre = 0

        for row in rows:
            nbr_total += row["nbr"]
            age_total += row["age_total"]
            if age_total > 0:
                devider += row["nbr"]

            exp_service += row["exploitation"]["en_service"]
            exp_chomage += row["exploitation"]["en_chomage"]
            exp_panne += row["exploitation"]["en_panne"]

            imm_chomage += row["immobilise"]["en_chomage"]
            imm_reparation += row["immobilise"]["en_reparation"]
            imm_autre += row["immobilise"]["autre"]

            rep_ALREM += row["reparation"]["ALREM"]
            rep_autre += row["reparation"]["autre"]

        age_moyen = age_total / devider if devider else 0

        return {
            "nombre_totale": nbr_total,
            "age_moyen": int(age_moyen),
            "exploitation": {
                "en_service": exp_service,
                "en_chomage": exp_chomage,
                "en_panne": exp_panne,
            },
            "immobilises": {
                "en_chomage": imm_chomage,
                "en_reparation": imm_reparation,
                "autre": imm_autre,
            },
            "reparation_externe": {
                "ALREM": rep_ALREM,
                "autre": rep_autre,
            },
        }