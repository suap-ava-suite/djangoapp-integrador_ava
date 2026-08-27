import logging
from functools import update_wrapper

import requests
from django.conf import settings
from django.contrib.admin import display, register
from django.db import transaction
from django.db.models import JSONField
from django.forms import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.timezone import localtime
from django.utils.translation import gettext as _
from django_json_widget.widgets import JSONEditorWidget
from import_export.resources import ModelResource

from base.admin import BaseModelAdmin
from integrador.brokers.suap2local_suap import Suap2LocalSuapBroker
from integrador.models import Ambiente, Solicitacao

logger = logging.getLogger(__name__)


####
# Admins
####
@register(Ambiente)
class AmbienteAdmin(BaseModelAdmin):
    class AmbienteResource(ModelResource):
        class Meta:
            model = Ambiente
            export_order = (
                "nome",
                "url",
                "local_suap_token",
                "local_suap_active",
                "tool_sga_token",
                "tool_sga_active",
                "expressao_seletora",
                "ordem",
            )
            import_id_fields = ("nome",)
            fields = export_order
            skip_unchanged = True

    list_display = ["nome", "checked_url", "checked_expressao_seletora", "checked_local_suap", "checked_tool_sga"]
    history_list_display = list_display
    field_to_highlight = list_display[0]
    search_fields = ["nome", "url"]
    list_filter = []
    fieldsets = [
        (_("Identificação"), {"fields": ["nome", "url", "expressao_seletora", "ordem"]}),
        (_("Local SUAP"), {"fields": ["local_suap_active", "local_suap_token"]}),
        (_("Tool SGA"), {"fields": ["tool_sga_active", "tool_sga_token"]}),
    ]
    resource_classes = [AmbienteResource]

    def get_queryset(self, request):
        """Otimiza queryset para evitar N+1 queries."""
        return super().get_queryset(request).all()

    @display(description="URL")
    def checked_url(self, obj):
        validation_error = format_html(
            '<span title="{}"> {}</span>',
            "Erro ao tentar validar a URL deste AVA.",
            "🚫",
        )
        validation_success = format_html(
            '<span title="{}"> {}</span>',
            "A URL deste AVA foi validada com sucesso.",
            "✅",
        )
        try:
            response = requests.get(f"{obj.url}/version.php", timeout=1)
            message = validation_success if response.status_code == 200 else validation_error
        except Exception:
            message = validation_error
        return format_html('{}<a href="{}">{}🔗</a>', message, obj.url, obj.url)

    @display(description="Expressão Seletora")
    def checked_expressao_seletora(self, obj):
        if obj.expressao_seletora is None or obj.expressao_seletora.strip() == "":
            title = "Não configurada"
            status = "⚠️"
            color = "orange"
        elif obj.valid_expressao_seletora:
            title = "Regra validada com sucesso."
            status = "✅"
            color = "green"
        else:
            title = "Regra inválida."
            status = "🚫"
            color = "red"

        es = obj.expressao_seletora or ""
        return format_html(
            '<span title="{title}"> {status}</span><span style="color: {color};">{expressao_seletora}</span>',
            expressao_seletora=(es if es.strip() != "" else ""),
            title=title,
            status=status,
            color=color,
        )

    def _integration_badge(self, obj, active, token_field, api_path, label):
        token = getattr(obj, token_field)
        has_token = bool(token and str(token).strip())

        if not active and not has_token:
            return format_html('<span title="{}">🚫</span>', f"{label}: inativo e sem token.")

        if not active:
            return format_html('<span title="{}">⏸️</span>', f"{label}: token configurado, mas inativo.")

        if not has_token:
            return format_html('<span title="{}">⚠️</span>', f"{label}: ativo, mas sem token configurado.")
        try:
            response = requests.get(
                f"{obj.base_url}{api_path}",
                headers={"Authentication": f"Token {token}"},
                timeout=3,
            )
            if response.status_code == 200:
                data = response.json()
                title = (
                    f"{label}: OK — plugin {data.get('plugin_release', '?')} / Moodle {data.get('moodle_release', '?')}"
                )
                return format_html('<span title="{}">✅</span>', title)
            elif response.status_code == 401:
                return format_html('<span title="{}">🔑</span>', f"{label}: token inválido (401).")
            else:
                return format_html(
                    '<span title="{}">❌</span>', f"{label}: resposta inesperada ({response.status_code})."
                )
        except Exception as e:
            return format_html('<span title="{}">⛔</span>', f"{label}: erro ao contactar o plugin — {e}.")

    @display(description="Local SUAP")
    def checked_local_suap(self, obj):
        return self._integration_badge(
            obj, obj.local_suap_active, "local_suap_token", "/local/suap/api/index.php?health", "Local SUAP"
        )

    @display(description="Tool SGA")
    def checked_tool_sga(self, obj):
        return self._integration_badge(
            obj, obj.tool_sga_active, "tool_sga_token", "/admin/tool/sga/api/index.php?health", "Tool SGA"
        )


