from django.db import migrations


def seed_default_types(apps, schema_editor):
    Type_Affectation = apps.get_model("api", "Type_Affectation")
    Type_Situation = apps.get_model("api", "Type_Situation")
    Type_Etat_Materiel = apps.get_model("api", "Type_Etat_Materiel")

    type_affectation, _ = Type_Affectation.objects.update_or_create(
        code_type_affectation="AFFECTATION",
        defaults={
            "libelle_type_affectation": "Affectation",
            "est_bloque": False,
        },
    )

    Type_Situation.objects.update_or_create(
        code_type_situation="CREATION",
        code_type_affectation=type_affectation,
        defaults={
            "libelle_type_situation": "Création",
            "est_bloque": False,
        },
    )

    Type_Etat_Materiel.objects.update_or_create(
        code_type_etat_materiel="NEUF",
        defaults={
            "libelle_type_etat_materiel": "Neuf",
            "est_bloque": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0020_alter_affectation_materiel_code_site_nullable"),
    ]

    operations = [
        migrations.RunPython(seed_default_types, migrations.RunPython.noop),
    ]
