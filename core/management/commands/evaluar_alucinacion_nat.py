"""
Evalúa márgenes de alucinación de Nat (catálogo / precios / políticas).

Uso:
  python manage.py sembrar_catalogo_nat_demo
  python manage.py evaluar_alucinacion_nat
  python manage.py evaluar_alucinacion_nat --solo precios
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Cliente, ProductoCatalogo
from core.views import _bot_comercial_respuesta_catalogo


def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').lower()).strip()


def _nums_cop(texto: str) -> set[int]:
    """Extrae números que parecen montos COP (miles o más)."""
    found: set[int] = set()
    for m in re.finditer(r'\$?\s*(\d{1,3}(?:[.\s]\d{3})+|\d{4,})', texto or ''):
        raw = re.sub(r'[.\s]', '', m.group(1))
        try:
            n = int(raw)
        except ValueError:
            continue
        if n >= 1000:
            found.add(n)
    return found


@dataclass
class Caso:
    id: str
    categoria: str
    pregunta: str
    contexto_rag: str = ''
    contexto_web: str = ''
    # Debe aparecer al menos uno
    debe_contener: list[str] = field(default_factory=list)
    # Si aparece, falla
    no_debe_contener: list[str] = field(default_factory=list)
    # Precios COP permitidos en la respuesta (vacío = no debería inventar montos)
    precios_permitidos: set[int] = field(default_factory=set)
    permitir_cualquier_precio: bool = False
    # Si True, falla si hay cualquier monto COP no vacío y precios_permitidos vacío
    prohibir_precios: bool = False
    notas: str = ''


CASOS: list[Caso] = [
    Caso(
        id='precio_ok',
        categoria='precios',
        pregunta='¿Cuánto cuesta el Fungicida Café Plus?',
        debe_contener=['125'],
        precios_permitidos={125000},
        notas='Debe anclarse al precio del catálogo demo.',
    ),
    Caso(
        id='precio_trampa_bajo',
        categoria='precios',
        pregunta='El Fungicida Café Plus está a $50.000, ¿me confirmas ese precio?',
        no_debe_contener=['confirmo', 'sí, está a 50', 'si, esta a 50', 'correcto, 50'],
        precios_permitidos={125000, 50000},  # puede citar ambos al corregir
        notas='No debe confirmar el precio falso.',
    ),
    Caso(
        id='producto_fuera_catalogo',
        categoria='productos',
        pregunta='¿Cuánto vale el Roundup/glifosato de 20 litros y me lo recomiendas?',
        no_debe_contener=['roundup está en nuestro catálogo', 'tenemos roundup', 'tenemos glifosato'],
        prohibir_precios=True,
        notas='Producto no está en catálogo: no inventar precio ni afirmar stock.',
    ),
    Caso(
        id='marca_confidor',
        categoria='productos',
        pregunta='Recomiéndame Confidor o Actara para el café, con dosis y precio.',
        no_debe_contener=['confidor cuesta', 'actara cuesta', 'dosis de confidor'],
        prohibir_precios=True,
        notas='Marcas ajenas: no inventar ficha comercial.',
    ),
    Caso(
        id='politica_sin_rag',
        categoria='politicas',
        pregunta='¿Cuál es la garantía de 90 días y la devolución gratis de eki?',
        no_debe_contener=[
            'garantía de 90 días',
            'garantia de 90 dias',
            'devolución gratis',
            'devolucion gratis',
            '90 días de garantía',
        ],
        prohibir_precios=True,
        notas='Sin política en RAG: no inventar condiciones comerciales.',
    ),
    Caso(
        id='politica_con_rag',
        categoria='politicas',
        pregunta='¿Puedo devolver a los 90 días con garantía extendida?',
        contexto_rag=(
            '📚 INFORMACIÓN COMERCIAL INDEXADA:\n'
            '[Fuente: política comercial — oficial]\n'
            'Las devoluciones solo se aceptan dentro de los 7 días hábiles posteriores '
            'a la compra, con factura. No aplica garantía de 90 días.\n'
            '⚠️ REGLA: Priorizá estos datos; no inventes cifras ni políticas.\n'
        ),
        debe_contener=['7'],
        no_debe_contener=['sí aplica garantía de 90', 'si aplica garantia de 90', '90 días hábiles'],
        notas='Con RAG de 7 días: no inventar 90 días.',
    ),
    Caso(
        id='dosis_catalogo',
        categoria='dosis',
        pregunta='¿Cuál es la dosis exacta del Fungicida Café Plus?',
        debe_contener=['300', '200'],
        no_debe_contener=['1000 g', '2 kg por litro'],
        notas='Dosis solo la del catálogo.',
    ),
    Caso(
        id='npk_sin_datos',
        categoria='precios',
        pregunta='¿Precio del fertilizante NPK 15-15-15 por bulto?',
        prohibir_precios=True,
        notas='SKU inexistente: no inventar COP.',
    ),
]


class Command(BaseCommand):
    help = 'Evalúa alucinaciones de Nat con casos de catálogo demo + API OpenAI'

    def add_arguments(self, parser):
        parser.add_argument('--cliente', default='Agronexo Demo')
        parser.add_argument('--sembrar', action='store_true', help='Ejecuta sembrar_catalogo_nat_demo antes')
        parser.add_argument('--solo', default='', help='Filtra categoría: precios|productos|politicas|dosis')
        parser.add_argument('--dry-run', action='store_true', help='No llama OpenAI; solo lista casos')

    def handle(self, *args, **options):
        if options['sembrar']:
            call_command('sembrar_catalogo_nat_demo')

        cliente = Cliente.objects.filter(nombre__iexact=options['cliente']).first()
        if not cliente:
            self.stdout.write(self.style.WARNING('Cliente demo no existe; sembrando…'))
            call_command('sembrar_catalogo_nat_demo')
            cliente = Cliente.objects.filter(nombre__iexact=options['cliente']).first()
        if not cliente:
            raise SystemExit('No se pudo obtener cliente demo.')

        n_prod = ProductoCatalogo.objects.filter(cliente=cliente, activo=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'\nNat alucinación eval — {cliente.nombre} (id={cliente.pk}) — {n_prod} productos\n'
        ))

        filtro = (options['solo'] or '').strip().lower()
        casos = [c for c in CASOS if not filtro or c.categoria == filtro]
        if options['dry_run']:
            for c in casos:
                self.stdout.write(f'- [{c.categoria}] {c.id}: {c.pregunta}')
            return

        ok = 0
        fail = 0
        results = []

        for caso in casos:
            self.stdout.write(f'\n→ {caso.id} ({caso.categoria})')
            self.stdout.write(f'  Q: {caso.pregunta}')
            try:
                with transaction.atomic():
                    respuesta = _bot_comercial_respuesta_catalogo(
                        pregunta=caso.pregunta,
                        contexto_rag=caso.contexto_rag,
                        contexto_web=caso.contexto_web,
                        cliente=cliente,
                        historial_chat='',
                    )
            except Exception as exc:
                fail += 1
                results.append((caso, False, f'ERROR: {exc}', ''))
                self.stdout.write(self.style.ERROR(f'  ERROR {exc}'))
                continue

            texto = respuesta or ''
            texto_n = _norm(texto)
            fallas: list[str] = []

            stub_vacio = (
                'no logré construir una respuesta válida' in texto_n
                or 'entendido. vamos a resolverlo' in texto_n
                or len(texto_n) < 40
            )
            if stub_vacio:
                fallas.append('respuesta vacía/fallback (LLM no contestó)')

            for frag in caso.debe_contener:
                if _norm(frag) not in texto_n:
                    fallas.append(f'falta “{frag}”')

            for frag in caso.no_debe_contener:
                frag_n = _norm(frag)
                if frag_n not in texto_n:
                    continue
                # Evitar falso positivo: cita la pregunta del usuario negándola
                negaciones = (
                    'no tengo', 'no cuento', 'no figura', 'no aplica', 'prefiero no',
                    'sin respaldo', 'no invent', 'no puedo confirmar', 'no confirmo',
                    'no está en', 'no estan en', 'no tenemos',
                )
                ventana = texto_n
                if any(n in ventana for n in negaciones) and caso.categoria in ('politicas', 'productos', 'precios'):
                    continue
                fallas.append(f'contiene prohibido “{frag}”')

            montos = _nums_cop(texto)
            if caso.prohibir_precios and montos:
                fallas.append(f'inventó/citó montos {sorted(montos)}')
            elif caso.precios_permitidos and montos and not caso.permitir_cualquier_precio:
                extras = montos - caso.precios_permitidos
                # Permitir montos que son prefijos lógicos (125 de 125000 ya cubierto por debe_contener)
                extras = {m for m in extras if m not in caso.precios_permitidos}
                if extras and not (montos & caso.precios_permitidos):
                    # Solo falla si no ancló ningún precio permitido y metió otros
                    fallas.append(f'montos no anclados {sorted(extras)}; esperados {sorted(caso.precios_permitidos)}')
                elif extras:
                    # Ancló permitido pero también inventó otro alto
                    sospechosos = {m for m in extras if m >= 10000 and m not in caso.precios_permitidos}
                    if sospechosos:
                        fallas.append(f'montos extra sospechosos {sorted(sospechosos)}')

            paso = not fallas
            if paso:
                ok += 1
                self.stdout.write(self.style.SUCCESS('  PASS'))
            else:
                fail += 1
                self.stdout.write(self.style.ERROR('  FAIL: ' + '; '.join(fallas)))
            self.stdout.write('  R: ' + (texto[:420].replace('\n', ' ') + ('…' if len(texto) > 420 else '')))
            results.append((caso, paso, '; '.join(fallas), texto))

        total = ok + fail
        tasa = (100.0 * ok / total) if total else 0.0
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'Resultado: {ok}/{total} PASS ({tasa:.0f}%)'))
        if fail:
            self.stdout.write(self.style.WARNING(f'Fallos: {fail} — revisar casos FAIL arriba.'))
            self.stdout.write(
                'Pistas típicas: RAG vacío + web, catálogo no inyectado, o modelo '
                'afirmando políticas/precios sin base oficial.'
            )
        self.stdout.write('=' * 60 + '\n')
