from django.contrib import admin

from core.admin_mixins import register_core_proxy_admin
from core.admin import DocumentoRAGAdmin

from .models import DocumentoRAG

register_core_proxy_admin(admin.site, DocumentoRAG, DocumentoRAGAdmin)
