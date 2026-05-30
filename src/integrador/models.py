import json
from pathlib import Path

from django.db.models import (
    PROTECT,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    JSONField,
    Manager,
    Model,
    TextField,
)
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django_better_choices import Choices
from rule_engine import Rule

from sga.db.fields import PermissiveURLField

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class Ambiente(Model):
    class AmbienteManager(Manager):
        def seleciona_ambiente(self, sync_json: dict) -> Model:
            ambientes = list(Ambiente.objects.all())
            for a in ambientes:
                if a.check_selectable(sync_json):
                    return a
            return None

    nome = CharField(_("nome do ambiente"), max_length=255)
    url = PermissiveURLField(_("URL"), max_length=255)
    expressao_seletora = TextField(_("expressão seletora"), max_length=2550, null=True, blank=True)
    ordem = IntegerField(_("ordem"), default=0)
    local_suap_token = CharField(_("token local_suap"), max_length=255, null=True, blank=True)
    local_suap_active = BooleanField(_("local_suap ativo?"), default=True)
    tool_sga_token = CharField(_("token tool_sga"), max_length=255, null=True, blank=True)
    tool_sga_active = BooleanField(_("tool_sga ativo?"), default=True)

    objects = AmbienteManager()

    class Meta:
        verbose_name = _("ambiente")
        verbose_name_plural = _("ambientes")
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.nome}"

    @property
    def base_url(self):
        url = self.url or ""
        return url if url[-1:] != "/" else url[:-1]

    @property
    def valid_expressao_seletora(self):
        try:
            if self.expressao_seletora is None or self.expressao_seletora.strip() == "":
                return False
            Rule(self.expressao_seletora)
            return True
        except Exception:
            return False

    @property
    def can_send_to_tool_sga(self):
        return self.tool_sga_active and (self.tool_sga_token or "").strip() != ""

    @property
    def can_send_to_local_suap(self):
        return self.local_suap_active and (self.local_suap_token or "").strip() != ""

    @property
    def which_broker(self):
        if self.can_send_to_tool_sga:
            return "tool_sga"
        if self.can_send_to_local_suap:
            return "local_suap"
        return None

    @property
    def token(self):
        return getattr(self, f"{self.which_broker}_token", None)

    def check_selectable(self, sync_json: dict):
        if (not self.can_send_to_local_suap and not self.can_send_to_tool_sga) or not self.valid_expressao_seletora:
            return False
        try:
            return Rule(self.expressao_seletora).matches(sync_json)
        except Exception:
            return False


class Solicitacao(Model):
    class Status(Choices):
        NAO_DEFINIDO = Choices.Value(_("Não Definido"), value=None)
        SUCESSO = Choices.Value(_("Sucesso"), value="S")
        FALHA = Choices.Value(_("Falha"), value="F")
        PROCESSANDO = Choices.Value(_("Processando"), value="P")

    class Operacao(Choices):
        SYNC_UP_DIARIO = Choices.Value(
            _("Sync UP: Diário"),
            value="SUDiario",
            schema=json.loads((STATIC_DIR / "SUDiario.schema.json").read_text(encoding="utf-8")),
        )
        SYNC_DOWN_NOTAS = Choices.Value(
            _("Sync DOWN: Notas"),
            value="SDNotas",
            schema=json.loads((STATIC_DIR / "SDNotas.schema.json").read_text(encoding="utf-8")),
        )

    ambiente = ForeignKey(Ambiente, verbose_name=_("ambiente"), on_delete=PROTECT, null=True, blank=False)
    timestamp = DateTimeField(_("quando ocorreu"), auto_now_add=True, db_index=True)
    campus_sigla = CharField(_("campus"), max_length=256, null=True, blank=True)
    diario_codigo = CharField(_("código do diário"), max_length=256, null=True, blank=True)
    diario_id = CharField(_("ID do diário"), max_length=256, null=True, blank=True)
    operacao = CharField(
        _("operação"),
        max_length=256,
        choices=Operacao.choices,
        null=False,
        blank=False,
        default=Operacao.SYNC_UP_DIARIO,
    )
    tipo = CharField(_("tipo de diário"), max_length=256, null=True, blank=True, default=None)
    status = CharField(_("status"), max_length=256, choices=Status.choices, null=True, blank=False)
    status_code = CharField(_("status code"), max_length=256, null=True, blank=True)
    recebido = JSONField(_("JSON recebido"), null=True, blank=True)
    enviado = JSONField(_("JSON enviado"), null=True, blank=True)
    respondido = JSONField(_("JSON respondido"), null=True, blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_url: str | None = None

    class Meta:
        verbose_name = _("solicitação")
        verbose_name_plural = _("solicitações")

        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.id}={self.status}, {self.tipo}[{self.ambiente}]: {self.campus_sigla}-{self.diario_id}"

    @property
    def status_merged(self):
        return format_html("{}<br>{}", self.get_status_display(), self.status_code or "")

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.recebido:
            diario = self.recebido.get("diario", {})
            componente = diario.get("sigla", "")
            turma = self.recebido.get("turma", {}).get("codigo", "")
            self.ambiente = self.ambiente or Ambiente.objects.seleciona_ambiente(self.recebido)
            self.campus_sigla = self.recebido.get("campus", {}).get("sigla", None)
            self.diario_id = diario.get("id", "")
            self.diario_codigo = f"{turma}.{componente}#{self.diario_id}"
            self.tipo = self.recebido.get("diario", {}).get(
                "tipo", "regular" if self.operacao == Solicitacao.Operacao.SYNC_UP_DIARIO else None
            )
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
