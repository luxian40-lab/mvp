from django.db import migrations, models


def normalizar_canales(apps, schema_editor):
    DocumentoRAGComercial = apps.get_model('core', 'DocumentoRAGComercial')
    DocumentoRAGComercial.objects.filter(canal='agro_nexo').update(canal='bot_comercial')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0073_alter_documentoragcomercial_canal_and_more'),
    ]

    operations = [
        migrations.RunPython(normalizar_canales, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='documentoragcomercial',
            name='canal',
            field=models.CharField(
                choices=[('bot_comercial', 'Bot Comercial WhatsApp')],
                default='bot_comercial',
                max_length=40,
                verbose_name='Canal comercial',
            ),
        ),
    ]
