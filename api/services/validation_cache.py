from uuid import uuid4

from django.core.cache import cache


CACHE_TIMEOUT = 600  # 10 minutes
CACHE_PREFIX = "csv_validation"


class ValidationCache:
    """
    Stores successful CSV validation results temporarily.

    The cache allows the import step to reuse the validated rows
    without validating the CSV a second time.
    """

    # ---------------------------------------------------------
    # Build cache key
    # ---------------------------------------------------------

    @staticmethod
    def _key(validation_id: str) -> str:
        return f"{CACHE_PREFIX}:{validation_id}"

    # ---------------------------------------------------------
    # Save validation result
    # ---------------------------------------------------------

    @classmethod
    def save(
        cls,
        report,
        filiale,
        filename="",
    ) -> str:
        """
        Save a successful validation result and return
        its unique validation identifier.
        """

        if not report.success:
            raise ValueError(
                "Impossible de mettre en cache une validation "
                "contenant des erreurs."
            )

        validation_id = str(uuid4())

        payload = {
            "rows": report.rows,
            "filiale": filiale,
            "filename": filename,
            "summary": report.to_dict()["summary"],
        }

        cache.set(
            cls._key(validation_id),
            payload,
            timeout=CACHE_TIMEOUT,
        )

        return validation_id

    # ---------------------------------------------------------
    # Retrieve validation payload
    # ---------------------------------------------------------

    @classmethod
    def get(
        cls,
        validation_id: str,
    ) -> dict | None:
        """
        Retrieve a previously validated payload.
        """

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
        """
        Remove a validation payload from the cache.
        """

        if not validation_id:
            return

        cache.delete(
            cls._key(validation_id)
        )