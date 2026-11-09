from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0203_bandeja_entrada'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutboxEnvio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('correlacion', models.CharField(max_length=64, unique=True)),
                ('canal', models.CharField(max_length=16)),
                ('telefono', models.CharField(max_length=32)),
                ('phone_id', models.CharField(blank=True, default='', max_length=32)),
                ('estado', models.CharField(db_index=True, default='PENDIENTE', max_length=20)),
                ('wamid', models.CharField(blank=True, default='', max_length=200)),
                ('codigo_error', models.CharField(blank=True, default='', max_length=32)),
                ('claim_token', models.UUIDField(blank=True, null=True)),
                ('intento_en', models.DateTimeField(blank=True, null=True)),
                ('intentos', models.PositiveSmallIntegerField(default=0)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Outbox de envío',
                'verbose_name_plural': 'Outbox de envíos',
            },
        ),
        migrations.AddIndex(
            model_name='outboxenvio',
            index=models.Index(fields=['estado', 'intento_en'], name='outbox_envio_enviando'),
        ),
    ]
