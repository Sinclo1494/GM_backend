from api.models import Grand_Materiel
from django.db.models import Count
from collections import defaultdict

# Test the batch grouping logic
model_configs = [
    ('grand_materiel', Grand_Materiel),
]

batches = defaultdict(lambda: {'models': defaultdict(int), 'created_at': None, 'module': None})

for model_key, ModelClass in model_configs:
    try:
        qs = ModelClass.objects.filter(status='PENDING').exclude(import_batch_id__isnull=True)
        for obj in qs.values('import_batch_id').annotate(c=Count('id')).order_by():
            bid = obj['import_batch_id']
            batches[bid]['models'][model_key] += obj['c']
            print(f'Batch: {bid}, count: {obj["c"]}')
    except Exception as e:
        print(f'Error: {e}')

print(f'Batches found: {len(batches)}')
for bid, data in batches.items():
    print(f'  {bid}: {dict(data["models"])}')