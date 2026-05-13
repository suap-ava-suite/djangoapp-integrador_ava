"""
Testes unitários para a app base.

Este módulo contém testes para:
- ActiveMixin: Mixin que adiciona ícone de status ativo/inativo
- BasicModelAdmin: ModelAdmin customizado com view mode
- BaseModelAdmin: ModelAdmin com suporte a import/export
- BaseChangeList: ChangeList customizado com URL de visualização
"""

from unittest.mock import MagicMock, Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import models
from django.forms.widgets import Media
from django.test import RequestFactory, TestCase

from base.admin import BaseChangeList, BaseModelAdmin, BasicModelAdmin
from base.models import ActiveMixin

User = get_user_model()


class MockActiveMixinModel(ActiveMixin, models.Model):
    """Modelo mock para testar o ActiveMixin."""

    active = models.BooleanField(default=True)
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "base"


class ActiveMixinTestCase(TestCase):
    """Testes para o ActiveMixin."""

    def test_active_icon_when_active_is_true(self):
        """Testa se retorna ícone correto quando active=True."""
        obj = MockActiveMixinModel(active=True)
        self.assertEqual(obj.active_icon, "✅")

    def test_active_icon_when_active_is_false(self):
        """Testa se retorna ícone correto quando active=False."""
        obj = MockActiveMixinModel(active=False)
        self.assertEqual(obj.active_icon, "⛔")

    def test_active_icon_is_property(self):
        """Testa se active_icon é uma property."""
        # active_icon é um método decorado, não uma property pura
        obj = MockActiveMixinModel(active=True)
        self.assertTrue(hasattr(obj, "active_icon"))
        self.assertIsInstance(obj.active_icon, str)


class MockModel(models.Model):
    """Modelo mock para testar os admins."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "base"
        verbose_name = "Mock Model"
        verbose_name_plural = "Mock Models"

    def __str__(self):
        return self.name


class MockModelAdmin(BasicModelAdmin):
    """ModelAdmin mock para testes."""

    list_display = ["name", "is_active"]
    readonly_fields = ["created_at"]


class BaseChangeListTestCase(TestCase):
    """Testes para BaseChangeList."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = MockModelAdmin(MockModel, self.site)
        self.user = User.objects.create_superuser(
            username="admin",  # noqa: S106
            email="admin@test.com",
            password="password123",  # noqa: S106
        )

    def test_url_for_result_uses_view_url(self):
        """Testa se url_for_result usa a URL de visualização."""
        obj = MockModel(id=1, name="Test")
        obj.pk = 1

        request = self.factory.get("/")
        request.user = self.user

        # Mock do queryset para evitar query no banco de MockModel
        with patch.object(self.admin, "get_queryset") as mock_qs:
            mock_qs.return_value = MockModel.objects.none()

            changelist = BaseChangeList(
                request=request,
                model=MockModel,
                list_display=["name"],
                list_display_links=["name"],
                list_filter=[],
                date_hierarchy=None,
                search_fields=[],
                list_select_related=[],
                list_per_page=100,
                list_max_show_all=200,
                list_editable=[],
                model_admin=self.admin,
                sortable_by=None,
                search_help_text=None,
            )

        # Mock reverse para evitar erro de URL não encontrada
        with patch("base.admin.reverse") as mock_reverse:
            mock_reverse.return_value = "/admin/base/mockmodel/1/view/"

            changelist.url_for_result(obj)

            # Verifica que reverse foi chamado com os parâmetros corretos
            mock_reverse.assert_called_once()
            call_args = mock_reverse.call_args
            self.assertEqual(call_args[0][0], "admin:base_mockmodel_view")


