from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0160_webhook_fallido'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsapplog',
            name='canal',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='meta o twilio. Vacío en el histórico: no abre la ventana de la línea Meta.',
                max_length=16,
            ),
        ),
    ]
