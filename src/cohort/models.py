from django.db.models import (
    PROTECT,
    BooleanField,
    CharField,
    ForeignKey,
    Model,
    TextField,
)
from django.utils.translation import gettext_lazy as _
from django_rule_engine.fields import RuleField
from simple_history.models import HistoricalRecords

from base.models import ActiveMixin

from .examples import JSON_DE_EXEMPLO


class MoodleUser(ActiveMixin, Model):
    fullname = CharField(_("nome completo do usuário"), max_length=2560)
    email = CharField(_("email do usuário"), max_length=2560)
    login = CharField(_("login do usuário"), max_length=2560, unique=True)
    active = BooleanField(
        _("sincronizar com o Moodle"),
        help_text=_(
            "Indica se a sincronização do usuário com o Moodle está ativa. Inativar aqui não remove o usuário do "
            "Moodle nem o inativa no Moodle, apenas indica que ele não deve ser sincronizado."
        ),
    )

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")
        ordering = ["fullname"]

    def __str__(self):
        return f"{self.fullname} ({self.email}) {self.active_icon}"


class Role(ActiveMixin, Model):
    name = CharField(
        _("nome da role"),
        max_length=256,
        help_text=_(
            "Este atributo será cohort.name"
            " Ex.: <sup>ZL.CooCurso.15056</sup>, <sup>ZL.CooPolo.Caraubas(RN)</sup>, <sup>ZL.MedPedProg.UAB</sup>."
        ),
    )
    shortname = CharField(
        _("shortname da role"),
        max_length=256,
        help_text=_(
            "Este atributo deve ser conforme role.shortname."
            " Ex.: <sup>teachercoordenadorcurso</sup>, <sup>coordenadordepolo</sup>, <sup>coordenadordeprograma</sup>"
        ),
    )
    active = BooleanField(_("ativo?"), help_text=_("Indica se esta coorte deverá ser sincronizada"))

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.active_icon}"


class Cohort(ActiveMixin, Model):
    name = CharField(_("nome da coorte"), max_length=2560, unique=True)
    idnumber = CharField(_("idnumber"), max_length=2560, unique=True)
    active = BooleanField(_("visível"), default=True)
    role = ForeignKey(Role, verbose_name=_("role"), on_delete=PROTECT, related_name="cohort_roles")
    rule_diario = RuleField(
        _("regra de validação para diário"),
        blank=True,
        null=True,
        example_data=JSON_DE_EXEMPLO,
        help_text=_("Exemplos: <ul><li>curso.codigo == '132456'</li></ul>"),
    )
    rule_coordenacao = RuleField(
        _("regra de validação para sala de coordenação"),
        blank=True,
        null=True,
        example_data=JSON_DE_EXEMPLO,
    )
    description = TextField(_("Descrição"), null=True, blank=True)

    class Meta:
        verbose_name = _("coorte")
        verbose_name_plural = _("coortes")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Enrolment(Model):
    user = ForeignKey(
        MoodleUser,
        verbose_name=_("usuário"),
        on_delete=PROTECT,
        related_name="enrolments",
        null=True,
        blank=False,
    )
    cohort = ForeignKey(Cohort, verbose_name=_("coorte"), on_delete=PROTECT, related_name="enrolments")
    active = BooleanField(_("ativo?"), default=True)

    class Meta:
        verbose_name = _("vínculo")
        verbose_name_plural = _("vínculos")
        ordering = ["cohort", "user"]

    def __str__(self):
        return f"{self.user.login} ({self.user.fullname}) em {self.cohort}"
