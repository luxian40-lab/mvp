from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0165_envio_campana_meta_estados'),
    ]

    operations = [
        migrations.AddField(
            model_name='campanameta',
            name='fecha_programada',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='campanameta',
            name='pausa_motivo',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='campanameta',
            name='pausada',
            field=models.BooleanField(default=False),
        ),
    ]
