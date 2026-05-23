from django.contrib import admin

from core.admin_mixins import register_core_proxy_admin
from core.admin import EventoIAAdmin, MetaMetricaEmpresaAdmin

from .models import EventoIA, MetaMetricaEmpresa

register_core_proxy_admin(admin.site, MetaMetricaEmpresa, MetaMetricaEmpresaAdmin)
register_core_proxy_admin(admin.site, EventoIA, EventoIAAdmin)
