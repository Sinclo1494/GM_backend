import csv
from datetime import datetime
import decimal

from django.db import transaction

from api.models import Pointage, Affectation_Materiel
from api.resources import normalize_datetime

from .csv_normalizer import CsvNormalizer

BATCH_SIZE = 5000


class CsvImporter:
    def __init__(self, uploaded_file, schema, mapping, filiale):
        self.file = CsvNormalizer.normalize(
            uploaded_file=uploaded_file, schema=schema, mapping=mapping, filiale=filiale
        )

        self.schema = schema
        self.filiale = filiale
        self.affectations = {}
        self.existing_keys = set()

    def parse_date(self, value):
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                pass

        raise ValueError(f"Unsupported date format: {value}")
    
    def load_cache(self):

        self.affectations = {
            (
                a.code_materiel.code_materiel,
                a.date_affectation.replace(tzinfo=None),
                a.code_site.code_site,
            ): a.id
            for a in Affectation_Materiel.objects.filter(
                code_filiale_mere=self.filiale
            ).select_related("code_materiel", "code_site", "code_filiale_mere")
        }

        self.existing_keys = set(
            Pointage.objects.values_list(
                "affectation_id",
                "mmaa",
            )
        )

    def transform_row(self, row):
        date_affectation = normalize_datetime(row["date_affectation"])

        key = (
            row["code_materiel"],
            date_affectation,
            row["code_site"],
        )

        affectation_id = self.affectations.get(key)

        if affectation_id is None:
            raise ValueError(f"Affectation not found: {key}")

        mmaa = self.parse_date(str(row["mmaa"]))
        unique_key = (affectation_id, mmaa)

        if unique_key in self.existing_keys:
            return None

        self.existing_keys.add(unique_key)

        heures_service = decimal.Decimal(row["heures_service"] or "0")
        heures_chomage = decimal.Decimal(row["heures_chomage"] or "0")
        heures_panne = decimal.Decimal(row["heures_panne"] or "0")
        potentiel = decimal.Decimal(row["potentiel"] or "0")
        taux = decimal.Decimal(row["taux_location"] or "0")

        return Pointage(
            affectation_id_id=affectation_id,
            mmaa=mmaa,
            taux_location=taux,
            heures_service=heures_service,
            heures_chomage=heures_chomage,
            heures_panne=heures_panne,
            potentiel=potentiel,
            montant_service=heures_service * taux,
            montant_chomage=heures_chomage * taux,
            montant_panne=heures_panne * taux,
            est_bloque=row.get("est_bloque", False),
            date_modification=normalize_datetime(row.get("date_modification")),
        )

    def import_data(self):
        self.load_cache()

        self.file.seek(0)

        reader = csv.DictReader(
            self.file,
            delimiter=";",
        )

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
        with transaction.atomic():
            Pointage.objects.bulk_create(
                batch,
                batch_size=BATCH_SIZE,
            )
