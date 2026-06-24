import csv
import io

from django.db import transaction

from api.models import Pointage, Affectation_Materiel
from api.resources import normalize_datetime

BATCH_SIZE = 5000


class PointageImportService:
    def __init__(self, file_obj):
        print("initializing")
        self.file_obj = file_obj
        self.affectations = {}
        self.existing_keys = set()

    def load_cache(self):
        print("loading cache")
        self.affectations = {
            (a.code_affectation, a.code_site.code_site): a.id
            for a in Affectation_Materiel.objects.select_related("code_site")
        }

        self.existing_keys = set(
            Pointage.objects.values_list("affectation_id", "mmaa")
        )

    def transform_row(self, row):
        print("transforming row")

        key = (row["code_affectation"], row["code_site"])

        affectation_id = self.affectations.get(key)

        if affectation_id is None:
            raise ValueError(f"Affectation not found: {key}")

        mmaa = row["mmaa"]
        unique_key = (affectation_id, mmaa)

        if unique_key in self.existing_keys:
            return None

        self.existing_keys.add(unique_key)

        return Pointage(
            affectation_id_id=affectation_id,
            mmaa=mmaa,
            taux_location=row["taux_location"],
            heures_service=row["heures_service"],
            heures_chomage=row["heures_chomage"],
            heures_panne=row["heures_panne"],
            potentiel=row["potentiel"],
            montant_service=row["montant_service"],
            montant_chomage=row["montant_chomage"],
            montant_panne=row["montant_panne"],
            est_bloque=row.get("est_bloque", False),
            date_modification=normalize_datetime(row.get("date_modification")),
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
            Pointage.objects.bulk_create(
                batch,
                batch_size=BATCH_SIZE,
            )