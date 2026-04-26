import factory
from factory.django import DjangoModelFactory

from core.models import Cliente, Curso, Estudiante, Modulo


class ClienteFactory(DjangoModelFactory):
    class Meta:
        model = Cliente

    nombre = factory.Sequence(lambda n: f"Organización {n}")
    contacto_principal = "Contacto"
    email = factory.LazyAttribute(lambda o: f"org{o.nombre}@test.co")
    telefono = "573001230000"


class EstudianteFactory(DjangoModelFactory):
    class Meta:
        model = Estudiante

    cedula = factory.Sequence(lambda n: f"GEI{n:06d}")
    nombre = factory.Faker("name", locale="es_CO")
    telefono = factory.Sequence(lambda n: f"57300{n:07d}")
    cliente = factory.SubFactory(ClienteFactory)
    estado_onboarding = "completado"
    estado_chat = "ACTIVO"
    acepto_terminos = True


class CursoFactory(DjangoModelFactory):
    class Meta:
        model = Curso

    nombre = factory.Sequence(lambda n: f"Curso GEI {n}")
    descripcion = "Curso de prueba"
    activo = True
    emoji = "🌱"


class ModuloFactory(DjangoModelFactory):
    class Meta:
        model = Modulo

    curso = factory.SubFactory(CursoFactory)
    numero = 1
    titulo = "Módulo"
    descripcion = "Desc"
    contenido = "Contenido"
    duracion_dias = 1
