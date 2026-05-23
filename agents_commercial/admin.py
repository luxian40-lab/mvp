from django.contrib import admin

from core.admin_mixins import register_core_proxy_admin
from core.admin import (
    CampanaB2BAdmin,
    ContextoAgroSessionAdmin,
    ConversacionRAGCandidataAdmin,
    DocumentoRAGComercialAdmin,
    MetaMetricaNatiAdmin,
    ProspectoB2BAdmin,
)

from .models import (
    CampanaB2B,
    ContextoAgroSession,
    ConversacionRAGCandidata,
    DocumentoRAGComercial,
    MetaMetricaNati,
    ProspectoB2B,
)

register_core_proxy_admin(admin.site, ProspectoB2B, ProspectoB2BAdmin)
register_core_proxy_admin(admin.site, CampanaB2B, CampanaB2BAdmin)
register_core_proxy_admin(admin.site, DocumentoRAGComercial, DocumentoRAGComercialAdmin)
register_core_proxy_admin(admin.site, MetaMetricaNati, MetaMetricaNatiAdmin)
register_core_proxy_admin(admin.site, ContextoAgroSession, ContextoAgroSessionAdmin)
register_core_proxy_admin(admin.site, ConversacionRAGCandidata, ConversacionRAGCandidataAdmin)
