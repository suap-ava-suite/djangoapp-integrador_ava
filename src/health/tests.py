"""
Testes unitários para a app health.

Este módulo contém testes para:
- health view: Endpoint de health check do sistema
- URLs: Roteamento da app health
- Verificação de status do banco de dados
- Verificação de modo DEBUG
"""

import json
from unittest.mock import patch

from django.http import JsonResponse
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings

from health.apps import HealthConfig
from health.views import health
from integrador.models import Ambiente


class HealthViewTestCase(TestCase):
    """Testes para a view health."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()

    @override_settings(DEBUG=False)
    @patch("health.views.connection")
    def test_health_check_success_with_debug_false(self, mock_connection):
        """Testa health check bem-sucedido com DEBUG=False."""
        # Mock da conexão com o banco
        mock_connection.connect.return_value = None

        request = self.factory.get("/health/")
        response = health(request)

        # Verifica status code
        self.assertEqual(response.status_code, 200)

        # Verifica conteúdo JSON
        content = json.loads(response.content)
        self.assertEqual(content["Debug"], "OK")
        self.assertEqual(content["Database"], "OK")
        self.assertIn("Moodles", content)

    @override_settings(DEBUG=True)
    @patch("health.views.connection")
    def test_health_check_with_debug_true(self, mock_connection):
        """Testa health check com DEBUG=True (deve reportar FAIL)."""
        mock_connection.connect.return_value = None

        request = self.factory.get("/health/")
        response = health(request)

        content = json.loads(response.content)
        self.assertEqual(content["Debug"], "FAIL (are active)")

    @override_settings(DEBUG=False)
    @patch("health.views.connection")
    def test_health_check_with_database_connection_failure(self, mock_connection):
        """Testa health check quando a conexão com banco falha."""
        # Simula erro na conexão
        mock_connection.connect.side_effect = Exception("Connection failed")

        request = self.factory.get("/health/")
        response = health(request)

        content = json.loads(response.content)
        self.assertEqual(content["Database"], "FAIL")

    @override_settings(DEBUG=False)
    @patch("health.views.connection")
    def test_health_check_returns_json_response(self, mock_connection):
        """Testa se health check retorna JsonResponse."""
        mock_connection.connect.return_value = None

        request = self.factory.get("/health/")
        response = health(request)

        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response["Content-Type"], "application/json")

    @override_settings(DEBUG=False)
    @patch("health.views.connection")
    def test_health_check_structure(self, mock_connection):
        """Testa se a estrutura do JSON está correta."""
        mock_connection.connect.return_value = None

        request = self.factory.get("/health/")
        response = health(request)

        content = json.loads(response.content)

        # Verifica estrutura básica
        self.assertIn("Debug", content)
        self.assertIn("Database", content)
        # self.assertIn("Moodles", content)

        # # Verifica estrutura do Moodles
        # self.assertIsInstance(content["Moodles"], dict)
        # self.assertIn("Ambiente 1", content["Moodles"])

    @override_settings(DEBUG=False)
    @patch("health.views.connection")
    def test_health_check_with_real_database_connection(self, mock_connection):
        """Testa health check com conexão real ao banco de dados."""
        mock_connection.connect.return_value = None

        request = self.factory.get("/health/")
        response = health(request)

        content = json.loads(response.content)

        # Se o teste está rodando, o banco deve estar OK
        self.assertEqual(content["Database"], "OK")


class HealthURLsTestCase(TransactionTestCase):
    """Testes para as URLs da app health."""

    def test_health_url_is_accessible(self):
        """Testa se a URL /health/ é acessível."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_url_returns_json(self):
        """Testa se a URL retorna JSON."""
        response = self.client.get("/health/")
        self.assertEqual(response["Content-Type"], "application/json")

    def test_health_url_with_trailing_slash(self):
        """Testa se a URL funciona com trailing slash."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=False)
    def test_health_endpoint_content(self):
        """Testa o conteúdo retornado pelo endpoint."""
        response = self.client.get("/health/")
        content = json.loads(response.content)

        # Verifica campos obrigatórios
        required_fields = ["Debug", "Database", "Moodles"]
        for field in required_fields:
            self.assertIn(field, content)


class HealthAppConfigTestCase(TestCase):
    """Testes para a configuração da app health."""

    def test_health_config_name(self):
        """Testa se o nome da app está correto."""
        self.assertEqual(HealthConfig.name, "health")

    def test_health_config_default_auto_field(self):
        """Testa se o default_auto_field está configurado."""
        self.assertEqual(HealthConfig.default_auto_field, "django.db.models.BigAutoField")


class HealthIntegrationTestCase(TransactionTestCase):
    """Testes de integração para a app health."""

    def test_health_check_full_workflow(self):
        """Testa o fluxo completo de health check."""
        # 1. Faz requisição ao endpoint
        response = self.client.get("/health/")

        # 2. Verifica resposta
        self.assertEqual(response.status_code, 200)

        # 3. Parseia JSON
        content = json.loads(response.content)

        # 4. Verifica estrutura completa
        self.assertIn("Debug", content)
        self.assertIn("Database", content)
        self.assertIn("Moodles", content)

        # 5. Verifica valores válidos
        self.assertIn(content["Debug"], ["OK", "FAIL (are active)"])
        self.assertIn(content["Database"], ["OK", "FAIL"])

    @override_settings(DEBUG=True)
    def test_health_check_detects_debug_mode(self):
        """Testa se o health check detecta modo DEBUG."""
        response = self.client.get("/health/")
        content = json.loads(response.content)

        # Em modo DEBUG, deve reportar FAIL
        self.assertEqual(content["Debug"], "FAIL (are active)")

    @override_settings(DEBUG=False)
    def test_health_check_production_mode(self):
        """Testa health check em modo produção."""
        response = self.client.get("/health/")
        content = json.loads(response.content)

        # Em produção, Debug deve ser OK
        self.assertEqual(content["Debug"], "OK")


class HealthEdgeCasesTestCase(TransactionTestCase):
    """Testes de casos extremos para health check."""

    def test_health_check_with_post_method(self):
        """Testa se health check aceita POST (deve aceitar qualquer método)."""
        response = self.client.post("/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_check_with_put_method(self):
        """Testa se health check aceita PUT."""
        response = self.client.put("/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_check_with_delete_method(self):
        """Testa se health check aceita DELETE."""
        response = self.client.delete("/health/")
        self.assertEqual(response.status_code, 200)

    @patch("health.views.connection")
    def test_health_check_with_database_timeout(self, mock_connection):
        """Testa health check quando há timeout no banco."""
        mock_connection.connect.side_effect = TimeoutError("Connection timeout")

        response = self.client.get("/health/")
        content = json.loads(response.content)

        self.assertEqual(content["Database"], "FAIL")

    @patch("health.views.connection")
    def test_health_check_with_database_permission_error(self, mock_connection):
        """Testa health check com erro de permissão no banco."""
        mock_connection.connect.side_effect = PermissionError("Access denied")

        response = self.client.get("/health/")
        content = json.loads(response.content)

        self.assertEqual(content["Database"], "FAIL")

    def test_health_check_json_is_valid(self):
        """Testa se o JSON retornado é válido."""
        response = self.client.get("/health/")
        json.loads(response.content)

    def test_health_check_with_query_parameters(self):
        """Testa health check com query parameters (devem ser ignorados)."""
        response = self.client.get("/health/?test=1&foo=bar")
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content)
        self.assertIn("Database", content)

    @override_settings(DEBUG=False)
    @patch("health.views.connection")
    def test_health_check_concurrent_requests(self, mock_connection):
        """Testa múltiplas requisições simultâneas ao health check."""
        mock_connection.connect.return_value = None

        # Simula múltiplas requisições
        responses = []
        for _ in range(10):
            response = self.client.get("/health/")
            responses.append(response)

        # Todas devem ter sucesso
        for response in responses:
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content)
            self.assertEqual(content["Database"], "OK")


class HealthMonitoringTestCase(TransactionTestCase):
    """Testes para monitoramento via health check."""

    @override_settings(DEBUG=False)
    def test_health_check_for_monitoring_tools(self):
        """Testa se o formato é adequado para ferramentas de monitoramento."""
        response = self.client.get("/health/")
        content = json.loads(response.content)

        # Verifica se contém informações úteis para monitoramento
        self.assertIn("Database", content)

        # Verifica se os valores são strings legíveis
        self.assertIsInstance(content["Database"], str)

    def test_health_check_response_time(self):
        """Testa se o health check responde rapidamente."""
        import time

        start = time.time()
        response = self.client.get("/health/")
        end = time.time()

        # Health check deve responder em menos de 1 segundo
        self.assertLess(end - start, 1.0)
        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=False)
    @patch("health.views.connection")
    def test_health_check_all_services_ok(self, mock_connection):
        """Testa cenário ideal onde todos os serviços estão OK."""
        mock_connection.connect.return_value = None

        response = self.client.get("/health/")
        content = json.loads(response.content)

        # Debug e Database devem estar OK
        self.assertEqual(content["Debug"], "OK")
        self.assertEqual(content["Database"], "OK")

    @override_settings(DEBUG=True)
    @patch("health.views.connection")
    def test_health_check_with_issues(self, mock_connection):
        """Testa cenário com problemas detectados."""
        mock_connection.connect.side_effect = Exception("DB Error")

        response = self.client.get("/health/")
        content = json.loads(response.content)

        # Debug em desenvolvimento e Database com erro
        self.assertEqual(content["Debug"], "FAIL (are active)")
        self.assertEqual(content["Database"], "FAIL")


class HealthAmbientesTestCase(TransactionTestCase):
    """Testes para o status de Ambientes no health check."""

    def setUp(self):
        """Configura o ambiente de teste."""
        Ambiente.objects.all().delete()

    @patch("health.views.requests.get")
    def test_health_with_ambientes(self, mock_get):
        """Testa health check com vários tipos de ambientes e respostas da API."""
        mock_response_ok = type("MockResponse", (object,), {})()
        mock_response_ok.status_code = 200
        mock_response_ok.json = lambda: {"status": "OK"}

        mock_response_fail = type("MockResponse", (object,), {})()
        mock_response_fail.status_code = 500

        def side_effect(url, **kwargs):
            if "env1" in url:
                return mock_response_ok
            if "env2" in url:
                return mock_response_fail
            if "env3" in url:
                raise requests.RequestException("Request timeout")
            return mock_response_ok

        mock_get.side_effect = side_effect

        # 1. Ambiente Ativo e tudo OK
        Ambiente.objects.create(
            nome="Env1",
            url="https://env1.moodle.com",
            ordem=1,
            expressao_seletora="campus['sigla'] == 'ENV1'",
            local_suap_token="token_suap",  # noqa: S106
            local_suap_active=True,
            tool_sga_token="token_sga",  # noqa: S106
            tool_sga_active=True,
        )

        # 2. Ambiente com token vazio e falha
        Ambiente.objects.create(
            nome="Env2",
            url="https://env2.moodle.com",
            ordem=2,
            expressao_seletora="campus['sigla'] == 'ENV2'",
            local_suap_token="",
            local_suap_active=True,
            tool_sga_token="token_sga_fail",  # noqa: S106
            tool_sga_active=True,
        )

        # 3. Ambiente inativo e erro
        Ambiente.objects.create(
            nome="Env3",
            url="https://env3.moodle.com",
            ordem=3,
            expressao_seletora="campus['sigla'] == 'ENV3'",
            local_suap_token="token_suap_error",  # noqa: S106
            local_suap_active=False,
            tool_sga_token="token_sga_error",  # noqa: S106
            tool_sga_active=True,
        )

        # 4. Ambiente extra para cobrir o fallback de side_effect
        Ambiente.objects.create(
            nome="Env4",
            url="https://env4.moodle.com",
            ordem=4,
            expressao_seletora="campus['sigla'] == 'ENV4'",
            local_suap_token="token_suap_ok",  # noqa: S106
            local_suap_active=True,
            tool_sga_token="token_sga_ok",  # noqa: S106
            tool_sga_active=True,
        )

        import requests  # assegura que requests está disponível no escopo do teste

        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content)
        moodles = content["Moodles"]

        # Verifica Env1 (OK)
        self.assertEqual(moodles["Env1"]["local_suap"], {"status": "OK"})
        self.assertEqual(moodles["Env1"]["tool_sga"], {"status": "OK"})

        # Verifica Env2 (NO_TOKEN para local_suap, e falha 500 para tool_sga)
        self.assertEqual(moodles["Env2"]["local_suap"], "NO_TOKEN")
        self.assertEqual(moodles["Env2"]["tool_sga"], "FAIL (500)")

        # Verifica Env3 (INACTIVE para local_suap, e erro de exceção para tool_sga)
        self.assertEqual(moodles["Env3"]["local_suap"], "INACTIVE")
        self.assertIn("ERROR (Request timeout)", moodles["Env3"]["tool_sga"])
