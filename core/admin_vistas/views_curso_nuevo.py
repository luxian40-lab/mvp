# -*- coding: utf-8 -*-
"""Asistente «Curso nuevo» — única puerta de alta. Aterriza en módulo modo Clase."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.admin.cursos import sembrar_plantilla_modulo
from core.models import Cliente, Curso, Modulo
from core.modulo_authoring_mode import MODO_CLASE, set_modulo_modo


@staff_member_required
@require_http_methods(['GET', 'POST'])
def curso_nuevo_wizard(request):
    """
    Alta corta: nombre + org + experiencia + N módulos → primer módulo en modo Clase (A).
    El Builder (B) se abre después, solo si el staff elige «Armar por partes».
    """
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')
    errores = []
    initial = {
        'nombre': '',
        'descripcion': '',
        'cliente_id': '',
        'modo_aula': Curso.MODO_AULA_MODULOS,
        'n_modulos': 3,
    }

    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        descripcion = (request.POST.get('descripcion') or '').strip()
        cliente_id = (request.POST.get('cliente_id') or '').strip()
        modo_aula = (request.POST.get('modo_aula') or Curso.MODO_AULA_MODULOS).strip()
        try:
            n_modulos = int(request.POST.get('n_modulos') or 1)
        except (TypeError, ValueError):
            n_modulos = 0

        initial.update(
            {
                'nombre': nombre,
                'descripcion': descripcion,
                'cliente_id': cliente_id,
                'modo_aula': modo_aula,
                'n_modulos': n_modulos or 1,
            }
        )

        if not nombre:
            errores.append('Escriba el nombre del curso.')
        if modo_aula not in (Curso.MODO_AULA_MODULOS, Curso.MODO_AULA_CLASES):
            errores.append('Elija la experiencia del curso.')
        if n_modulos < 1 or n_modulos > 20:
            errores.append('Número de módulos: entre 1 y 20.')

        cliente = None
        if cliente_id:
            cliente = Cliente.objects.filter(pk=cliente_id, activo=True).first()
            if cliente is None:
                errores.append('Organización no válida.')

        if not errores:
            with transaction.atomic():
                curso = Curso.objects.create(
                    nombre=nombre[:200],
                    descripcion=descripcion or f'Curso {nombre}',
                    cliente=cliente,
                    modo_aula=modo_aula,
                    activo=True,
                    visible_en_studio=False,
                    visible_en_aula=True,
                    usar_gamificacion=(modo_aula == Curso.MODO_AULA_MODULOS),
                )
                primer_mod = None
                for i in range(1, n_modulos + 1):
                    mod = Modulo.objects.create(
                        curso=curso,
                        numero=i,
                        titulo=f'Módulo {i}',
                        descripcion=f'Módulo {i} de {nombre}',
                        contenido='',
                        modo_entrega=Modulo.MODO_ENTREGA_PASOS,
                        publicado_wa=False,
                    )
                    sembrar_plantilla_modulo(mod)
                    if primer_mod is None:
                        primer_mod = mod

            messages.success(
                request,
                f'Curso «{curso.nombre}» creado con {n_modulos} módulo(s). '
                'Complete el primero (texto + archivo). '
                'Para WhatsApp por partes use «Armar por partes».',
            )
            if primer_mod:
                set_modulo_modo(request, primer_mod.pk, MODO_CLASE)
                return redirect(
                    reverse('admin:core_modulo_change', args=[primer_mod.pk])
                    + '?modo=clase'
                )
            return redirect('admin:core_curso_change', curso.pk)

        for e in errores:
            messages.error(request, e)

    return render(
        request,
        'admin/curso_nuevo.html',
        {
            'title': 'Curso nuevo',
            'clientes': clientes,
            'form': initial,
            'modo_choices': Curso.MODO_AULA_CHOICES,
        },
    )
