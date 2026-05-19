"""
Bounded contexts de Eki (Parte 0 — separación de dominios).

Cada subpaquete agrupa lógica de un dominio sin romper imports legacy en ``core/``.
Nuevas features deben importar desde aquí; el código existente se migra gradualmente.
"""

from core.domains.registry import DOMAIN_REGISTRY, get_domain

__all__ = ['DOMAIN_REGISTRY', 'get_domain']
