from api.models import Grand_Materiel
from django.db.models import Count

qs = Grand_Materiel.objects.filter(status='PENDING').exclude(import_batch_id__isnull=True)
result = list(qs.values('import_batch_id').annotate(c=Count('id')).order_by())
print(f'Found {len(result)} batches')
for r in result:
    print(f'  batch_id={r["import_batch_id"]}, count={r["c"]}')