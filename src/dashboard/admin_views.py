"""
View personalizada para o dashboard de administração.
Integra dados de múltiplos modelos do integrador.
"""

import logging

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

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


@staff_member_required
def admin_app_index_dashboard(request, app_label, extra_context=None):
    """
    Dashboard personalizado para as páginas de índice de cada aplicação do admin.
    """
    context = admin.site.each_context(request)
    storage = DashboardStorage()

    app_dict = admin.site._build_app_dict(request, app_label)
    if isinstance(app_dict, dict) and app_label in app_dict:
        app_dict = app_dict[app_label]

    if not app_dict or not isinstance(app_dict, dict) or "name" not in app_dict:
        raise Http404(_("App não encontrada."))

    if app_label == "auth":
        context.update(storage.get_auth_context())
    elif app_label == "cohort":
        context.update(storage.get_cohort_context())
    elif app_label == "integrador":
        context.update(storage.get_integrador_context())

    context["title"] = app_dict.get("name", app_label)
    context["subtitle"] = None
    context["app_label"] = app_label
    context["app_dict"] = app_dict
    context["app_list"] = [app_dict]
    context["available_apps"] = admin.site.get_app_list(request)

    if extra_context:
        context.update(extra_context)

    template_list = [f"admin/{app_label}/app_index.html", "admin/app_index.html"]
    return render(request, template_list, context)
