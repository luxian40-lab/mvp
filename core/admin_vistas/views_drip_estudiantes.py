"""Pantalla unificada: drip / módulos por estudiante (sin ir uno por uno)."""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.forms import BaseModelFormSet, modelformset_factory
from django.shortcuts import redirect, render

from core.drip_matriz_service import (
    filas_matriz_modulo,
    habilitaciones_activas_modulo,
    modulos_para_curso,
    sincronizar_habilitaciones_modulo,
)
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, HabilitacionModuloEstudiante, Modulo

DATETIME_LOCAL_FMT = '%Y-%m-%dT%H:%M'


class DripEstudianteForm(forms.ModelForm):
    class Meta:
        model = HabilitacionModuloEstudiante
        fields = ('estudiante', 'curso', 'modulo', 'habilitado_desde', 'activo', 'notas')
        widgets = {
            'habilitado_desde': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format=DATETIME_LOCAL_FMT,
            ),
            'notas': forms.TextInput(attrs={'size': 20}),
        }

    def __init__(self, *args, cliente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['habilitado_desde'].input_formats = [
            DATETIME_LOCAL_FMT,
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y %H:%M',
        ]
        if self.instance and self.instance.pk and self.instance.habilitado_desde:
            dt = self.instance.habilitado_desde
            if timezone.is_aware(dt):
                dt = timezone.localtime(dt)
            self.initial.setdefault('habilitado_desde', dt.strftime(DATETIME_LOCAL_FMT))
        if cliente:
            self.fields['estudiante'].queryset = (
                Estudiante.objects.filter(cliente=cliente, activo=True).order_by('nombre')
            )
            self.fields['curso'].queryset = (
                Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre')
            )
            self.fields['modulo'].queryset = (
                Modulo.objects.filter(curso__cliente=cliente, curso__activo=True).order_by(
                    'curso__orden', 'numero',
                )
            )


class DripEstudianteFormSet(BaseModelFormSet):
    def __init__(self, *args, cliente=None, **kwargs):
        self._cliente = cliente
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['cliente'] = self._cliente
        return super()._construct_form(i, **kwargs)


def _cliente_desde_request(request) -> Cliente | None:
    raw = request.GET.get('cliente') or request.POST.get('cliente')
    if not raw:
        return None
    try:
        return Cliente.objects.get(pk=int(raw), activo=True)
    except (ValueError, Cliente.DoesNotExist):
        return None


def _int_param(request, name: str) -> int | None:
    raw = request.GET.get(name) or request.POST.get(name) or ''
    return int(raw) if str(raw).isdigit() else None


def _redirect_drip(
    cliente_id: int,
    *,
    curso_id=None,
    modulo_id=None,
    estudiante_id=None,
    guardado=False,
    avanzado=False,
):
    q = f'?cliente={cliente_id}'
    if curso_id:
        q += f'&curso={curso_id}'
    if modulo_id:
        q += f'&modulo={modulo_id}'
    if estudiante_id:
        q += f'&estudiante={estudiante_id}'
    if guardado:
        q += '&guardado=1'
    if avanzado:
        q += '&avanzado=1'
    return redirect(f'/admin/drip-estudiantes/{q}')


def _build_formset(cliente: Cliente):
    qs = (
        HabilitacionModuloEstudiante.objects
        .filter(estudiante__cliente=cliente)
        .select_related('estudiante', 'curso', 'modulo')
        .order_by('estudiante__nombre', 'curso__orden', 'modulo__numero')
    )

    DripFormSet = modelformset_factory(
        HabilitacionModuloEstudiante,
        form=DripEstudianteForm,
        formset=DripEstudianteFormSet,
        extra=0,
        can_delete=True,
    )
    return DripFormSet, qs


def _curso_y_modulo_matriz(cliente: Cliente, curso_id: int | None, modulo_id: int | None):
    if not curso_id or not modulo_id:
        return None, None
    try:
        curso = Curso.objects.get(pk=curso_id, cliente=cliente, activo=True)
        modulo = Modulo.objects.get(pk=modulo_id, curso=curso)
    except (Curso.DoesNotExist, Modulo.DoesNotExist):
        return None, None
    return curso, modulo


@staff_member_required
def drip_estudiantes_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    cliente = _cliente_desde_request(request)

    if not cliente:
        return render(request, 'admin/drip_estudiantes.html', {
            'titulo': 'Acceso a módulos por estudiante',
            'clientes': clientes,
            'cliente': None,
        })

    DripFormSet, qs = _build_formset(cliente)
    curso_id = _int_param(request, 'curso')
    modulo_id = _int_param(request, 'modulo')
    estudiante_id = _int_param(request, 'estudiante')

    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    if estudiante_id:
        qs = qs.filter(estudiante_id=estudiante_id)
    if modulo_id:
        qs = qs.filter(modulo_id=modulo_id)

    curso_matriz, modulo_matriz = _curso_y_modulo_matriz(cliente, curso_id, modulo_id)

    if request.method == 'POST' and request.POST.get('action') == 'guardar_matriz':
        if not curso_matriz or not modulo_matriz:
            messages.error(request, 'Elija curso y módulo para asignar accesos.')
            return _redirect_drip(cliente.id, curso_id=curso_id, modulo_id=modulo_id)
        seleccionados = {
            int(pk) for pk in request.POST.getlist('estudiantes_habilitados')
            if str(pk).isdigit()
        }
        try:
            habilitados, desactivados = sincronizar_habilitaciones_modulo(
                cliente, curso_matriz, modulo_matriz, seleccionados,
            )
        except ValueError:
            messages.error(request, 'Curso o módulo no válido para este cliente.')
            return _redirect_drip(cliente.id, curso_id=curso_id, modulo_id=modulo_id)
        messages.success(
            request,
            f'Acceso al módulo M{modulo_matriz.numero}: {habilitados} estudiante(s) habilitado(s)'
            + (f', {desactivados} quitado(s).' if desactivados else '.'),
        )
        return _redirect_drip(
            cliente.id,
            curso_id=curso_matriz.id,
            modulo_id=modulo_matriz.id,
            estudiante_id=estudiante_id,
            guardado=True,
        )

    if request.method == 'POST' and request.POST.get('action') == 'guardar':
        formset = DripFormSet(request.POST, queryset=qs, cliente=cliente)
        if formset.is_valid():
            with transaction.atomic():
                instances = formset.save(commit=False)
                for obj in instances:
                    if obj.estudiante_id and obj.estudiante.cliente_id != cliente.id:
                        messages.error(request, 'Estudiante fuera del cliente seleccionado.')
                        return _redirect_drip(cliente.id, curso_id=curso_id, modulo_id=modulo_id)
                    if obj.curso_id and obj.curso.cliente_id != cliente.id:
                        messages.error(request, 'Curso fuera del cliente seleccionado.')
                        return _redirect_drip(cliente.id, curso_id=curso_id, modulo_id=modulo_id)
                    obj.save()
                for obj in formset.deleted_objects:
                    obj.delete()
            messages.success(request, 'Habilitaciones guardadas (fechas y notas incluidas).')
            return _redirect_drip(
                cliente.id,
                curso_id=curso_id,
                modulo_id=modulo_id,
                estudiante_id=estudiante_id,
                guardado=True,
                avanzado=True,
            )
        messages.error(request, 'Revise los errores del formulario (fechas en formato dd/mm/aaaa hh:mm).')
    else:
        formset = DripFormSet(queryset=qs, cliente=cliente)

    cursos = Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre')
    modulos = modulos_para_curso(cliente, curso_id)
    estudiantes = Estudiante.objects.filter(cliente=cliente, activo=True).order_by('nombre')
    mostrar_tabla_avanzada = (
        request.GET.get('avanzado') == '1'
        or request.POST.get('avanzado') == '1'
        or request.method == 'POST' and request.POST.get('action') == 'guardar'
    )
    total_filas = qs.count()

    matriz_filas = []
    matriz_habilitados = 0
    habilitaciones_guardadas = []
    if curso_matriz and modulo_matriz:
        matriz_filas = filas_matriz_modulo(cliente, curso_matriz, modulo_matriz)
        matriz_habilitados = sum(1 for f in matriz_filas if f['habilitado'])
        habilitaciones_guardadas = list(
            habilitaciones_activas_modulo(cliente, curso_matriz, modulo_matriz)
        )

    return render(request, 'admin/drip_estudiantes.html', {
        'titulo': 'Acceso a módulos por estudiante',
        'clientes': clientes,
        'cliente': cliente,
        'formset': formset,
        'cursos': cursos,
        'modulos': modulos,
        'estudiantes': estudiantes,
        'filtro_curso': curso_id,
        'filtro_modulo': modulo_id,
        'filtro_estudiante': estudiante_id,
        'total_filas': total_filas,
        'drip_lista_activo': cliente.drip_modulos_solo_estudiantes_listados,
        'curso_matriz': curso_matriz,
        'modulo_matriz': modulo_matriz,
        'matriz_filas': matriz_filas,
        'matriz_habilitados': matriz_habilitados,
        'matriz_total': len(matriz_filas),
        'habilitaciones_guardadas': habilitaciones_guardadas,
        'recien_guardado': request.GET.get('guardado') == '1',
        'mostrar_tabla_avanzada': mostrar_tabla_avanzada,
    })
