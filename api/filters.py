from django.db.models import Q
from rest_framework import filters

class AffectationMaterielFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        code_affectation = request.query_params.get("code_affectation")
        code_materiel = request.query_params.get("code_materiel")
        code_site = request.query_params.get("code_site")
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")
        est_bloque = request.query_params.get("est_bloque")
        prenable = request.query_params.get("prenable")

        if code_affectation:
            queryset = queryset.filter(code_affectation__icontains=code_affectation)
        if code_materiel:
            queryset = queryset.filter(code_materiel__code_materiel__icontains=code_materiel)
        if code_site:
            queryset = queryset.filter(code_site__code_site__icontains=code_site)
        if code_filiale:
            queryset = queryset.filter(code_filiale_mere__code_filiale__icontains=code_filiale)
        if date_debut:
            queryset = queryset.filter(date_affectation__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_affectation__lte=date_fin)
        if est_bloque is not None:
            queryset = queryset.filter(est_bloque=est_bloque.lower() == "true")
        if prenable is not None:
            queryset = queryset.filter(prenable=prenable.lower() == "true")
        return queryset

class SituationMaterielFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        id_situation = request.query_params.get("id_situation")
        code_affectation = request.query_params.get("code_affectation")
        code_materiel = request.query_params.get("code_materiel")
        code_type_situation = request.query_params.get("code_type_situation")
        code_type_affectation = request.query_params.get("code_type_affectation")
        etat_materiel = request.query_params.get("etat_materiel")
        code_site = request.query_params.get("code_site")
        code_filiale = request.query_params.get("code_filiale")
        date_debut = request.query_params.get("date_debut")
        date_fin = request.query_params.get("date_fin")
        est_bloque = request.query_params.get("est_bloque")

        if id_situation:
            queryset = queryset.filter(id_situation__icontains=id_situation)
        if code_affectation:
            queryset = queryset.filter(affectation_id__code_affectation__icontains=code_affectation)
        if code_materiel:
            queryset = queryset.filter(affectation_id__code_materiel__code_materiel__icontains=code_materiel)
        if code_type_situation:
            queryset = queryset.filter(type_situation_id__code_type_situation__icontains=code_type_situation)
        if code_type_affectation:
            queryset = queryset.filter(type_situation_id__code_type_affectation__code_type_affectation__icontains=code_type_affectation)
        if etat_materiel:
            queryset = queryset.filter(code_type_etat_materiel__code_type_etat_materiel__icontains=etat_materiel)
        if code_site:
            queryset = queryset.filter(affectation_id__code_site__code_site__icontains=code_site)
        if code_filiale:
            queryset = queryset.filter(affectation_id__code_filiale_mere__code_filiale__icontains=code_filiale)
        if date_debut:
            queryset = queryset.filter(date_situation__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_situation__lte=date_fin)
        if est_bloque is not None:
            queryset = queryset.filter(est_bloque=est_bloque.lower() == "true")
        return queryset

class GrandMaterielFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        code_materiel = request.query_params.get("code_materiel")
        designation = request.query_params.get("designation")
        num_serie = request.query_params.get("num_serie")
        immatriculation = request.query_params.get("immatriculation")
        code_sous_famille = request.query_params.get("code_sous_famille")
        code_type_marque = request.query_params.get("code_type_marque")
        code_filiale = request.query_params.get("code_filiale")
        est_bloque = request.query_params.get("est_bloque")

        if code_materiel:
            queryset = queryset.filter(code_materiel__icontains=code_materiel)
        if designation:
            queryset = queryset.filter(designation__icontains=designation)
        if num_serie:
            queryset = queryset.filter(num_serie__icontains=num_serie)
        if immatriculation:
            queryset = queryset.filter(immatriculation__icontains=immatriculation)
        if code_sous_famille:
            queryset = queryset.filter(code_sous_famille_materiel__code_sous_famille__icontains=code_sous_famille)
        if code_type_marque:
            queryset = queryset.filter(code_type_marque__code_type_marque__icontains=code_type_marque)
        if code_filiale:
            queryset = queryset.filter(code_filiale_g__code_filiale__icontains=code_filiale)
        if est_bloque is not None:
            queryset = queryset.filter(est_bloque=est_bloque.lower() == "true")
        return queryset

class PointageFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        code_affectation = request.query_params.get("code_affectation")
        code_materiel = request.query_params.get("code_materiel")
        mmaa = request.query_params.get("mmaa")
        mmaa_debut = request.query_params.get("mmaa_debut")
        mmaa_fin = request.query_params.get("mmaa_fin")
        code_site = request.query_params.get("code_site")
        code_filiale = request.query_params.get("code_filiale")
        est_bloque = request.query_params.get("est_bloque")

        if code_affectation:
            queryset = queryset.filter(affectation_id__code_affectation__icontains=code_affectation)
        if code_materiel:
            queryset = queryset.filter(affectation_id__code_materiel__code_materiel__icontains=code_materiel)
        if mmaa:
            queryset = queryset.filter(mmaa=mmaa)
        if mmaa_debut:
            queryset = queryset.filter(mmaa__gte=mmaa_debut)
        if mmaa_fin:
            queryset = queryset.filter(mmaa__lte=mmaa_fin)
        if code_site:
            queryset = queryset.filter(affectation_id__code_site__code_site__icontains=code_site)
        if code_filiale:
            queryset = queryset.filter(affectation_id__code_filiale_mere__code_filiale__icontains=code_filiale)
        if est_bloque is not None:
            queryset = queryset.filter(est_bloque=est_bloque.lower() == "true")
        return queryset
