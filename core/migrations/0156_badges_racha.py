from django.db import migrations

BADGES_RACHA = [
    (3, 'Constancia', '3 días seguidos aprendiendo con eki.'),
    (7, 'Semana firme', '7 días seguidos aprendiendo con eki.'),
    (14, 'Dos semanas', '14 días seguidos aprendiendo con eki.'),
    (21, 'Hábito', '21 días seguidos: el aprendizaje ya es hábito.'),
    (30, 'Mes completo', '30 días seguidos aprendiendo con eki.'),
]


def crear_badges_racha(apps, schema_editor):
    Badge = apps.get_model('core', 'Badge')
    for orden, (dias, nombre, descripcion) in enumerate(BADGES_RACHA, start=1):
        if Badge.objects.filter(tipo='RACHA', valor_requerido=dias).exists():
            continue
        Badge.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            icono='',
            tipo='RACHA',
            valor_requerido=dias,
            orden=100 + orden,
            activo=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0155_conocimiento_agente'),
    ]

    operations = [
        migrations.RunPython(crear_badges_racha, migrations.RunPython.noop),
    ]
