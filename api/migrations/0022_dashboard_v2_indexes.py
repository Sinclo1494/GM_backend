"""Dashboard v2 — covering indexes for the aggregation queries.

Uses raw ``CREATE INDEX CONCURRENTLY`` instead of ``AddIndex`` so the tables stay
writable while the indexes are built (no ``ACCESS EXCLUSIVE`` lock), which matters
for ``api_pointage`` and ``api_affectation_materiel``.

``CONCURRENTLY`` cannot run inside a transaction, hence ``atomic = False`` and one
``RunSQL`` per index. ``IF NOT EXISTS`` keeps the migration re-runnable.
"""

from django.db import migrations

# (table, column, index name)
DASHBOARD_V2_INDEXES = [
    ("api_pointage", "mmaa", "dashboard_v2_pointage_mmaa_idx"),
    ("api_pointage", "est_bloque", "dashboard_v2_pointage_est_bloque_idx"),
    (
        "api_affectation_materiel",
        "code_materiel",
        "dashboard_v2_affectation_code_materiel_idx",
    ),
    (
        "api_affectation_materiel",
        "code_filiale_mere",
        "dashboard_v2_affectation_code_filiale_mere_idx",
    ),
    (
        "api_affectation_materiel",
        "date_fin_affectation",
        "dashboard_v2_affectation_date_fin_idx",
    ),
    (
        "api_situation_materiel",
        "date_situation",
        "dashboard_v2_situation_date_situation_idx",
    ),
    (
        "api_grand_materiel",
        "code_filiale_g",
        "dashboard_v2_grand_materiel_code_filiale_g_idx",
    ),
    (
        "api_grand_materiel",
        "code_sous_famille_materiel",
        "dashboard_v2_grand_materiel_code_sous_famille_idx",
    ),
]

# Partial indexes on the boolean flags: the dashboard always filters
# `est_bloque=False`, so the vast majority of rows live in a small slice.
PARTIAL_INDEXES = [
    ("api_pointage", "est_bloque", "dashboard_v2_pointage_not_bloque_idx"),
]


def _create_sql(table, column, name, where=None):
    sql = f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{name}" ON "{table}" ("{column}")'
    if where:
        sql += f" WHERE {where}"
    return sql + ";"


def _drop_sql(name):
    return f'DROP INDEX CONCURRENTLY IF EXISTS "{name}";'


def build_operations():
    operations = []
    for table, column, name in DASHBOARD_V2_INDEXES:
        operations.append(
            migrations.RunSQL(
                sql=[_create_sql(table, column, name)],
                reverse_sql=[_drop_sql(name)],
            )
        )
    for table, column, name in PARTIAL_INDEXES:
        operations.append(
            migrations.RunSQL(
                sql=[_create_sql(table, column, name, where='"est_bloque" = false')],
                reverse_sql=[_drop_sql(name)],
            )
        )
    return operations


class Migration(migrations.Migration):
    # `CREATE INDEX CONCURRENTLY` is not allowed inside a transaction block.
    atomic = False

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = build_operations()
