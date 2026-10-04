from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0164_estudiante_wa_optin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enviocampanameta',
            name='estado',
            field=models.CharField(
                choices=[
                    ('PENDIENTE', 'Pendiente'),
                    ('ENVIANDO', 'Enviando'),
                    ('ENVIADO', 'Enviado'),
                    ('ERROR', 'Error'),
                    ('ERROR_REINTENTABLE', 'Error reintentable'),
                    ('INCIERTO', 'Incierto'),
                    ('OMITIDO', 'Omitido'),
                    ('FALLIDO', 'Fallido'),
                ],
                default='FALLIDO',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='enviocampanameta',
            name='wamid',
            field=models.CharField(blank=True, db_index=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='claim_token',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='claimed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='entregado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='error_codigo',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='estado_entrega',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='intentos',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='leido_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='enviocampanameta',
            name='omitido_motivo',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddConstraint(
            model_name='enviocampanameta',
            constraint=models.UniqueConstraint(
                fields=('campana', 'estudiante'),
                name='uniq_envio_meta_campana_estudiante',
            ),
        ),
    ]
