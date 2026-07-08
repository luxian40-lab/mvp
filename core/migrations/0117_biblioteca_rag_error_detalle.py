from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0116_biblioteca_conocimiento_nat'),
    ]

    operations = [
        migrations.AddField(
            model_name='bibliotecaconocimiento',
            name='rag_error_detalle',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Motivo del último fallo de indexación (si aplica).',
                max_length=500,
            ),
        ),
    ]
