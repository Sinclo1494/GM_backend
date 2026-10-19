from uuid import uuid4

from django.core.cache import cache


CACHE_TIMEOUT = 600  # 10 minutes
CACHE_PREFIX = "csv_validation"


class ValidationCache:
    @staticmethod
    def _key(validation_id: str) -> str:
        return f"{CACHE_PREFIX}:{validation_id}"

    @classmethod
    def save(
        cls,
        report,
        filiale,
        filename="",
        import_batch_id=None,
    ) -> str:
        if not report.success:
            raise ValueError(
                "Impossible de mettre en cache une validation "
                "contenant des erreurs."
            )

        validation_id = str(uuid4())
        if not import_batch_id:
            import_batch_id = str(uuid4())

        payload = {
            "rows": report.rows,
            "filiale": filiale,
            "filename": filename,
            "summary": report.to_dict()["summary"],
            "import_batch_id": import_batch_id,
        }

        cache.set(
            cls._key(validation_id),
            payload,
            timeout=CACHE_TIMEOUT,
        )

        return validation_id

    @classmethod
    def get(
        cls,
        validation_id: str,
    ) -> dict | None:
        if not validation_id:
            return None
        return cache.get(cls._key(validation_id))

    @classmethod
    def delete(
        cls,
        validation_id: str,
    ) -> None:
        if not validation_id:
            return
        cache.delete(cls._key(validation_id))
