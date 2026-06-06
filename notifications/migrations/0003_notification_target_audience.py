from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_add_admin_notification_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='target_audience',
            field=models.CharField(
                choices=[
                    ('ALL', 'All Users'),
                    ('BASIC', 'Basic Subscribers'),
                    ('PREMIUM', 'Premium Subscribers'),
                ],
                default='ALL',
                max_length=20,
            ),
        ),
    ]
