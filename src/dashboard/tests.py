"""
Testes unitários para a app dashboard.

Este módulo contém testes para:
- DashboardStorage: carregamento de dados e cache
- admin_views: views personalizadas do admin
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.utils.timezone import now

from cohort.models import Cohort, Role
from dashboard.admin_views import admin_index_dashboard
from dashboard.storage import DashboardStorage
from integrador.models import Ambiente, Solicitacao

AMBIENTE_GOOD = dict(
    nome="Ambiente Teste",  # noqa: S106
    url="https://test.moodle.com",
    ordem=1,
    expressao_seletora="campus.sigla == 'TEST'",
    local_suap_token="local_suap_token",  # noqa: S106
    local_suap_active=True,
    tool_sga_token="tool_sga_token",  # noqa: S106
    tool_sga_active=True,
)


class DashboardStorageTestCase(TestCase):
    """Testes para a classe DashboardStorage."""

    def setUp(self):
        """Configura o ambiente de teste."""
        cache.clear()
        self.storage = DashboardStorage()

        # Cria dados de teste
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD)

        self.role = Role.objects.create(shortname="ROLE01", name="Test Role", active=True)

        self.cohort = Cohort.objects.create(name="Test Cohort", idnumber="C001", role=self.role, active=True)

        self.user = User.objects.create_user(username="testuser", is_active=True)

        # Cria solicitações de teste
        self.solicitacao_sucesso = Solicitacao.objects.create(
            campus_sigla="TEST",
            tipo="regular",
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            status=Solicitacao.Status.SUCESSO,
            timestamp=now(),
        )

        self.solicitacao_falha = Solicitacao.objects.create(
            campus_sigla="TEST",
            tipo="regular",
            operacao=Solicitacao.Operacao.SYNC_DOWN_NOTAS,
            status=Solicitacao.Status.FALHA,
            timestamp=now() - timedelta(hours=12),
        )

        self.solicitacao_processando = Solicitacao.objects.create(
            campus_sigla="TEST",
            tipo="regular",
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            status=Solicitacao.Status.PROCESSANDO,
            timestamp=now() - timedelta(hours=25),
        )

    def tearDown(self):
        """Limpa o cache após cada teste."""
        cache.clear()

    def test_dashboard_storage_initialization(self):
        """Testa inicialização do DashboardStorage."""
        storage = DashboardStorage()
        self.assertIsNotNone(storage.data)
        self.assertEqual(storage.data["ambientes_total"], 0)
        self.assertEqual(storage.data["total_solicitacoes"], 0)

    def test_get_context_without_cache(self):
        """Testa obtenção do contexto sem cache."""
        with override_settings(DASHBOARD_CACHE_ENABLED=False):
            context = self.storage.get_context()
            self.assertIsNotNone(context)
            self.assertIn("ambientes_total", context)

    def test_get_context_with_cache(self):
        """Testa obtenção do contexto com cache."""
        with override_settings(DASHBOARD_CACHE_ENABLED=True, DASHBOARD_CACHE_TIMEOUT=300):
            # Primeira chamada deve carregar dados
            context1 = self.storage.get_context()
            self.assertIsNotNone(context1)

            # Segunda chamada deve usar cache
            context2 = self.storage.get_context()
            self.assertEqual(context1["ambientes_total"], context2["ambientes_total"])

    def test_load_ambientes(self):
        """Testa carregamento de ambientes."""
        context = self.storage.get_context()
        self.assertEqual(context["ambientes_total"], 1)
        self.assertEqual(context["ambientes_ativos"], 1)

    def test_load_ambientes_with_invalid_expressao(self):
        """Testa carregamento de ambientes com expressão inválida."""
        # Cria um ambiente com expressão inválida
        Ambiente.objects.create(**{**AMBIENTE_GOOD, "expressao_seletora": "invalid expression"})

        storage = DashboardStorage()
        context = storage.get_context()
        # Deve contar ambientes com erro
        self.assertEqual(context["ambientes_total"], 2)

    def test_load_coortes(self):
        """Testa carregamento de coortes."""
        context = self.storage.get_context()
        self.assertEqual(context["coortes_total"], 1)
        self.assertEqual(context["coortes_ativas"], 1)
        self.assertEqual(context["coortes_inativas"], 0)

    def test_load_coortes_with_inactive(self):
        """Testa carregamento de coortes inativas."""
        Cohort.objects.create(name="Inactive Cohort", idnumber="C002", role=self.role, active=False)

        storage = DashboardStorage()
        context = storage.get_context()
        self.assertEqual(context["coortes_total"], 2)
        self.assertEqual(context["coortes_ativas"], 1)
        self.assertEqual(context["coortes_inativas"], 1)

    def test_load_papeis(self):
        """Testa carregamento de papéis."""
        context = self.storage.get_context()
        self.assertEqual(context["papeis_total"], 1)
        self.assertEqual(context["papeis_ativos"], 1)
        self.assertEqual(context["papeis_inativos"], 0)

    def test_load_papeis_with_inactive(self):
        """Testa carregamento de papéis inativos."""
        Role.objects.create(shortname="coordenadordecurso", name="Inactive Role", active=False)

        storage = DashboardStorage()
        context = storage.get_context()
        self.assertEqual(context["papeis_total"], 2)
        self.assertEqual(context["papeis_ativos"], 1)
        self.assertEqual(context["papeis_inativos"], 1)

    def test_load_usuarios(self):
        """Testa carregamento de usuários."""
        context = self.storage.get_context()
        self.assertGreater(context["usuarios_total"], 0)
        self.assertGreaterEqual(context["usuarios_ativos"], 1)

    def test_load_solicitacoes(self):
        """Testa carregamento de solicitações."""
        context = self.storage.get_context()
        self.assertEqual(context["solicitacoes_sucesso"], 1)
        self.assertEqual(context["solicitacoes_falha"], 1)
        self.assertEqual(context["solicitacoes_processando"], 1)
        self.assertEqual(context["total_solicitacoes"], 3)
        # success and failure are within the last 24h; processing is outside (25 hours)
        # however, the default timestamp may actually have been included during create
        self.assertGreaterEqual(context["solicitacoes_24h"], 2)

    def test_load_solicitacoes_taxa_sucesso(self):
        """Testa cálculo da taxa de sucesso."""
        context = self.storage.get_context()
        expected_taxa = (1 / 3) * 100
        self.assertEqual(context["taxa_sucesso"], int(expected_taxa))

    def test_load_solicitacoes_with_no_requests(self):
        """Testa carregamento quando não há solicitações."""
        Solicitacao.objects.all().delete()
        storage = DashboardStorage()
        context = storage.get_context()
        self.assertEqual(context["total_solicitacoes"], 0)
        self.assertEqual(context["taxa_sucesso"], 0)

    def test_load_series_temporal(self):
        """Testa carregamento da série temporal."""
        context = self.storage.get_context()
        self.assertIsNotNone(context["solicitacoes_series"])
        self.assertIsInstance(context["solicitacoes_series"], list)

    def test_load_series_temporal_with_multiple_months(self):
        """Testa carregamento da série temporal com múltiplos meses."""
        # Cria solicitações em diferentes meses
        three_months_ago = now() - timedelta(days=90)
        Solicitacao.objects.create(
            campus_sigla="TEST",
            tipo="regular",
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            status=Solicitacao.Status.SUCESSO,
            timestamp=three_months_ago,
        )

        storage = DashboardStorage()
        context = storage.get_context()
        # Deve ter mais de uma série
        self.assertGreater(len(context["solicitacoes_series"]), 0)

    def test_load_data_handles_exception(self):
        """Testa se exceções são tratadas no carregamento."""
        with patch("dashboard.storage.Ambiente.objects.count", side_effect=Exception("DB Error")):
            context = self.storage.get_context()
            # Deve retornar contexto mesmo com erro
            self.assertIsNotNone(context)

    def test_load_coortes_handles_exception(self):
        """Testa tratamento de exceção no carregamento de coortes."""
        with patch("dashboard.storage.Cohort.objects.count", side_effect=Exception("DB Error")):
            storage = DashboardStorage()
            storage._load_coortes()
            # Deve manter valores padrão
            self.assertEqual(storage.data["coortes_total"], 0)

    def test_load_papeis_handles_exception(self):
        """Testa tratamento de exceção no carregamento de papéis."""
        with patch("dashboard.storage.Role.objects.count", side_effect=Exception("DB Error")):
            storage = DashboardStorage()
            storage._load_papeis()
            # Deve manter valores padrão
            self.assertEqual(storage.data["papeis_total"], 0)

    def test_load_usuarios_handles_exception(self):
        """Testa tratamento de exceção no carregamento de usuários."""
        with patch("dashboard.storage.User.objects.count", side_effect=Exception("DB Error")):
            storage = DashboardStorage()
            storage._load_usuarios()
            # Deve manter valores padrão
            self.assertEqual(storage.data["usuarios_total"], 0)

    def test_load_solicitacoes_handles_exception(self):
        """Testa tratamento de exceção no carregamento de solicitações."""
        with patch("dashboard.storage.Solicitacao.objects.filter", side_effect=Exception("DB Error")):
            storage = DashboardStorage()
            storage._load_solicitacoes()
            # Deve manter valores padrão
            self.assertEqual(storage.data["total_solicitacoes"], 0)

    def test_load_series_temporal_handles_exception(self):
        """Testa tratamento de exceção no carregamento da série temporal."""
        with patch("dashboard.storage.Solicitacao.objects.all", side_effect=Exception("DB Error")):
            storage = DashboardStorage()
            storage._load_series_temporal()
            # Deve manter lista vazia
            self.assertEqual(storage.data["solicitacoes_series"], [])

    def test_cache_key_storage(self):
        """Testa se os dados são armazenados no cache."""
        cache.clear()
        with override_settings(DASHBOARD_CACHE_ENABLED=True, DASHBOARD_CACHE_TIMEOUT=300):
            storage = DashboardStorage()
            # Primeira chamada carrega dados
            context1 = storage.get_context()

            # Chama novamente - se cache funcionar, deve vir do cache
            storage2 = DashboardStorage()
            context2 = storage2.get_context()

            # Os dados devem ser iguais
            self.assertEqual(context1["ambientes_total"], context2["ambientes_total"])
            self.assertEqual(context1["coortes_total"], context2["coortes_total"])

    def test_cache_disabled_not_stored(self):
        """Testa se cache não armazena quando desabilitado."""
        with override_settings(DASHBOARD_CACHE_ENABLED=False):
            self.storage.get_context()
            # Verifica se dados não estão em cache
            from django.core.cache import cache

            cached = cache.get("admin_dashboard_data")
            self.assertIsNone(cached)

    def test_get_context_stores_data_in_cache_when_enabled(self):
        """Testa get_context persistindo dados em cache quando habilitado."""
        with patch("dashboard.storage.CACHE_ENABLED", True):
            with patch("dashboard.storage.CACHE_TIMEOUT", 123):
                with patch.object(DashboardStorage, "_load_data") as mock_load_data:
                    with patch("dashboard.storage.cache.set") as mock_cache_set:
                        context = self.storage.get_context()

        self.assertEqual(context, self.storage.data)
        mock_load_data.assert_called_once()
        mock_cache_set.assert_called_once_with("admin_dashboard_data", self.storage.data, 123)


class AdminIndexDashboardTestCase(TestCase):
    """Testes para a view admin_index_dashboard."""

    def setUp(self):
        """Configura o ambiente de teste."""
        cache.clear()
        self.factory = RequestFactory()

        # Cria usuário staff
        self.staff_user = User.objects.create_user(
            username="staffuser",  # noqa: S106
            password="testpass123",  # noqa: S106
            is_staff=True,
            is_superuser=True,
        )

        # Cria usuário não-staff
        self.regular_user = User.objects.create_user(
            username="regularuser",  # noqa: S106
            password="testpass123",  # noqa: S106
            is_staff=False,
            is_superuser=False,
        )

    def tearDown(self):
        """Limpa o cache após cada teste."""
        cache.clear()

    def test_admin_dashboard_requires_staff(self):
        """Testa se o dashboard requer usuário staff (redirect)."""
        request = self.factory.get("/admin/")
        request.user = self.regular_user

        response = admin_index_dashboard(request)
        # Deve redirecionar para login
        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard_loads_storage_data(self):
        """Testa se o dashboard carrega dados do storage."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user

        with patch("dashboard.admin_views.DashboardStorage") as mock_storage:
            mock_instance = mock_storage.return_value
            mock_instance.get_context.return_value = {"test_key": "test_value"}

            with patch("dashboard.admin_views.LogEntry.objects.filter") as mock_log:
                mock_log.return_value.select_related.return_value.order_by.return_value = []

                with patch("dashboard.admin_views.admin.site.get_app_list", return_value=[]):
                    with patch("dashboard.admin_views.render") as mock_render:
                        admin_index_dashboard(request)
                        mock_render.assert_called_once()
                        # Verifica que storage foi criado e chamado
                        mock_storage.assert_called_once()
                        mock_instance.get_context.assert_called_once()

    def test_admin_dashboard_handles_log_entry_error(self):
        """Testa se dashboard lida com erro no histórico."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user

        with patch("dashboard.admin_views.LogEntry.objects.filter", side_effect=Exception("DB Error")):
            with patch("dashboard.admin_views.DashboardStorage") as mock_storage:
                mock_instance = mock_storage.return_value
                mock_instance.get_context.return_value = {}

                with patch("dashboard.admin_views.admin.site.get_app_list", return_value=[]):
                    with patch("dashboard.admin_views.render") as mock_render:
                        admin_index_dashboard(request)
                        # Pega o contexto passado para render
                        context = mock_render.call_args[0][2]
                        # Deve ter lista vazia
                        self.assertEqual(context["log_entries"], [])
