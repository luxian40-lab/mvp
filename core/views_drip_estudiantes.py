"""Pantalla unificada: drip / módulos por estudiante (sin ir uno por uno)."""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.forms import BaseModelFormSet, modelformset_factory
from django.shortcuts import redirect, render

from core.models import Cliente, Curso, Estudiante, HabilitacionModuloEstudiante, Modulo


class DripEstudianteForm(forms.ModelForm):
    class Meta:
        model = HabilitacionModuloEstudiante
        fields = ('estudiante', 'curso', 'modulo', 'habilitado_desde', 'activo', 'notas')
        widgets = {
            'habilitado_desde': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notas': forms.TextInput(attrs={'size': 20}),
        }

    def __init__(self, *args, cliente=None, **kwargs):
        super().__init__(*args, **kwargs)
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
        extra=5,
        can_delete=True,
    )
    return DripFormSet, qs


@staff_member_required
def drip_estudiantes_view(request):
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    cliente = _cliente_desde_request(request)

    if not cliente:
        return render(request, 'admin/drip_estudiantes.html', {
            'titulo': 'Módulos por estudiante',
            'clientes': clientes,
            'cliente': None,
        })

    DripFormSet, qs = _build_formset(cliente)
    filtro_curso = request.GET.get('curso') or request.POST.get('curso') or ''
    filtro_estudiante = request.GET.get('estudiante') or request.POST.get('estudiante') or ''
    curso_id = int(filtro_curso) if str(filtro_curso).isdigit() else None
    estudiante_id = int(filtro_estudiante) if str(filtro_estudiante).isdigit() else None

    if curso_id:
        qs = qs.filter(curso_id=curso_id)
    if estudiante_id:
        qs = qs.filter(estudiante_id=estudiante_id)

    if request.method == 'POST' and request.POST.get('action') == 'guardar':
        formset = DripFormSet(request.POST, queryset=qs, cliente=cliente)
        if formset.is_valid():
            with transaction.atomic():
                instances = formset.save(commit=False)
                for obj in instances:
                    if obj.estudiante_id and obj.estudiante.cliente_id != cliente.id:
                        messages.error(request, 'Estudiante fuera del cliente seleccionado.')
                        return redirect(f'/admin/drip-estudiantes/?cliente={cliente.id}')
                    if obj.curso_id and obj.curso.cliente_id != cliente.id:
                        messages.error(request, 'Curso fuera del cliente seleccionado.')
                        return redirect(f'/admin/drip-estudiantes/?cliente={cliente.id}')
                    obj.save()
                for obj in formset.deleted_objects:
                    obj.delete()
            messages.success(request, 'Habilitaciones guardadas.')
            q = f'?cliente={cliente.id}'
            if curso_id:
                q += f'&curso={curso_id}'
            if estudiante_id:
                q += f'&estudiante={estudiante_id}'
            return redirect(f'/admin/drip-estudiantes/{q}')
        messages.error(request, 'Revise los errores del formulario.')
    else:
        formset = DripFormSet(queryset=qs, cliente=cliente)

    cursos = Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre')
    estudiantes = Estudiante.objects.filter(cliente=cliente, activo=True).order_by('nombre')[:500]
    total_filas = qs.count()

    return render(request, 'admin/drip_estudiantes.html', {
        'titulo': 'Módulos por estudiante',
        'clientes': clientes,
        'cliente': cliente,
        'formset': formset,
        'cursos': cursos,
        'estudiantes': estudiantes,
        'filtro_curso': curso_id,
        'filtro_estudiante': estudiante_id,
        'total_filas': total_filas,
        'drip_lista_activo': cliente.drip_modulos_solo_estudiantes_listados,
    })