@register(Solicitacao)
class SolicitacaoAdmin(BaseModelAdmin):
    list_display = (
        "requisicao",
        "origem",
        "links",
        "professores",
        "acoes",
    )
    list_filter = ("operacao", "tipo", "ambiente", "status", "status_code", "campus_sigla")

    search_fields = ["diario_codigo", "diario_id"]
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)

    def get_queryset(self, request):
        """Otimiza queryset para evitar N+1 queries ao acessar ForeignKey 'ambiente'."""
        return super().get_queryset(request).select_related("ambiente")

    class SolicitacaoAdminForm(ModelForm):
        class Meta:
            model = Solicitacao
            widgets = {
                "recebido": JSONEditorWidget(),
                "enviado": JSONEditorWidget(),
                "respondido": JSONEditorWidget(),
            }
            fields = "__all__"
            readonly_fields = ["timestamp"]

    formfield_overrides = {JSONField: {"widget": JSONEditorWidget}}
    form = SolicitacaoAdminForm

    @display(description="Requisição", ordering="timestamp")
    def requisicao(self, obj):
        if obj.timestamp:
            nbspace = "\u00a0"
            horalocal_dt = localtime(obj.timestamp)
            horalocal = horalocal_dt.strftime("%d/%m/%Y" + nbspace + "%H:%M:%S")
            clock_icons = ["🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"]
            hora = clock_icons[horalocal_dt.hour % 12]
        else:
            horalocal = None
            hora = "🕛"
        return format_html(
            "{}{}<br>{}{}<br>{}<br>📄{}",
            hora,
            horalocal or "-",
            Solicitacao.Operacao(obj.operacao).icon,
            obj.operacao,
            obj.status_merged,
            obj.tipo,
        )

    @display(description="Contexto")
    def origem(self, obj):
        return format_html("{}<br>{}", obj.ambiente, obj.campus_sigla)

    @display(description="Ações")
    def acoes(self, obj):
        if obj.operacao == Solicitacao.Operacao.SYNC_UP_DIARIO:
            return format_html(
                '<a class="export_link" href="{}">Reenviar</a>',
                reverse("admin:integrador_solicitacao_sync", args=[obj.id]),
            )
        return "-"

    @display(description="Professores")
    def professores(self, obj):
        try:
            professores = []
            for p in (obj.recebido or {}).get("professores", []):
                username = p.get("login", None)
                urlpath = (
                    "/admin/comum/prestadorservico/?q="
                    if username and len(username) > 10
                    else "/admin/rh/servidor/?ativo__exact=1&q="
                )
                vinculo = "externo" if username and len(username) > 10 else "servidor"
                professores.append(
                    format_html(
                        '<li><a href="{}{}{}">{} ({}:{})</a></li>',
                        settings.SUAP_BASE_URL,
                        urlpath,
                        username or "",
                        p.get("nome", "-"),
                        p.get("tipo", "-"),
                        vinculo,
                    ),
                )

            if not professores:
                return "-"

            return format_html("<ul>{}</ul>", format_html_join("", "{}", ((p,) for p in professores)))
        except Exception:
            return "-"

    @display(description="Links")
    def links(self, obj):
        try:
            respondido = obj.respondido if obj and isinstance(obj.respondido, dict) else {}
            items = []

            url = respondido.get("url")
            if url:
                items.append(format_html('<li><a href="{}">{}</a></li>', url, obj.diario_codigo or "-"))
            elif obj.diario_codigo:
                items.append(
                    format_html(
                        '<li><a href="{}/course/management.php?search={}">{}</a></li>',
                        obj.ambiente.base_url,
                        obj.diario_codigo,
                        obj.diario_codigo or "-",
                    )
                )

            url_sala_coordenacao = respondido.get("url_sala_coordenacao")
            if url_sala_coordenacao:
                items.append(format_html('<li><a href="{}">Sala de coordenação</a></li>', url_sala_coordenacao))
            elif obj.diario_codigo:
                items.append(
                    format_html(
                        '<li><a href="{}/course/management.php?search={}">Sala de coordenação</a></li>',
                        obj.ambiente.base_url,
                        obj.diario_codigo,
                    )
                )

            if obj.diario_id:
                items.append(
                    format_html(
                        '<li><a href="{}/edu/meu_diario/{}/1/">Diário no SUAP</a></li>',
                        settings.SUAP_BASE_URL,
                        obj.diario_id,
                    )
                )

            sincronizacao_url = respondido.get("sincronizacao_url")
            if sincronizacao_url:
                items.append(
                    format_html('<li><a href="{}" target="_blank">Sincronização no Moodle</a></li>', sincronizacao_url)
                )

            if not items:
                return "-"

            return format_html("<ul>{}</ul>", format_html_join("", "{}", ((item,) for item in items)))
        except Exception:
            return "-"

    def get_urls(self):
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name
        return [
            path(
                "<path:object_id>/sync_moodle/",
                wrap(self.sync_moodle_view),
                name="%s_%s_sync" % info,
            )
        ] + super().get_urls()

    @transaction.atomic
    def sync_moodle_view(self, request, object_id, form_url="", extra_context=None):
        original = get_object_or_404(Solicitacao, pk=object_id)
        solicitacao = Solicitacao.objects.create(
            ambiente=original.ambiente,
            campus_sigla=original.campus_sigla,
            diario_codigo=original.diario_codigo,
            diario_id=original.diario_id,
            operacao=original.operacao,
            tipo=original.tipo,
            recebido=original.recebido,
        )

        solicitacao.site_url = request.build_absolute_uri("/")
        try:
            respondido = Suap2LocalSuapBroker(solicitacao).sync_up_enrolments()
            if not respondido:
                raise ValueError("Erro desconhecido")
            solicitacao.respondido = respondido
            solicitacao.status = Solicitacao.Status.SUCESSO
            solicitacao.status_code = "200"
            solicitacao.save()
            return HttpResponseRedirect(reverse("admin:integrador_solicitacao_changelist"))
        except Exception as e:
            solicitacao.status = Solicitacao.Status.FALHA
            solicitacao.status_code = getattr(e, "code", "500")
            solicitacao.save()
            logger.exception(f"Error while syncing Moodle for Solicitacao {getattr(original, 'id', '-')}. ERROR: {e}")
            return render(
                request,
                "integrador/sync_error.html",
                context={"error_cause": str(e), "solicitacao": original},
                status=200,
            )
