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

# Type_Affectation codes that take a material out of the parc. "NON FOURNIE" is
# one of those codes, not a libelle.
EXCLUDED_TYPES_AFFECTATION = ("06", "07", "08", "NON FOURNIE")


class AnalyseQuantitative:

    @staticmethod
    def get_situations(
        code_filiale,
        date_debut,
        date_fin,
    ):
        """Situation of every material *in force* during ``[date_debut, date_fin]``.

        The period is a window, not a filter on the situation rows: a situation
        recorded *before* ``date_debut`` that has no successor inside the period
        is the material's state for the whole period (carry-forward), and only a
        successor located inside the period supersedes it.

        Every ordering is done on business dates -- ``date_situation`` inside an
        affectation, ``date_situation`` then ``date_affectation`` to pick the
        affectation of a material -- never on the insert id or on the ``.001`` /
        ``.002`` suffix of ``code_affectation``, which is not chronological once
        affectations are closed and re-opened. The primary key is only kept as a
        last-resort tiebreak for rows sharing the exact same timestamp.

        The subsidiary is the *affectation's* subsidiary
        (``Affectation_Materiel.code_filiale_mere``), never the materiel's
        ``code_filiale_g``: the two disagree as soon as a materiel is
        transferred, and the analysis reports the parc as operated by a
        subsidiary, that is per affectation. Reading it from the materiel both
        dropped the affectations sitting in another subsidiary and attributed a
        materiel to a subsidiary that does not hold it any more -- e.g.
        ``A01020072`` is ``code_filiale_g = M`` while most of its affectations
        are ``G``. A materiel affected in two subsidiaries contributes one row
        to each of the two subsidiary reports.

        The 06 / 07 / 08 / NON FOURNIE affectations are excluded on the row
        retained for each material, once the in-force situation is known, so a
        material whose latest state is one of them leaves the parc instead of
        falling back on the predecessor that situation superseded. That
        exclusion therefore happens while aggregating, not in the queryset: a
        filter on the annotated `code_type_affectation` is folded into the inner
        WHERE of the window query and would run before `ROW_NUMBER()`.
        """
        situations = Situation_Materiel.objects.filter(
            date_situation__date__lte=date_fin,
        )

        situations = situations.annotate(
            code_materiel=F("affectation_id__code_materiel__code_materiel"),
            code_affectation=F("affectation_id__code_affectation"),
            code_filiale=F("affectation_id__code_filiale_mere__code_filiale"),
            libelle_filiale=F(
                "affectation_id__code_filiale_mere__libelle_filiale"
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
            code_filiale=code_filiale,
        )

        # `next_date` chains the situations of a *single* affectation: a material
        # affected twice (....001 then ....002) must not let a situation of the
        # new affectation close the interval of a situation belonging to the
        # previous one, otherwise the end of the interval is attributed to the
        # wrong affectation / site. No situation is discarded before this point,
        # 06/07/08 and NON FOURNIE included: one of them must still close the
        # interval of the situation it supersedes.
        situations = situations.annotate(
            next_date=Window(
                expression=Lead("date_situation"),
                partition_by=[F("affectation_id")],
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

        # `default=date_fin` is the carry-forward rule: when the situation has
        # no successor inside the period -- no next situation at all, or the
        # next one predating `date_debut` -- it stays in force until the end of
        # the period. Without it the interval collapsed onto `date_debut`
        # itself, which made the period filter drop every material whose
        # successor was dated exactly on the first day of the month.
        situations = situations.annotate(
            date_fin_affectation=Case(
                When(
                    next_date__date__range=(date_debut, date_fin),
                    then=ExpressionWrapper(
                        Cast(F("next_date"), DateField()) - Value(timedelta(days=1)),
                        output_field=DateField(),
                    ),
                ),
                default=Value(date_fin, output_field=DateField()),
                output_field=DateField(),
            )
        )
        situations = situations.filter(
            Q(date_deb_affectation__lte=date_fin),
            Q(date_fin_affectation__gte=date_debut),
        )

        # One row per material: the situation in force at the end of the period
        # (most recent `date_situation`), attributed to the most recent
        # `date_affectation` when several affectations carry a situation on the
        # same day.
        situations = situations.annotate(
            rn=Window(
                expression=RowNumber(),
                partition_by=[F("affectation_id__code_materiel")],
                order_by=[
                    F("date_situation").desc(),
                    F("affectation_id__date_affectation").desc(),
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
            "code_affectation",
            "age",
        )

        result = {}

        for s in situations:
            # Parc exclusion on the row *retained* for the material, so it can
            # only be applied here: an `exclude()` on the `code_type_affectation`
            # annotation is folded into the inner WHERE by Django and therefore
            # runs before `ROW_NUMBER()`, promoting the superseded predecessor
            # back to rn=1 and keeping a material whose real state left the parc
            # counted until `date_fin`.
            if s["code_type_affectation"] in EXCLUDED_TYPES_AFFECTATION:
                continue

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

            # Single exhaustive classifier: every counted material lands in
            # exactly one bucket, so `nbr` always equals the sum of the
            # sub-counters. Pairs outside the reference grid (e.g. an
            # "Immobilisé" material carrying an "En rénovation" situation, or
            # "Acquisition"/"Cession reçue" affectations) are routed into the
            # Immobilisé "Autre" catch-all, mirroring the v2 dashboard's
            # "autres" bucket.
            if affectation == "01":
                if situation == "01":
                    row["exploitation"]["en_service"] += 1
                elif situation == "02":
                    row["exploitation"]["en_chomage"] += 1
                elif situation == "03":
                    row["exploitation"]["en_panne"] += 1
                else:
                    row["immobilise"]["autre"] += 1
            elif affectation == "04":
                if situation == "02":
                    row["immobilise"]["en_chomage"] += 1
                elif situation == "04":
                    row["immobilise"]["en_reparation"] += 1
                elif situation == "05":
                    row["immobilise"]["autre"] += 1
                else:
                    row["immobilise"]["autre"] += 1
            elif affectation == "02":
                if situation == "05":
                    row["reparation"]["autre"] += 1
                elif situation == "06":
                    row["reparation"]["ALREM"] += 1
                else:
                    row["immobilise"]["autre"] += 1
            else:
                row["immobilise"]["autre"] += 1
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
            if row["age_total"] > 0:
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
