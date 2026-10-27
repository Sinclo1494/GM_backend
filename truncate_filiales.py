#!/usr/bin/env python
"""
Truncate the transactional tables of every affiliate (filiale) database.

Tables emptied
--------------
    api_regularisation_gm   (Regularisation_GM)
    api_pointage             (Pointage)
    api_situation_materiel   (Situation_Materiel)
    api_affectation_materiel (Affectation_Materiel)
    api_grand_materiel       (Grand_Materiel)

Scope
-----
Only the affiliate databases registered in ``settings.FILIALE_DATABASES``
(``gm_a``, ``gm_c``, ``gm_e``, ``gm_g``, ``gm_k``, ``gm_l``, ``gm_m``,
``gm_p``, ``gm_r``, ``gm_t``) are touched.

The central database (``default``) is NEVER modified: it holds the users,
the ``Filiale`` reference table and the configuration data.  The reference
data that lives in the affiliate databases (``api_site``, ``api_filiale``,
``api_type_situation``, ``api_type_etat_materiel``, ``api_type_marque``,
``api_sous_famille_materiel``, ...) is also left untouched, as are the
``api_regularisation_mois_gm2`` rows.

Safety
------
* The five tables are emptied with a single ``TRUNCATE`` statement, so the
  foreign keys between them (pointage -> affectation, situation ->
  affectation, affectation -> grand materiel) never break.
* ``CASCADE`` is deliberately NOT used.  Before truncating, the script
  checks that no table outside the target set has a foreign key pointing at
  the target tables; if one does, the database is skipped and reported
  instead of silently emptying that extra table.
* ``RESTART IDENTITY`` resets the primary-key sequences of the emptied
  tables, so the next import starts from a clean id space.

Usage
-----
    python truncate_filiales.py --dry-run          # show the plan only
    python truncate_filiales.py                     # truncate every affiliate DB
    python truncate_filiales.py --filiale A --filiale C
"""

import argparse
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import connections, transaction  # noqa: E402


# The models whose tables are emptied, in the order used for the report.
TARGET_MODELS = [
    "regularisation_gm",
    "pointage",
    "situation_materiel",
    "affectation_materiel",
    "grand_materiel",
]


def target_tables():
    """Return [(model_name, db_table)] for the models to truncate."""
    return [(name, apps.get_model("api", name)._meta.db_table) for name in TARGET_MODELS]


def count_rows(alias, table):
    with connections[alias].cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {connections[alias].ops.quote_name(table)}")
        return cursor.fetchone()[0]


def external_referencing_tables(alias, tables):
    """
    Return the tables OUTSIDE ``tables`` that have a foreign key pointing at
    one of them.  An empty list means the truncation cannot cascade onto any
    other table.
    """
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT src.relname
            FROM pg_constraint con
            JOIN pg_class src ON src.oid = con.conrelid
            JOIN pg_class tgt ON tgt.oid = con.confrelid
            WHERE con.contype = 'f'
              AND tgt.relname = ANY(%s)
              AND NOT (src.relname = ANY(%s))
            GROUP BY src.relname
            ORDER BY src.relname
            """,
            [tables, tables],
        )
        return [row[0] for row in cursor.fetchall()]


def truncate_database(alias, tables):
    """
    Empty the given tables of one database in a single transaction.
    Returns the number of rows removed per table.
    """
    quote = connections[alias].ops.quote_name
    table_list = ", ".join(quote(t) for t in tables)
    sql = f"TRUNCATE TABLE {table_list} RESTART IDENTITY"
    with transaction.atomic(using=alias):
        with connections[alias].cursor() as cursor:
            cursor.execute(sql)
    return sql


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only show the plan and the row counts, change nothing",
    )
    parser.add_argument(
        "--filiale",
        action="append",
        default=None,
        help="restrict the truncation to the given affiliate code (repeatable)",
    )
    args = parser.parse_args(argv)

    codes = list(settings.FILIALE_DATABASES.keys())
    if args.filiale:
        unknown = [c for c in args.filiale if c not in codes]
        if unknown:
            raise SystemExit(f"Unknown affiliate code(s): {unknown}")
        codes = args.filiale

    models = target_tables()
    tables = [table for _name, table in models]
    total = 0
    failures = []

    for code in codes:
        alias = f"filiale_{code}"
        db_name = settings.FILIALE_DATABASES[code]
        print("=" * 72)
        print(f"[{code}] -> {alias} ({db_name})")

        try:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! unreachable: {exc}")
            failures.append((code, f"unreachable: {exc}"))
            continue

        external = external_referencing_tables(alias, tables)
        if external:
            print(
                f"  ! skipped: {external} reference the target tables; "
                "truncating would cascade onto them."
            )
            failures.append((code, f"external references: {external}"))
            continue

        counts = {}
        for name, table in models:
            counts[table] = count_rows(alias, table)
            print(f"    {table:<26} {counts[table]:>9} rows")

        if args.dry_run:
            print("  - dry run: nothing truncated")
            total += sum(counts.values())
            continue

        # The TRUNCATE is issued even when the tables are already empty: it
        # resets the primary-key sequences, which may still hold a stale
        # value from rows that were deleted earlier.
        sql = truncate_database(alias, tables)
        print(f"  - truncated ({sql})")
        total += sum(counts.values())

    print("=" * 72)
    if args.dry_run:
        print(f"Dry run: {total} rows would be removed across {len(codes)} database(s).")
    else:
        print(f"Done: {total} rows removed across {len(codes)} database(s).")
    if failures:
        print(f"Failures: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
