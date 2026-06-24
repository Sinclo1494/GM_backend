import csv
import io

from django.db import transaction

from api.models import (
    Situation_Materiel,
    Affectation_Materiel,
    Type_Situation,
    Type_Etat_Materiel,
)
from api.resources import normalize_datetime

BATCH_SIZE = 5000


class SituationImportService:
    def __init__(self, file_obj):
        print("initializing")
        self.file_obj = file_obj
        self.affectations = {}
        self.situations = {}
        self.etats = {}
        self.existing_keys = set()

    def load_cache(self):
        print("loading cache")

        self.affectations = {
            (code_affectation, code_site): id_
            for code_affectation, code_site, id_ in Affectation_Materiel.objects.values_list(
                "code_affectation",
                "code_site__code_site",
                "id",
            )
        }

        self.situations = {
            (code_situation, code_affectation): id_
            for code_situation, code_affectation, id_ in Type_Situation.objects.values_list(
                "code_type_situation",
                "code_type_affectation__code_type_affectation",
                "id",
            )
        }

        self.etats = dict(
            Type_Etat_Materiel.objects.values_list("code_type_etat_materiel", "id")
        )

        self.existing_keys = set(Situation_Materiel.objects.values_list("id_situation"))

    def transform_row(self, row):
        print("transforming row")

        affectation_key = (row["code_affectation"], row["code_site"])
        affectation_id = self.affectations.get(affectation_key)
        if affectation_id is None:
            raise ValueError(f"Affectation not found: {affectation_key}")

        type_situation_key = (row["code_type_situation"], row["code_type_affectation"])
        type_situation_id = self.situations.get(type_situation_key)
        if type_situation_id is None:
            raise ValueError(f"Type Situtaion not found: {type_situation_key}")
        
        etat_id = self.etats.get(row["code_type_etat_materiel"])

        id_situtaion = row["id_situation"]
        unique_key = id_situtaion

        if unique_key in self.existing_keys:
            return None

        self.existing_keys.add(unique_key)

        return Situation_Materiel(
            id_situation=row["id_situation"],
            affectation_id_id=affectation_id,
            type_situation_id_id=type_situation_id,
            code_type_etat_materiel_id=etat_id,
            date_situation=normalize_datetime(row["date_situation"]),
            est_bloque=row.get("est_bloque", False),
            date_modification=normalize_datetime(row["date_modification"]),
        )

    def import_data(self):
        print("Importing data ...")

        self.load_cache()

        self.file_obj.seek(0)
        text_file = io.TextIOWrapper(self.file_obj.file, encoding="utf-8", newline="")
        reader = csv.DictReader(text_file)

        batch = []
        total_inserted = 0

        for row in reader:
            obj = self.transform_row(row)

            if obj is not None:
                batch.append(obj)

            if len(batch) >= BATCH_SIZE:
                self._flush(batch)
                total_inserted += len(batch)
                batch.clear()

        if batch:
            self._flush(batch)
            total_inserted += len(batch)

        return total_inserted

    def _flush(self, batch):
        print("flushing ...")

        with transaction.atomic():
            Situation_Materiel.objects.bulk_create(
                batch,
                batch_size=BATCH_SIZE,
            )
