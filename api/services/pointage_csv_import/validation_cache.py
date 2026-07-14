from uuid import uuid4

from django.core.cache import cache


CACHE_TIMEOUT = 600  # 10 minutes
CACHE_PREFIX = "pointage_validation"


class ValidationCache:

    # ---------------------------------------------------------
    # Cache key
    # ---------------------------------------------------------

    @staticmethod
    def _key(validation_id: str) -> str:
        return f"{CACHE_PREFIX}:{validation_id}"

    # ---------------------------------------------------------
    # Save successful validation
    # ---------------------------------------------------------

    @classmethod
    def save(
        cls,
        report,
        filiale,
    ) -> str:

        if not report.success:
            raise ValueError(
                "Impossible de mettre en cache "
                "une validation contenant des erreurs."
            )

        validation_id = str(uuid4())

        payload = {
            "rows": report.rows,
            "filiale": filiale,
            "summary": report.to_dict()["summary"],
        }

        cache.set(
            cls._key(validation_id),
            payload,
            timeout=CACHE_TIMEOUT,
        )

        return validation_id

    # ---------------------------------------------------------
    # Retrieve validated import payload
    # ---------------------------------------------------------

    @classmethod
    def get(
        cls,
        validation_id: str,
    ) -> dict | None:

        if not validation_id:
            return None

        return cache.get(
            cls._key(validation_id)
        )

    # ---------------------------------------------------------
    # Delete validation payload
    # ---------------------------------------------------------

    @classmethod
    def delete(
        cls,
        validation_id: str,
    ) -> None:

        if not validation_id:
            return

        cache.delete(
            cls._key(validation_id)
        )