class BasicModelAdminTestCase(TestCase):
    """Testes para BasicModelAdmin."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = MockModelAdmin(MockModel, self.site)
        self.user = User.objects.create_superuser(
            username="admin",  # noqa: S106
            email="admin@test.com",
            password="password123",  # noqa: S106
        )

    def test_get_changelist_returns_base_changelist(self):
        """Testa se get_changelist retorna BaseChangeList."""
        request = self.factory.get("/")
        request.user = self.user

        changelist_class = self.admin.get_changelist(request)
        self.assertEqual(changelist_class, BaseChangeList)

    def test_get_urls_includes_view_url(self):
        """Testa se get_urls adiciona a URL de visualização."""
        urls = self.admin.get_urls()

        # Verifica se existe uma URL com name terminando em '_view'
        view_url_exists = any(url.pattern.name and url.pattern.name.endswith("_view") for url in urls)
        self.assertTrue(view_url_exists)

    @patch("base.admin.redirect")
    def test_redirect_view_redirects_to_default_view(self, mock_redirect):
        """Testa se redirect_view redireciona para a view padrão."""
        request = self.factory.get("/admin/base/mockmodel/1/")
        request.user = self.user

        self.admin.redirect_view(request, "1")

        mock_redirect.assert_called_once_with(
            "admin:base_mockmodel_view",
            object_id="1",
        )

    @patch.object(MockModelAdmin, "has_view_or_change_permission")
    @patch.object(MockModelAdmin, "get_object")
    def test_preview_view_renders_readonly_form(self, mock_get_object, mock_has_perm):
        """Testa se preview_view renderiza o formulário em modo leitura."""
        obj = MockModel(id=1, name="Test Object")
        obj.pk = 1
        mock_get_object.return_value = obj
        mock_has_perm.return_value = True

        request = self.factory.get("/admin/base/mockmodel/1/")
        request.user = self.user

        with patch.object(self.admin, "render_change_form") as mock_render:
            mock_render.return_value = Mock()
            self.admin.preview_view(request, "1")

            # Verifica se render_change_form foi chamado
            self.assertTrue(mock_render.called)

            # Verifica os argumentos passados
            call_args = mock_render.call_args
            self.assertEqual(call_args[1]["change"], False)
            self.assertEqual(call_args[1]["obj"], obj)

    @patch.object(MockModelAdmin, "has_view_or_change_permission")
    @patch.object(MockModelAdmin, "get_object")
    def test_preview_view_requires_permission(self, mock_get_object, mock_has_perm):
        """Testa se preview_view requer permissão."""
        obj = MockModel(id=1, name="Test Object")
        mock_get_object.return_value = obj
        mock_has_perm.return_value = False

        request = self.factory.get("/admin/base/mockmodel/1/")
        request.user = self.user

        with self.assertRaises(PermissionDenied):
            self.admin.preview_view(request, "1")

    @patch.object(MockModelAdmin, "has_view_or_change_permission")
    @patch.object(MockModelAdmin, "get_object")
    def test_preview_view_sets_request_in_view_mode(self, mock_get_object, mock_has_perm):
        """Testa se preview_view define request.in_view_mode."""
        obj = MockModel(id=1, name="Test Object")
        mock_get_object.return_value = obj
        mock_has_perm.return_value = True

        request = self.factory.get("/admin/base/mockmodel/1/")
        request.user = self.user

        with patch.object(self.admin, "render_change_form") as mock_render:
            mock_render.return_value = Mock()
            self.admin.preview_view(request, "1")

            # Verifica se request.in_view_mode foi definido
            self.assertTrue(hasattr(request, "in_view_mode"))
            self.assertTrue(request.in_view_mode)

    def test_preview_view_denies_disallowed_to_field(self):
        """Testa se preview_view nega acesso quando to_field não é permitido."""
        request = self.factory.get("/admin/base/mockmodel/1/?_to_field=id")
        request.user = self.user

        with patch.object(self.admin, "to_field_allowed", return_value=False):
            with self.assertRaises(PermissionDenied):
                self.admin.preview_view(request, "1")

    @patch.object(MockModelAdmin, "has_view_or_change_permission")
    @patch.object(MockModelAdmin, "get_object")
    def test_preview_view_updates_inline_readonly_fields_and_media(self, mock_get_object, mock_has_perm):
        """Testa se preview_view atualiza media e readonly_fields dos inline formsets."""
        obj = MockModel(id=1, name="Test Object")
        mock_get_object.return_value = obj
        mock_has_perm.return_value = True

        request = self.factory.get("/admin/base/mockmodel/1/")
        request.user = self.user

        inline_formset = Mock()
        inline_formset.media = Media(js=["inline.js"])
        inline_formset.fieldsets = ((None, {"fields": ("name", "description")}),)

        with patch.object(self.admin, "get_inline_formsets", return_value=[inline_formset]):
            with patch.object(self.admin, "render_change_form") as mock_render:
                mock_render.return_value = Mock()
                self.admin.preview_view(request, "1")

                context = mock_render.call_args[0][1]
                self.assertIn("inline.js", context["media"]._js)
                self.assertEqual(inline_formset.readonly_fields, ["name", "description"])

    def test_get_inline_formsets_disables_edit_in_view_mode(self):
        """Testa se get_inline_formsets desabilita edição em modo visualização."""
        obj = MockModel(id=1, name="Test Object")
        request = self.factory.get("/")
        request.user = self.user
        request.in_view_mode = True

        # Mock dos formsets e inline_instances
        mock_formset = MagicMock()
        mock_formset.extra = 5
        mock_formset.max_num = 10

        mock_inline = MagicMock()
        mock_inline.get_fieldsets.return_value = []
        mock_inline.get_readonly_fields.return_value = []
        mock_inline.get_prepopulated_fields.return_value = {}
        mock_inline.has_view_permission.return_value = True

        formsets = [mock_formset]
        inline_instances = [mock_inline]

        result = self.admin.get_inline_formsets(request, formsets, inline_instances, obj)

        # Verifica se as permissões foram desabilitadas
        self.assertEqual(len(result), 1)
        inline_formset = result[0]
        self.assertFalse(inline_formset.has_add_permission)
        self.assertFalse(inline_formset.has_change_permission)
        self.assertFalse(inline_formset.has_delete_permission)

        # Verifica se formset.extra e max_num foram zerados
        self.assertEqual(mock_formset.extra, 0)
        self.assertEqual(mock_formset.max_num, 0)

    def test_get_inline_formsets_enables_edit_when_not_in_view_mode(self):
        """Testa se get_inline_formsets permite edição fora do modo visualização."""
        obj = MockModel(id=1, name="Test Object")
        request = self.factory.get("/")
        request.user = self.user
        # Sem definir in_view_mode (comportamento normal)

        # Mock dos formsets e inline_instances
        mock_formset = MagicMock()
        mock_formset.extra = 5
        mock_formset.max_num = 10

        mock_inline = MagicMock()
        mock_inline.get_fieldsets.return_value = []
        mock_inline.get_readonly_fields.return_value = []
        mock_inline.get_prepopulated_fields.return_value = {}
        mock_inline.has_view_permission.return_value = True
        mock_inline.has_add_permission.return_value = True
        mock_inline.has_change_permission.return_value = True
        mock_inline.has_delete_permission.return_value = True

        formsets = [mock_formset]
        inline_instances = [mock_inline]

        with patch.object(self.admin, "has_change_permission", return_value=True):
            result = self.admin.get_inline_formsets(request, formsets, inline_instances, obj)

        # Verifica se as permissões foram habilitadas
        self.assertEqual(len(result), 1)
        inline_formset = result[0]
        self.assertTrue(inline_formset.has_add_permission)
        self.assertTrue(inline_formset.has_change_permission)
        self.assertTrue(inline_formset.has_delete_permission)


class BaseModelAdminTestCase(TestCase):
    """Testes para BaseModelAdmin."""

    def test_base_model_admin_extends_basic_model_admin(self):
        """Testa se BaseModelAdmin herda de BasicModelAdmin."""
        self.assertTrue(issubclass(BaseModelAdmin, BasicModelAdmin))

    def test_base_model_admin_has_import_export_mixin(self):
        """Testa se BaseModelAdmin inclui ImportExportMixin."""
        from import_export.admin import ImportExportMixin

        self.assertTrue(issubclass(BaseModelAdmin, ImportExportMixin))

    def test_base_model_admin_has_export_action_mixin(self):
        """Testa se BaseModelAdmin inclui ExportActionMixin."""
        from import_export.admin import ExportActionMixin

        self.assertTrue(issubclass(BaseModelAdmin, ExportActionMixin))


class IntegrationTestCase(TestCase):
    """Testes de integração entre os componentes."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.user = User.objects.create_superuser(
            username="admin",  # noqa: S106
            email="admin@test.com",
            password="password123",  # noqa: S106
        )

    def test_basic_model_admin_full_workflow(self):
        """Testa o fluxo completo do BasicModelAdmin."""
        admin = MockModelAdmin(MockModel, self.site)

        # 1. Verifica se get_changelist retorna BaseChangeList
        request = self.factory.get("/")
        request.user = self.user
        changelist_class = admin.get_changelist(request)
        self.assertEqual(changelist_class, BaseChangeList)

        # 2. Verifica se URLs foram registradas
        urls = admin.get_urls()
        self.assertGreater(len(urls), 0)

        # 3. Verifica se há URL de visualização
        view_url_exists = any(url.pattern.name and url.pattern.name.endswith("_view") for url in urls)
        self.assertTrue(view_url_exists)

    def test_active_mixin_integration_with_admin(self):
        """Testa integração do ActiveMixin com o admin."""
        # Cria um modelo que usa ActiveMixin
        obj = MockActiveMixinModel(active=True, name="Test")

        # Verifica se o ícone está correto
        self.assertEqual(obj.active_icon, "✅")

        # Muda o status
        obj.active = False
        self.assertEqual(obj.active_icon, "⛔")


