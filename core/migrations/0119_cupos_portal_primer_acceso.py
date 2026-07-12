from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0118_documentorag_error_indexacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='cupos_portal',
            field=models.PositiveIntegerField(
                default=5,
                help_text=(
                    'Máximo de usuarios del portal B2B para esta organización. '
                    'Solo eki (Django admin) puede crearlos; el cliente no invita usuarios.'
                ),
                verbose_name='Cupos de usuarios portal',
            ),
        ),
    ]
