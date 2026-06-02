from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('movies', '0007_remove_movie_access_level_moviedownload'),
    ]

    operations = [
        migrations.AlterField(
            model_name='movie',
            name='thumbnail',
            field=models.URLField(max_length=500),
        ),
        migrations.AlterField(
            model_name='movie',
            name='movie_file',
            field=models.URLField(max_length=500),
        ),
        migrations.AlterField(
            model_name='movie',
            name='thriller_clip',
            field=models.URLField(
                blank=True, null=True, max_length=500,
                help_text='Short 30-second preview clip',
            ),
        ),
    ]
