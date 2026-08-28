from django.contrib.admin import StackedInline, register
from django.db.models import Model
from django.utils.translation import gettext as _
from import_export.resources import ModelResource

from base.admin import BaseModelAdmin, BasicModelAdmin
from cohort.models import Cohort, Enrolment, MoodleUser, Role

####
# Inlines
####


class EnrolmentInline(StackedInline):
    model: Model = Enrolment
    extra: int = 0
    autocomplete_fields = ["user", "cohort"]


####
# Admins
####


@register(MoodleUser)
class MoodleUserAdmin(BaseModelAdmin):
    class Resource(ModelResource):
        class Meta:
            model = MoodleUser
            import_id_fields = ("login",)
            export_order = ("fullname", "email", "login", "active")
            fields = export_order
            skip_unchanged = True

    list_display = ["fullname", "email", "login", "active"]
    list_filter = [
        "active",
    ] + BaseModelAdmin.list_filter
    search_fields = ["fullname", "email", "login"]
    resource_classes = [Resource]
    inlines = [EnrolmentInline]


@register(Role)
class RoleAdmin(BaseModelAdmin):
    class Resource(ModelResource):
        class Meta:
            model = Role
            import_id_fields = ("shortname",)
            export_order = ("name", "shortname", "active")
            fields = export_order
            skip_unchanged = True

    list_display = ["name", "shortname", "active"]
    list_filter = [
        "active",
    ] + BaseModelAdmin.list_filter
    search_fields = ["name", "shortname"]
    resource_classes = [Resource]


@register(Cohort)
class CohortAdmin(BasicModelAdmin):
    class Resource(ModelResource):
        def dehydrate_enrolments(self, obj):
            return ", ".join(e.user.login for e in obj.enrolments.select_related("user"))

        class Meta:
            model = Cohort
            import_id_fields = ("idnumber",)
            export_order = (
                "idnumber",
                "name",
                "rule_diario",
                "rule_coordenacao",
                "active",
                "enrolments",
            )
            fields = export_order
            skip_unchanged = True

    list_display = ["name", "idnumber", "rule_diario", "rule_coordenacao", "active"]
    search_fields = ["name", "idnumber"]
    list_filter = ["active"] + BasicModelAdmin.list_filter
    fieldsets = (
        (
            _("Informações Básicas"),
            {"fields": (("name", "idnumber", "active"), "role")},
        ),
        (
            _("Regras de Validação"),
            {
                "fields": (
                    "rule_diario",
                    "rule_coordenacao",
                ),
                "classes": ("wide",),
                "description": _("Configure a regra para validar quando este coorte deve ser sincronizado no diário"),
            },
        ),
        (_("Descrição"), {"fields": ("description",)}),
    )
    inlines = [EnrolmentInline]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Garante que o RuleField use o widget correto."""
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        return formfield
