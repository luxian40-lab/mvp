from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0202_sesion_registro_cliente'),
    ]

    operations = [
        migrations.CreateModel(
            name='EntradaBandeja',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canal', models.CharField(max_length=16)),
                ('external_id', models.CharField(max_length=128)),
                ('telefono', models.CharField(max_length=32)),
                ('secuencia', models.PositiveIntegerField()),
                ('estado', models.CharField(default='PENDIENTE', max_length=16)),
                ('intentos', models.PositiveSmallIntegerField(default=0)),
                ('ultimo_error', models.TextField(blank=True)),
                ('payload', models.JSONField(default=dict)),
                ('creado', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'entrada de bandeja',
                'verbose_name_plural': 'entradas de bandeja',
                'indexes': [
                    models.Index(fields=['telefono', 'estado', 'secuencia'], name='entrada_bandeja_cabeza'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('canal', 'external_id'), name='uniq_entrada_bandeja_externo'),
                    models.UniqueConstraint(fields=('telefono', 'secuencia'), name='uniq_entrada_bandeja_secuencia'),
                ],
            },
        ),
    ]
