from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0117_biblioteca_rag_error_detalle'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentoragcomercial',
            name='error_indexacion',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Motivo del último fallo de indexación RAG.',
                max_length=500,
            ),
        ),
    ]
