from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('BROADCAST', 'Broadcast'),
                    ('PERSONAL', 'Personal'),
                    ('ADMIN', 'Admin'),
                ],
                default='PERSONAL',
                max_length=20,
            ),
        ),
    ]
