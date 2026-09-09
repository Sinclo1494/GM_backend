import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from api.models import Type_Situation, Affectation_Materiel, Situation_Materiel
from django.db.models import Count
import sys

# Force UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

print('Type_Situation records:', Type_Situation.objects.count())
for t in Type_Situation.objects.all():
    print(f"  pk={t.pk}, code={t.code_type_situation}, libelle={t.libelle_type_situation}")

print()
print('Situation_Materiel records:', Situation_Materiel.objects.count())

print()
qs = Affectation_Materiel.objects.annotate(num_situations=Count('situation_ids'))
print('AMs total:', qs.count())
print('AMs with situations > 0:', qs.filter(num_situations__gt=0).count())
