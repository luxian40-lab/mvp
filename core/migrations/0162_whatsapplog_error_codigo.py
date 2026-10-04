from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0161_whatsapplog_canal'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsapplog',
            name='error_codigo',
            field=models.CharField(
                blank=True,
                help_text='Código de error del proveedor (Graph o Twilio).',
                max_length=16,
                null=True,
            ),
        ),
    ]