class EdgeCasesTestCase(TestCase):
    """Testes de casos extremos e edge cases."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = MockModelAdmin(MockModel, self.site)
        self.user = User.objects.create_superuser(
            username="admin",  # noqa: S106
            email="admin@test.com",
            password="password123",  # noqa: S106
        )

    @patch.object(MockModelAdmin, "get_object")
    def test_preview_view_with_none_object(self, mock_get_object):
        """Testa preview_view quando o objeto não existe."""
        mock_get_object.return_value = None

        request = self.factory.get("/admin/base/mockmodel/999/")
        request.user = self.user

        with patch.object(self.admin, "has_view_or_change_permission", return_value=True):
            with patch.object(self.admin, "render_change_form") as mock_render:
                mock_render.return_value = Mock()
                self.admin.preview_view(request, "999")

                # Verifica se foi chamado com obj=None
                call_args = mock_render.call_args
                self.assertIsNone(call_args[1]["obj"])

    def test_get_inline_formsets_with_empty_lists(self):
        """Testa get_inline_formsets com listas vazias."""
        request = self.factory.get("/")
        request.user = self.user

        result = self.admin.get_inline_formsets(request, [], [], None)
        self.assertEqual(result, [])

    def test_active_icon_with_non_boolean_active(self):
        """Testa active_icon quando active não é exatamente True/False."""
        # Testa com valores truthy
        obj = MockActiveMixinModel(active=1)
        self.assertEqual(obj.active_icon, "✅")

        # Testa com valores falsy
        obj.active = 0
        self.assertEqual(obj.active_icon, "⛔")

        obj.active = None
        self.assertEqual(obj.active_icon, "⛔")
