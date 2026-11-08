from __future__ import annotations
from calendar import monthrange
from datetime import date, datetime, time
from decimal import Decimal
from django.db.models import Sum
from api.models import Grand_Materiel, Pointage, Situation_Materiel as Situation
from django.conf import settings
from api.multidb import filiale_db_name, affiliate_routing
from api.permissions import can_access_all_filiales, can_access_filiale


class MgtDashboardService:
    EXCLUDED_TYPE_AFFECTATION = {"06", "07", "08"}
    EXCLUDED_LIBELLE = {"NON FOURNIE"}

    @staticmethod
    def _fmt_date(value):
        if value is None:
            return None
        if hasattr(value, "date"):
            value = value.date()
        return value.isoformat()

    @staticmethod
    def _mat_aux(mat):
        tm = mat.code_type_marque
        marque = ""
        mtype = ""
        if tm is not None:
            mtype = tm.libelle_type_marque or ""
            cm = tm.code_marque
            if cm is not None:
                marque = cm.libelle_marque or ""
        performance = mat.puissance_materiel or ""
        age = ""
        if mat.date_acquisition:
            try:
                age = str(date.today().year - mat.date_acquisition.year)
            except Exception:
                age = ""
        return {
            "marque": marque,
            "type": mtype,
            "performance": performance,
            "date_acquisition": mat.date_acquisition.isoformat() if mat.date_acquisition else None,
            "age": age,
        }

    @staticmethod
    def _get_decade_range(mmaa_str, decade):
        if not mmaa_str or not decade:
            return None
        try:
            year = int(mmaa_str[:4])
            month = int(mmaa_str[4:6])
        except Exception:
            return None
        if decade == "1":
            return date(year, month, 1), date(year, month, 10)
        elif decade == "2":
            return date(year, month, 11), date(year, month, 20)
        elif decade == "3":
            _, last = monthrange(year, month)
            return date(year, month, 21), date(year, month, last)
        return None

    @staticmethod
    def _month_range(mmaa_str):
        if not mmaa_str:
            return None
        try:
            year = int(mmaa_str[:4])
            month = int(mmaa_str[4:6])
        except Exception:
            return None
        _, last = monthrange(year, month)
        return date(year, month, 1), date(year, month, last)

    @classmethod
    def _is_material_filtered_out(cls, mat, user=None):
        latest = Situation.objects.filter(affectation_id__code_materiel=mat.code_materiel).order_by("-date_situation", "-id").first()
        if latest:
            ts = latest.type_situation_id
            taff = (ts.code_type_affectation.code_type_affectation if ts and ts.code_type_affectation else "").strip().upper()
            lib = (ts.libelle_type_situation or "").strip().upper()
            if taff in cls.EXCLUDED_TYPE_AFFECTATION or lib == cls.EXCLUDED_LIBELLE:
                return True
        return False

    @classmethod
    def _filiale_dbs_to_query(cls, user, filiale):
        """
        Return the list of filiale codes whose databases must be queried.

        - ``filiale`` is a specific code: query only that DB (if accessible).
        - ``filiale`` is ``'toutes'`` / ``None`` / empty: query every filiale DB
          the user may access (all-filiales users get all; others only their own).
        """
        if filiale and filiale != "toutes":
            if can_access_filiale(user, filiale):
                return [filiale]
            return []
        if can_access_all_filiales(user):
            return list(settings.FILIALE_DATABASES.keys())
        profile = getattr(user, "profile", None)
        if profile and profile.filiale and profile.filiale.code_filiale:
            code = profile.filiale.code_filiale
            if code in settings.FILIALE_DATABASES:
                return [code]
        return []

    @classmethod
    def _mgt_data(cls, user, famille, site, filiale, mmaa, decade, date_debut, date_fin, page, page_size, mode):
        filiale_codes = cls._filiale_dbs_to_query(user, filiale)
        if not filiale_codes:
            return {"results": [], "count": 0, "total_pages": 0, "page": page, "page_size": page_size, "totals": {}}

        date_range = None
        if date_debut and date_fin:
            try:
                date_range = (date.fromisoformat(date_debut), date.fromisoformat(date_fin))
            except Exception:
                pass
        if date_range is None:
            if mode == "decadaire":
                date_range = cls._get_decade_range(mmaa, decade)
            if date_range is None and mmaa:
                date_range = cls._month_range(mmaa)

        date_range_end = date_range[1] if date_range else None
        date_range_end_dt = datetime.combine(date_range_end, time.max) if date_range_end else None

        all_results = []
        for fil_code in filiale_codes:
            db = filiale_db_name(fil_code)
            with affiliate_routing(fil_code):
                gm_qs = Grand_Materiel.objects.using(db).select_related(
                    'code_sous_famille_materiel__code_famille_materiel',
                    'code_type_marque__code_marque',
                )
                if famille:
                    gm_qs = gm_qs.filter(code_sous_famille_materiel__code_famille_materiel__code_famille=famille)
                if site:
                    gm_qs = gm_qs.filter(affectations__code_site__code_site=site).distinct()
                if filiale and filiale != "toutes":
                    gm_qs = gm_qs.filter(affectations__code_filiale_mere=filiale).distinct()
                materiels = list(gm_qs)
                materiel_codes = [m.code_materiel for m in materiels if not cls._is_material_filtered_out(m, user)]
                if not materiel_codes:
                    continue

                pt_qs = Pointage.objects.using(db).filter(affectation_id__code_materiel__in=materiel_codes)
                if site:
                    pt_qs = pt_qs.filter(affectation_id__code_site__code_site=site)
                if date_range:
                    pt_qs = pt_qs.filter(mmaa__range=date_range)

                mat_map = {}
                for mat in materiels:
                    if mat.code_materiel not in materiel_codes:
                        continue
                    aux = cls._mat_aux(mat)
                    fdata = {
                        "famille": (
                            mat.code_sous_famille_materiel.code_famille_materiel.libelle_famille
                            if mat.code_sous_famille_materiel and mat.code_sous_famille_materiel.code_famille_materiel
                            else "UNKNOWN"
                        ),
                        "designation": mat.designation,
                        "code_materiel": mat.code_materiel,
                        "marque": aux["marque"],
                        "type": aux["type"],
                        "performance": aux["performance"],
                        "date_acquisition": aux["date_acquisition"],
                        "age": aux["age"],
                        "heures_service": Decimal("0"),
                        "heures_chomage": Decimal("0"),
                        "heures_panne": Decimal("0"),
                        "heures_total": Decimal("0"),
                        "date_immobilisation": None,
                    }
                    if mode == "mensuel":
                        fdata["parc_total"] = 0
                    mat_map[mat.code_materiel] = fdata

                sit_immob = Situation.objects.using(db).filter(
                    affectation_id__code_materiel__in=materiel_codes,
                    type_situation_id__code_type_affectation__code_type_affectation='04',
                )
                if date_range_end_dt:
                    sit_immob = sit_immob.filter(date_situation__lte=date_range_end_dt)
                sit_immob = sit_immob.order_by(
                    'affectation_id__code_materiel', '-date_situation', '-id'
                ).values('affectation_id__code_materiel', 'date_situation')
                immob_dates = {}
                for s in sit_immob:
                    cm = s['affectation_id__code_materiel']
                    if cm not in immob_dates:
                        immob_dates[cm] = s['date_situation']
                for mat in materiels:
                    if mat.code_materiel not in materiel_codes:
                        continue
                    mat_map[mat.code_materiel]["date_immobilisation"] = immob_dates.get(mat.code_materiel)

                pt_agg = pt_qs.values('affectation_id__code_materiel').annotate(
                    hs=Sum('heures_service'), hc=Sum('heures_chomage'), hp=Sum('heures_panne')
                )
                pt_map = {}
                for row in pt_agg:
                    cm = row['affectation_id__code_materiel']
                    pt_map[cm] = {
                        'heures_service': Decimal(str(row['hs'] or 0)),
                        'heures_chomage': Decimal(str(row['hc'] or 0)),
                        'heures_panne': Decimal(str(row['hp'] or 0)),
                    }

                # Chantier selected: only materiel that has pointage at that site are returned.
                if site:
                    mat_map = {cm: fdata for cm, fdata in mat_map.items() if cm in pt_map}

                for mat_code, fdata in mat_map.items():
                    pdata = pt_map.get(mat_code, {})
                    hs = pdata.get('heures_service', Decimal("0"))
                    hc = pdata.get('heures_chomage', Decimal("0"))
                    hp = pdata.get('heures_panne', Decimal("0"))
                    fdata["heures_service"] += hs
                    fdata["heures_chomage"] += hc
                    fdata["heures_panne"] += hp
                    fdata["heures_total"] += hs + hc + hp
                    if mode == "mensuel":
                        fdata["parc_total"] = 1

                for mat_code, fdata in mat_map.items():
                    htot = fdata["heures_total"]
                    hs = fdata["heures_service"]
                    hc = fdata["heures_chomage"]
                    hp = fdata["heures_panne"]
                    row = {
                        "famille": fdata["famille"],
                        "code_materiel": mat_code,
                        "designation": fdata["designation"],
                        "marque": fdata["marque"],
                        "type": fdata["type"],
                        "performance": fdata["performance"],
                        "age": fdata["age"],
                        "date_immobilisation": cls._fmt_date(fdata["date_immobilisation"]),
                        "heures_service": round(float(hs), 2),
                        "heures_chomage": round(float(hc), 2),
                        "heures_panne": round(float(hp), 2),
                        "heures_total": round(float(htot), 2),
                    }
                    if mode == "decadaire":
                        row["pourcentage_service"] = round(float((hs / htot * 100) if htot else 0), 2)
                        row["pourcentage_chomage"] = round(float((hc / htot * 100) if htot else 0), 2)
                        row["pourcentage_panne"] = round(float((hp / htot * 100) if htot else 0), 2)
                    else:
                        row["parc_total"] = fdata["parc_total"]
                        row["pourcentage_service"] = round(float((hs / htot * 100) if htot else 0), 2)
                        row["pourcentage_chomage"] = round(float((hc / htot * 100) if htot else 0), 2)
                        row["pourcentage_panne"] = round(float((hp / htot * 100) if htot else 0), 2)
                    all_results.append(row)

        total = len(all_results)
        if page_size and page_size > 0:
            start = (page - 1) * page_size
            paginated = all_results[start:start + page_size]
            total_pages = (total + page_size - 1) // page_size
        else:
            paginated = all_results
            total_pages = 1
        totals = {}
        if all_results:
            if mode == "decadaire":
                ths = sum(Decimal(str(r["heures_service"])) for r in all_results)
                thc = sum(Decimal(str(r["heures_chomage"])) for r in all_results)
                thp = sum(Decimal(str(r["heures_panne"])) for r in all_results)
                tht = sum(Decimal(str(r["heures_total"])) for r in all_results)
                totals = {
                    "heures_service": round(float(ths), 2),
                    "heures_chomage": round(float(thc), 2),
                    "heures_panne": round(float(thp), 2),
                    "heures_total": round(float(tht), 2),
                    "pourcentage_service": round(float((ths / tht * 100) if tht else 0), 2),
                    "pourcentage_chomage": round(float((thc / tht * 100) if tht else 0), 2),
                    "pourcentage_panne": round(float((thp / tht * 100) if tht else 0), 2),
                }
            else:
                tparc = sum(r["parc_total"] for r in all_results)
                ths = sum(Decimal(str(r["heures_service"])) for r in all_results)
                thc = sum(Decimal(str(r["heures_chomage"])) for r in all_results)
                thp = sum(Decimal(str(r["heures_panne"])) for r in all_results)
                tht = sum(Decimal(str(r["heures_total"])) for r in all_results)
                totals = {
                    "parc_total": tparc,
                    "heures_service": round(float(ths), 2),
                    "heures_chomage": round(float(thc), 2),
                    "heures_panne": round(float(thp), 2),
                    "heures_total": round(float(tht), 2),
                    "pourcentage_service": round(float((ths / tht * 100) if tht else 0), 2),
                    "pourcentage_chomage": round(float((thc / tht * 100) if tht else 0), 2),
                    "pourcentage_panne": round(float((thp / tht * 100) if tht else 0), 2),
                }
        return {
            "results": paginated,
            "count": total,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size,
            "totals": totals,
        }

    @classmethod
    def get_decadaire_data(cls, user, famille=None, site=None, filiale=None, mmaa=None, decade=None, date_debut=None, date_fin=None, page=1, page_size=100):
        return cls._mgt_data(user, famille, site, filiale, mmaa, decade, date_debut, date_fin, page, page_size, "decadaire")

    @classmethod
    def get_mensuel_data(cls, user, famille=None, site=None, filiale=None, mmaa=None, date_debut=None, date_fin=None, page=1, page_size=100):
        return cls._mgt_data(user, famille, site, filiale, mmaa, None, date_debut, date_fin, page, page_size, "mensuel")

    @classmethod
    def _get_famille_codes(cls, user, famille, site, filiale, mmaa, decade, date_debut, date_fin, mode):
        filiale_codes = cls._filiale_dbs_to_query(user, filiale)
        if not filiale_codes:
            return []

        date_range = None
        if date_debut and date_fin:
            try:
                date_range = (date.fromisoformat(date_debut), date.fromisoformat(date_fin))
            except Exception:
                pass
        if date_range is None:
            if mode == "decadaire":
                date_range = cls._get_decade_range(mmaa, decade)
            if date_range is None and mmaa:
                date_range = cls._month_range(mmaa)

        famille_codes = set()
        for fil_code in filiale_codes:
            db = filiale_db_name(fil_code)
            with affiliate_routing(fil_code):
                gm_qs = Grand_Materiel.objects.using(db).select_related(
                    'code_sous_famille_materiel__code_famille_materiel',
                )
                if famille:
                    gm_qs = gm_qs.filter(code_sous_famille_materiel__code_famille_materiel__code_famille=famille)
                if site:
                    gm_qs = gm_qs.filter(affectations__code_site__code_site=site).distinct()
                if filiale and filiale != "toutes":
                    gm_qs = gm_qs.filter(affectations__code_filiale_mere=filiale).distinct()
                codes = gm_qs.values_list(
                    'code_sous_famille_materiel__code_famille_materiel__code_famille', flat=True
                ).distinct()
                for c in codes:
                    if c:
                        famille_codes.add(c)
        return sorted(famille_codes)

    @classmethod
    def get_decadaire_recap_data(cls, user, famille=None, site=None, filiale=None, mmaa=None, decade=None, date_debut=None, date_fin=None):
        from api.models import Famille_Materiel
        famille_codes = cls._get_famille_codes(user, famille, site, filiale, mmaa, decade, date_debut, date_fin, "decadaire")
        famille_labels = {f.code_famille: f.libelle_famille for f in Famille_Materiel.objects.using('default').all()}
        results = []
        for fam_code in famille_codes:
            data = cls._mgt_data(user, fam_code, site, filiale, mmaa, decade, date_debut, date_fin, 1, 0, "decadaire")
            totals = data.get("totals", {})
            if not totals:
                continue
            results.append({
                "famille": fam_code,
                "famille_label": famille_labels.get(fam_code, fam_code),
                "heures_service": totals.get("heures_service", 0),
                "pourcentage_service": totals.get("pourcentage_service", 0),
                "heures_chomage": totals.get("heures_chomage", 0),
                "pourcentage_chomage": totals.get("pourcentage_chomage", 0),
                "heures_panne": totals.get("heures_panne", 0),
                "pourcentage_panne": totals.get("pourcentage_panne", 0),
            })
        return results

    @classmethod
    def get_mensuel_recap_data(cls, user, famille=None, site=None, filiale=None, mmaa=None, date_debut=None, date_fin=None):
        from api.models import Famille_Materiel
        famille_codes = cls._get_famille_codes(user, famille, site, filiale, mmaa, None, date_debut, date_fin, "mensuel")
        famille_labels = {f.code_famille: f.libelle_famille for f in Famille_Materiel.objects.using('default').all()}
        results = []
        for fam_code in famille_codes:
            data = cls._mgt_data(user, fam_code, site, filiale, mmaa, None, date_debut, date_fin, 1, 0, "mensuel")
            totals = data.get("totals", {})
            if not totals:
                continue
            results.append({
                "famille": fam_code,
                "famille_label": famille_labels.get(fam_code, fam_code),
                "heures_service": totals.get("heures_service", 0),
                "pourcentage_service": totals.get("pourcentage_service", 0),
                "heures_chomage": totals.get("heures_chomage", 0),
                "pourcentage_chomage": totals.get("pourcentage_chomage", 0),
                "heures_panne": totals.get("heures_panne", 0),
                "pourcentage_panne": totals.get("pourcentage_panne", 0),
            })
        return results
