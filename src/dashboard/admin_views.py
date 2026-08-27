"""
View personalizada para o dashboard de administração.
Integra dados de múltiplos modelos do integrador.
"""

import logging

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from dashboard.storage import DashboardStorage

logger = logging.getLogger(__name__)


@staff_member_required
def admin_index_dashboard(request, extra_context=None):
    """
    Dashboard personalizado para a página inicial do admin.
    Agrega dados de ambientes e solicitações de integração.
    """
    context = admin.site.each_context(request)
    storage = DashboardStorage()
    context.update(storage.get_context())

    # Adicionar histórico de ações do usuário
    try:
        log_entries = LogEntry.objects.filter(user=request.user).select_related("user").order_by("-action_time")
    except Exception:
        log_entries = []

    context["log_entries"] = log_entries

    # Garantir título e lista de aplicações para navegação no menu lateral
    context["title"] = admin.site.index_title
    context["subtitle"] = None
    app_list = admin.site.get_app_list(request)
    context["available_apps"] = app_list
    context["app_list"] = app_list

    if extra_context:
        context.update(extra_context)

    return render(request, "admin/index.html", context)

