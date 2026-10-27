#!/usr/bin/env python
"""
Apply Django migrations to the central database and every filiale database.

Usage (from the backend directory):
    python migrate_all_filiales.py

This runs `manage.py migrate --database=<db>` for:
  1. "default" (central admin DB: users, auth, Filiale, config)
  2. each "filiale_<code>" connection registered in settings.FILIALE_DATABASES

Per-filiale databases are guaranteed to have identical schemas at all times, so
the same migration set is applied to every filiale database.

This script does NOT create databases or provision new filiales (that is done
out-of-band / intentionally left unimplemented per project decision).
"""

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

import django

django.setup()

from django.core.management import call_command
from django.conf import settings


def migrate_database(database, label):
    print(f"=== Migrating database: {database} ({label}) ===")
    call_command("migrate", database=database, interactive=False, verbosity=1)
    print(f"=== Done: {database} ===\n")


def main():
    # 1. Central database (users, auth, Filiale, config)
    migrate_database("default", "central admin")

    # 2. Each filiale database (schemas identical at all times)
    for _filiale_code, _filiale_db_name in settings.FILIALE_DATABASES.items():
        target_db = f"filiale_{_filiale_code}"
        migrate_database(
            target_db, f"filiale {_filiale_code} ({_filiale_db_name})"
        )

    print("All databases migrated successfully.")


if __name__ == "__main__":
    main()
