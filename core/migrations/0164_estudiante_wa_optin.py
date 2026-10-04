from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0163_usollm'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='wa_optin_fecha',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='wa_optin_origen',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='wa_optin_version',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='wa_optout_fecha',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
