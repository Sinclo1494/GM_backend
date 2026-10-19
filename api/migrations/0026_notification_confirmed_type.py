from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0025_notification_rejection_details'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(choices=[('PENDING_IMPORT', 'Import en attente'), ('IMPORT_REJECTED', 'Import rejeté'), ('IMPORT_CONFIRMED', 'Import confirmé')], default='PENDING_IMPORT', max_length=50),
        ),
    ]
