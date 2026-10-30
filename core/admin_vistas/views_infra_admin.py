"""Admin: monitoreo operativo de Redis / DB / S3."""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render

from core.infra_monitor import snapshot_infra


@staff_member_required
def infra_monitor_view(request):
    data = snapshot_infra()
    return render(request, 'admin/infra_monitor.html', {'data': data})


@staff_member_required
def infra_monitor_api(request):
    force = request.GET.get('force') in ('1', 'true', 'yes')
    return JsonResponse(snapshot_infra(force=force))
