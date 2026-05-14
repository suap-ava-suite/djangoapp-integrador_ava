"""
Testes unitários para a app integrador.

Este módulo contém testes para:
- Models: Ambiente, Solicitacao
- Decorators: json_response, exception_as_json, check_is_post, check_is_get, valid_token, check_json, try_solicitacao,
detect_ambiente
- Views: sync_up_enrolments, sync_down_grades
- Utils: SyncError, http_get, http_post, http_get_json, http_post_json
- Middleware: DisableCSRFForAPIMiddleware
- Brokers: BaseBroker, Suap2LocalSuapBroker
- Management Commands: atualiza_solicitacoes
"""

import io
import json
import logging
import uuid
from http.client import HTTPException
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django import forms
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings

from cohort.models import Cohort, Enrolment, MoodleUser, Role
from integrador.apps import IntegradorConfig
from integrador.brokers.base import BaseBroker
from integrador.brokers.suap2local_suap import Suap2LocalSuapBroker
from integrador.decorators import (
    check_is_get,
    check_is_post,
    check_json,
    detect_ambiente,
    exception_as_json,
    json_response,
    try_solicitacao,
    valid_token,
)
from integrador.middleware import DisableCSRFForAPIMiddleware
from integrador.models import Ambiente, Solicitacao
from integrador.moodle_mock import LocalSuapHTTPMock, MockHTTPResponse, ToolSgaHTTPMock
from integrador.utils import SyncError, http_get, http_get_json, http_post, http_post_json
from integrador.views import sync_up_enrolments

# Configura logging para WARNING durante testes (suprime DEBUG e INFO)
logging.getLogger("integrador").setLevel(logging.WARNING)


TEST_TOKEN = ToolSgaHTTPMock.TEST_TOKEN
TEST_TOKEN_NOT_OK = f"test-{uuid.uuid4().hex}"


AMBIENTE_GOOD_SGA = dict(
    nome="Ambiente Teste",
    url="https://test.moodle.com",
    ordem=1,
    expressao_seletora="campus.sigla == 'TEST'",
    tool_sga_token=TEST_TOKEN,
    tool_sga_active=True,
    local_suap_token=TEST_TOKEN,
    local_suap_active=True,
)

AMBIENTE_GOOD_SUAP = dict(
    nome="Ambiente Teste",
    url="https://test.moodle.com",
    ordem=1,
    expressao_seletora="campus.sigla == 'TEST'",
    tool_sga_token=None,
    tool_sga_active=False,
    local_suap_token=TEST_TOKEN,
    local_suap_active=True,
)


class IntegradorConfigTestCase(TestCase):
    """Testes para a configuração da app integrador."""

    def test_app_config_name(self):
        """Testa se o nome da app está correto."""
        self.assertEqual(IntegradorConfig.name, "integrador")

    def test_app_config_icon(self):
        """Testa se o ícone está definido."""
        self.assertEqual(IntegradorConfig.icon, "fa fa-home")

    def test_app_config_default_auto_field(self):
        """Testa se default_auto_field está configurado."""
        self.assertEqual(IntegradorConfig.default_auto_field, "django.db.models.BigAutoField")


class SyncErrorTestCase(TestCase):
    """Testes para a classe SyncError."""

    def test_sync_error_creation(self):
        """Testa criação de SyncError."""
        error = SyncError("Test error", 500)

        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.code, 500)

    def test_sync_error_with_retorno(self):
        """Testa SyncError com retorno."""
        retorno = {"detail": "error detail"}
        error = SyncError("Test error", 400, retorno=retorno)

        self.assertEqual(error.retorno, retorno)


class UtilsFunctionsTestCase(TestCase):
    """Testes para funções utilitárias."""

    @patch("integrador.utils.sc4net.get")
    def test_http_get_success(self, mock_get):
        """Testa http_get com sucesso."""
        mock_get.return_value = "Test content"

        result = http_get("http://test.com")

        self.assertEqual(result, "Test content")

    @patch("integrador.utils.sc4net.get")
    def test_http_get_failure(self, mock_get):
        """Testa http_get com falha."""
        exc = HTTPException("404 - Not Found")
        exc.status = 404
        exc.reason = "Not Found"
        exc.headers = {}
        exc.url = "http://test.com"
        mock_get.side_effect = exc

        with self.assertRaises(HTTPException):
            http_get("http://test.com")

    @patch("integrador.utils.sc4net.post")
    def test_http_post_success(self, mock_post):
        """Testa http_post com sucesso."""
        mock_post.return_value = "Posted"

        result = http_post("http://test.com", {"data": "value"})

        self.assertEqual(result, "Posted")

    @patch("integrador.utils.sc4net.post")
    def test_http_post_failure(self, mock_post):
        """Testa http_post com falha."""
        exc = HTTPException("500 - Server Error")
        exc.status = 500
        exc.reason = "Server Error"
        exc.headers = {}
        exc.url = "http://test.com"
        mock_post.side_effect = exc

        with self.assertRaises(HTTPException):
            http_post("http://test.com", {"data": "value"})

    @patch("integrador.utils.http_get")
    def test_http_get_json_success(self, mock_http_get):
        """Testa http_get_json com sucesso."""
        mock_http_get.return_value = '{"key": "value"}'

        result = http_get_json("http://test.com")

        self.assertEqual(result, {"key": "value"})

    @patch("integrador.utils.http_post")
    def test_http_post_json_success(self, mock_http_post):
        """Testa http_post_json com sucesso."""
        mock_http_post.return_value = '{"result": "success"}'

        result = http_post_json("http://test.com", {"data": "value"})

        self.assertEqual(result, {"result": "success"})


class ToolSgaHTTPMockTestCase(TestCase):
    """
    Testes para ToolSgaHTTPMock.

    Cobre o mock do plugin `tool_sga`, usado pelos brokers
    `Suap2ToolSgaBroker` e `Sga2ToolSgaBroker`.

    Os brokers ainda não estão implementados, portanto os testes cobrem
    apenas o comportamento de stub (respostas 4xx/501).
    """

    PLUGIN_PATH = ToolSgaHTTPMock.PLUGIN_PATH
    BASE_URL = f"https://test.moodle.com{PLUGIN_PATH}"
    AUTH_HEADERS = {"Authentication": f"Token {TEST_TOKEN}"}

    def setUp(self):
        self.mock = ToolSgaHTTPMock()

    def test_sem_authentication_retorna_400(self):
        """Chamada sem cabeçalho Authentication deve retornar 400."""
        response = self.mock.get(self.BASE_URL)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 400)

    def test_authentication_incorreta_retorna_401(self):
        """Cabeçalho Authentication errado deve retornar 401."""
        response = self.mock.get(self.BASE_URL, headers={"Authentication": f"Token {TEST_TOKEN_NOT_OK}"})
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 401)

    def test_endpoint_errado_retorna_404(self):
        """URL com path incorreto deve retornar 404."""
        response = self.mock.get("https://test.moodle.com/outro/path", headers=self.AUTH_HEADERS)
        self.assertEqual(response.status_code, 404)

    def test_qualquer_servico_retorna_501(self):
        """Qualquer serviço autenticado deve retornar 501 enquanto o broker não for implementado."""
        response = self.mock.post(self.BASE_URL, jsonbody={}, headers=self.AUTH_HEADERS)
        self.assertEqual(response.status_code, 501)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 501)


class LocalSuapHTTPMockTestCase(TestCase):
    """
    Testes para LocalSuapHTTPMock e MockHTTPResponse.

    Cobre o mock do plugin `local_suap`, usado pelo broker `Suap2LocalSuapBroker`.
    """

    BASE_URL = "https://test.moodle.com/local/suap/api/index.php"

    def setUp(self):
        self.mock = LocalSuapHTTPMock()

    # --- MockHTTPResponse ---

    def test_mock_response_ok(self):
        """Resposta JSON padrão deve ser ok."""
        response = MockHTTPResponse({"status": "ok"})
        self.assertTrue(response.ok)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"status": "ok"})

    def test_mock_response_html_error_nao_ok(self):
        """html_error com status 5xx deve ter ok=False e Content-Type HTML."""
        response = MockHTTPResponse.html_error(500)
        self.assertFalse(response.ok)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"<html>", response.content)

    def test_mock_response_html_error_2xx_ok_true(self):
        """Moodle pode retornar HTML com status 200 (erro PHP com output antes dos headers)."""
        response = MockHTTPResponse.html_error(200, message="Fatal error: Uncaught Error")
        self.assertTrue(response.ok)
        self.assertIn(b"Fatal error", response.content)

    def test_mock_response_html_nao_e_json_valido(self):
        """Conteúdo HTML não pode ser parseado como JSON."""
        response = MockHTTPResponse.html_error(500)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(response.content)

    # --- LocalSuapHTTPMock ---

    def test_endpoint_desconhecido_retorna_404(self):
        response = self.mock.get("https://test.moodle.com/outro/endpoint")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.ok)

    AUTH_HEADERS = {"Authentication": f"Token {TEST_TOKEN}"}

    SYNC_UP_PAYLOAD_MINIMO = {
        "campus": {"id": 1, "sigla": "ZL", "descricao": "Campus ZL"},
        "curso": {"id": 1, "codigo": "15806", "nome": "Sistemas Operacionais Abertos"},
        "turma": {"id": 2, "codigo": "20261.6.15806.1E"},
        "componente": {"id": 1, "sigla": "TEC.1023", "descricao": "Bancos de Dados"},
        "diario": {"id": 2, "sigla": "TEC.1023", "situacao": "Aberto"},
    }

    def test_sync_up_enrolments_post_sucesso(self):
        url = f"{self.BASE_URL}?sync_up_enrolments"
        payload = {**self.SYNC_UP_PAYLOAD_MINIMO, "coortes": [{"id": 1}, {"id": 2}]}
        response = self.mock.post(url, jsonbody=payload, headers=self.AUTH_HEADERS)
        self.assertTrue(response.ok)
        data = json.loads(response.content)
        self.assertIn("url", data)
        self.assertIn("url_sala_coordenacao", data)
        self.assertEqual(data["roles_not_found"], [])
        self.assertNotIn("mock", data)
        self.assertNotIn("cohort_count", data)

    def test_sync_up_enrolments_payload_invalido_retorna_422(self):
        url = f"{self.BASE_URL}?sync_up_enrolments"
        response = self.mock.post(url, jsonbody={"coortes": []}, headers=self.AUTH_HEADERS)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.ok)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 422)
        self.assertIn("campus", data["error"]["message"])

    def test_sync_down_grades_get_sucesso(self):
        url = f"{self.BASE_URL}?sync_down_grades&diario_id=42"
        response = self.mock.get(url, headers=self.AUTH_HEADERS)
        self.assertTrue(response.ok)
        data = json.loads(response.content)
        self.assertEqual(data[0]["diario_id"], "42")
        self.assertTrue(data[0]["mock"])

    def test_servico_desconhecido_retorna_404(self):
        url = f"{self.BASE_URL}?servico_inexistente"
        response = self.mock.get(url, headers=self.AUTH_HEADERS)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.ok)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 404)
        self.assertEqual(data["error"]["message"], "Serviço não existe")

    def test_servico_nao_implementado_retorna_501(self):
        url = f"{self.BASE_URL}?get_diarios"
        response = self.mock.get(url, headers=self.AUTH_HEADERS)
        self.assertEqual(response.status_code, 501)
        self.assertFalse(response.ok)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 501)
        self.assertEqual(data["error"]["message"], "Não implementado")

    def test_sem_authentication_retorna_400(self):
        url = f"{self.BASE_URL}?sync_up_enrolments"
        response = self.mock.post(url, jsonbody={})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.ok)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 400)
        self.assertIn("Authentication not informed", data["error"]["message"])

    def test_authentication_incorreta_retorna_401(self):
        url = f"{self.BASE_URL}?sync_up_enrolments"
        response = self.mock.post(url, jsonbody={}, headers={"Authentication": f"Token {TEST_TOKEN_NOT_OK}"})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.ok)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], 401)
        self.assertEqual(data["error"]["message"], "Unauthorized")

    def test_html_error_com_status_200_causa_json_decode_error_em_get(self):
        """Moodle retorna HTML com status 200 (erro PHP): http_get_json falha ao parsear."""
        html_str = "<!DOCTYPE html><html><body><h1>Fatal error</h1></body></html>"
        with patch("integrador.utils.http_get", return_value=html_str):
            with self.assertRaises(json.JSONDecodeError):
                http_get_json(f"{self.BASE_URL}?sync_down_grades&diario_id=1")

    def test_html_error_com_status_200_causa_json_decode_error_em_post(self):
        """Moodle retorna HTML com status 200 (erro PHP): http_post_json falha ao parsear."""
        html_str = "<!DOCTYPE html><html><body><h1>Fatal error</h1></body></html>"
        with patch("integrador.utils.http_post", return_value=html_str):
            with self.assertRaises(json.JSONDecodeError):
                http_post_json(f"{self.BASE_URL}?sync_up_enrolments", {})


class MiddlewareTestCase(TestCase):
    """Testes para middleware."""

    def setUp(self):
        """Configura o ambiente de teste."""
        # Suprime logs durante testes
        logging.getLogger("integrador").setLevel(logging.WARNING)

        self.factory = RequestFactory()
        self.middleware = DisableCSRFForAPIMiddleware(lambda x: None)

    def test_csrf_middleware_exempts_api_urls(self):
        """Testa que middleware isenta URLs da API de CSRF."""
        request = self.factory.post("/api/enviar_diarios/")

        self.middleware.process_request(request)

        self.assertTrue(getattr(request, "_dont_enforce_csrf_checks", False))

    def test_csrf_middleware_exempts_baixar_notas(self):
        """Testa que middleware isenta baixar_notas de CSRF."""
        request = self.factory.post("/api/baixar_notas/")

        self.middleware.process_request(request)

        self.assertTrue(getattr(request, "_dont_enforce_csrf_checks", False))

    def test_csrf_middleware_does_not_exempt_other_urls(self):
        """Testa que middleware não isenta outras URLs."""
        request = self.factory.post("/admin/")

        self.middleware.process_request(request)

        self.assertFalse(getattr(request, "_dont_enforce_csrf_checks", False))


class CSRFErrorViewTestCase(TestCase):
    """Testes para a view customizada de erro CSRF."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        # Importa a view de erro CSRF
        from integrador.views_errors import csrf_failure

        self.csrf_failure_view = csrf_failure

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_sends_to_sentry(self, mock_sentry):
        """Testa que erro CSRF envia informação para o Sentry."""
        request = self.factory.post("/api/test/")
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_REFERER"] = "https://external.com"
        request.user = Mock()
        request.user.is_authenticated = False

        self.csrf_failure_view(request, reason="CSRF cookie not set")

        # Verifica que Sentry foi chamado
        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        self.assertIn("CSRF verification failed", call_args[0][0])
        self.assertEqual(call_args[1]["level"], "warning")

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_returns_json_for_api(self, mock_sentry):
        """Testa que erro CSRF retorna JSON para requisições de API."""
        request = self.factory.post("/api/test/")
        request.META["HTTP_ACCEPT"] = "application/json"
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.csrf_failure_view(request, reason=f"Token {TEST_TOKEN_NOT_OK}")

        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertIn("error", data)
        self.assertIn("reason", data)
        self.assertEqual(data["reason"], f"Token {TEST_TOKEN_NOT_OK}")

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_returns_html_for_browser(self, mock_sentry):
        """Testa que erro CSRF retorna HTML para requisições de navegador."""
        request = self.factory.post("/admin/login/")
        request.META["HTTP_ACCEPT"] = "text/html"
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.csrf_failure_view(request, reason="Referer check failed")

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"403", response.content)

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_includes_user_info_when_authenticated(self, mock_sentry):
        """Testa que erro CSRF inclui informações do usuário autenticado."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password=f"test-{uuid.uuid4().hex}",
        )

        request = self.factory.post("/api/test/")
        request.user = user
        request.META["HTTP_ACCEPT"] = "application/json"

        self.csrf_failure_view(request, reason="Token expired")

        # Verifica que o contexto do Sentry foi configurado corretamente
        mock_sentry.push_scope.assert_called()

    @patch("integrador.views_errors.sentry_sdk")
    @patch("integrador.views_errors.logger")
    def test_csrf_failure_logs_warning(self, mock_logger, mock_sentry):
        """Testa que erro CSRF gera log de warning."""
        request = self.factory.post("/api/test/")
        request.user = Mock()
        request.user.is_authenticated = False

        self.csrf_failure_view(request, reason="Invalid token")

        # Verifica se o logger foi chamado
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        self.assertIn("CSRF verification failed", call_args[0][0])

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_captures_request_details(self, mock_sentry):
        """Testa que erro CSRF captura detalhes completos da requisição."""
        request = self.factory.post("/api/sensitive-endpoint/")
        request.META["HTTP_USER_AGENT"] = "MaliciousBot/1.0"
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        request.META["HTTP_REFERER"] = "https://malicious-site.com"
        request.META["CONTENT_TYPE"] = "application/json"
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.csrf_failure_view(request, reason="CSRF cookie not set")

        # Verifica que todos os detalhes foram capturados
        self.assertEqual(response.status_code, 403)
        mock_sentry.capture_message.assert_called_once()

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_with_empty_reason(self, mock_sentry):
        """Testa erro CSRF com razão vazia."""
        request = self.factory.post("/api/test/")
        request.META["HTTP_ACCEPT"] = "application/json"
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.csrf_failure_view(request, reason="")

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("reason", data)

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_returns_json_when_content_type_is_json(self, mock_sentry):
        """Testa que erro CSRF retorna JSON quando Content-Type é application/json."""
        request = self.factory.post("/admin/test/", content_type="application/json", data=json.dumps({"test": "data"}))
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.csrf_failure_view(request, reason="Token mismatch")

        # Mesmo sem /api/ no path, deve retornar JSON porque Content-Type é JSON
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(data["error"], "CSRF verification failed")
        self.assertEqual(data["reason"], "Token mismatch")

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_returns_json_when_accept_is_json(self, mock_sentry):
        """Testa que erro CSRF retorna JSON quando Accept é application/json."""
        request = self.factory.post("/admin/test/")
        request.META["HTTP_ACCEPT"] = "application/json; charset=utf-8"
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.csrf_failure_view(request, reason="Referer check failed")

        # Deve retornar JSON porque Accept contém application/json
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(data["error"], "CSRF verification failed")

    @patch("integrador.views_errors.sentry_sdk")
    def test_csrf_failure_returns_json_for_api_paths(self, mock_sentry):
        """Testa que erro CSRF retorna JSON para paths começando com /api/."""
        request = self.factory.post("/api/some/endpoint/")
        request.META["HTTP_ACCEPT"] = "text/html"  # Mesmo com Accept HTML
        request.user = Mock()
        request.user.is_authenticated = False

        response = self.csrf_failure_view(request, reason="CSRF token missing")

        # Deve retornar JSON porque path começa com /api/
        self.assertEqual(response.status_code, 403)
        self.assertIsInstance(response, JsonResponse)


class AmbienteModelTestCase(TestCase):
    """Testes para o modelo Ambiente."""

    SYNC_JSON_OK = {"campus": {"sigla": "TEST"}}
    SYNC_JSON_NOT_OK = {"campus": {"sigla": "ERROR"}}

    def test_create_ambiente(self):
        """Testa criação de ambiente."""
        ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)
        self.assertIsNotNone(ambiente.pk)

    def test_manager_seleciona_ambiente_valid(self):
        """Testa __str__."""
        Ambiente.objects.create(**AMBIENTE_GOOD_SGA)
        ambiente = Ambiente.objects.seleciona_ambiente(AmbienteModelTestCase.SYNC_JSON_OK)
        self.assertIsNotNone(ambiente)

    def test_manager_seleciona_ambiente_none(self):
        """Testa __str__."""
        ambiente = Ambiente.objects.seleciona_ambiente(AmbienteModelTestCase.SYNC_JSON_NOT_OK)
        self.assertIsNone(ambiente)

    def test_str(self):
        """Testa __str__."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SGA)
        self.assertEqual(ambiente.nome, str(ambiente))

    def test_ok_base_url(self):
        """Testa validação de base_url válida (OK)."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SGA)
        self.assertEqual("https://test.moodle.com", ambiente.base_url)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"url": "https://test.moodle.com/"}))
        self.assertEqual("https://test.moodle.com", ambiente.base_url)

    def test_not_ok_base_url(self):
        """Testa validação de base_url (NOT OK)."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"url": None}))
        self.assertEqual("", ambiente.base_url)

    def test_ok_valid_expressao_seletora(self):
        """Testa validação de expressão seletora (OK)."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SGA)
        self.assertTrue(ambiente.valid_expressao_seletora)

    def test_not_ok_valid_expressao_seletora(self):
        """Testa validação de expressão seletora (NOT OK)."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": ""}))
        self.assertFalse(ambiente.valid_expressao_seletora)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": " "}))
        self.assertFalse(ambiente.valid_expressao_seletora)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": None}))
        self.assertFalse(ambiente.valid_expressao_seletora)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": "asdf asdf"}))
        self.assertFalse(ambiente.valid_expressao_seletora)

    def test_ok_can_send_to_local_suap(self):
        """Testa validação can_send_to_local_suap (OK)."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SUAP)
        self.assertTrue(ambiente.can_send_to_local_suap)

    def test_not_ok_can_send_to_local_suap(self):
        """Testa validação can_send_to_local_suap (NOT OK)."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SUAP | {"local_suap_active": False}))
        self.assertFalse(ambiente.can_send_to_local_suap)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SUAP | {"local_suap_token": None}))
        self.assertFalse(ambiente.can_send_to_local_suap)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SUAP | {"local_suap_token": ""}))
        self.assertFalse(ambiente.can_send_to_local_suap)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SUAP | {"local_suap_token": " "}))
        self.assertFalse(ambiente.can_send_to_local_suap)

    def test_ok_can_send_to_tool_sga(self):
        """Testa validação can_send_to_local_suap (OK)."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SGA)
        self.assertTrue(ambiente.can_send_to_tool_sga)

    def test_not_ok_can_send_to_tool_sga(self):
        """Testa validação can_send_to_tool_sga (NOT OK)."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False}))
        self.assertFalse(ambiente.can_send_to_tool_sga)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": None}))
        self.assertFalse(ambiente.can_send_to_tool_sga)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": ""}))
        self.assertFalse(ambiente.can_send_to_tool_sga)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": " "}))
        self.assertFalse(ambiente.can_send_to_tool_sga)

    def test_ok_which_broker(self):
        """Testa validação which_broker (OK)."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SGA)
        self.assertEqual("tool_sga", ambiente.which_broker)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False}))
        self.assertEqual("local_suap", ambiente.which_broker)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": None}))
        self.assertEqual("local_suap", ambiente.which_broker)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": ""}))
        self.assertEqual("local_suap", ambiente.which_broker)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": " "}))
        self.assertEqual("local_suap", ambiente.which_broker)

    def test_not_ok_which_broker(self):
        """Testa validação which_broker (NOT OK)."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False, "local_suap_active": False}))
        self.assertIsNone(ambiente.which_broker)

    def test_ok_token(self):
        """Testa validação token (OK)."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SGA)
        self.assertEqual(TEST_TOKEN, ambiente.token)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False}))
        self.assertEqual(TEST_TOKEN, ambiente.token)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": None}))
        self.assertEqual(TEST_TOKEN, ambiente.token)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": ""}))
        self.assertEqual(TEST_TOKEN, ambiente.token)

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": " "}))
        self.assertEqual(TEST_TOKEN, ambiente.token)

    def test_not_ok_token(self):
        """Testa validação token (NOT OK)."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False, "local_suap_active": False}))
        self.assertIsNone(ambiente.token)

    def test_ok_check_selectable(self):
        """Testa validação check_selectable (OK)."""
        ambiente = Ambiente(**AMBIENTE_GOOD_SGA)
        self.assertTrue(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_OK))
        self.assertFalse(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_NOT_OK))

    def test_not_ok_check_selectable(self):
        """Testa validação token (NOT OK)."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False, "local_suap_active": False}))
        self.assertFalse(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_OK))
        self.assertFalse(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_NOT_OK))

        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": ""}))
        self.assertFalse(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_OK))
        self.assertFalse(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_NOT_OK))

        ambiente = Ambiente(
            **(AMBIENTE_GOOD_SGA | {"tool_sga_active": False, "local_suap_active": False, "expressao_seletora": ""})
        )
        self.assertFalse(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_OK))
        self.assertFalse(ambiente.check_selectable(AmbienteModelTestCase.SYNC_JSON_NOT_OK))

    def test_ok_ambiente_ordering(self):
        """Testa ordenação de ambientes."""
        ambiente2 = Ambiente.objects.create(**(AMBIENTE_GOOD_SGA | {"ordem": 0}))

        ambientes = list(Ambiente.objects.all())
        # Ordenação por ordem, id
        self.assertEqual(ambientes[0], ambiente2)

    def test_ok_ambiente_verbose_names(self):
        """Testa verbose_name e verbose_name_plural."""
        self.assertEqual(Ambiente._meta.verbose_name, "ambiente")
        self.assertEqual(Ambiente._meta.verbose_name_plural, "ambientes")

    def test_ok_url(self):
        """Testa que PermissiveURLField aceita URLs http e https válidas."""
        for url in ["http://localhost:8000/path", "https://example.com"]:
            ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"nome": f"Ambiente {url}", "url": url}))
            ambiente.full_clean()

    def test_not_ok_url(self):
        """Testa que PermissiveURLField rejeita valores sem protocolo HTTP/HTTPS."""
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"nome": "Ambiente inválido", "url": "ftp://example.com"}))
        with self.assertRaises(ValidationError):
            ambiente.full_clean()

    def test_permissive_url_field_formfield_is_charfield(self):
        """Testa que o formfield do PermissiveURLField usa forms.CharField."""
        field = Ambiente._meta.get_field("url")
        form_field = field.formfield()
        self.assertIsInstance(form_field, forms.CharField)


class AmbienteAdminTestCase(TestCase):
    """Testes para AmbienteAdmin."""

    def setUp(self):
        """Configura o ambiente de teste."""
        from django.contrib.admin.sites import AdminSite

        from integrador.admin import AmbienteAdmin

        self.admin = AmbienteAdmin(Ambiente, AdminSite())
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

    @patch("requests.get")
    def test_ok_checked_url(self, mock_get):
        """Testa checked_url com sucesso."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = self.admin.checked_url(Ambiente(**AMBIENTE_GOOD_SGA))
        self.assertIn("✅", result)
        self.assertIn("https://test.moodle.com", result)

    @patch("requests.get")
    def test_not_ok_checked_url(self, mock_get):
        """Testa checked_url com falha."""
        mock_get.side_effect = Exception("Connection error")

        result = self.admin.checked_url(Ambiente(**AMBIENTE_GOOD_SGA))
        self.assertIn("🚫", result)

    def test_ok_checked_expressao_seletora(self):
        """Testa checked_expressao_seletora válida."""
        result = self.admin.checked_expressao_seletora(
            Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": "campus.sigla == 'TEST'"}))
        )
        self.assertIn("✅", result)

    def test_not_ok_checked_expressao_seletora(self):
        """Testa checked_expressao_seletora inválida."""
        result = self.admin.checked_expressao_seletora(
            Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": "invalid rule"}))
        )
        self.assertIn("🚫", result)

        result = self.admin.checked_expressao_seletora(Ambiente(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": None})))
        self.assertIn("⚠️", result)

    def test_ok_get_queryset(self):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        request = RequestFactory().get("/admin/integrador/ambiente/")
        self.assertEqual(1, len(self.admin.get_queryset(request)))

    @patch("requests.get")
    def test_ok_checked_tool_sga(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""

        # mock_get.side_effect = Exception("Connection error")
        mock_get.return_value = Mock(status_code=200, text="")
        result = self.admin.checked_tool_sga(Ambiente(**AMBIENTE_GOOD_SGA))
        self.assertIn("Tool SGA", result)
        self.assertIn("✅", result)

    @patch("requests.get")
    def test_not_ok_checked_tool_sga1(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""

        # mock_get.side_effect = Exception("Connection error")
        mock_get.return_value = Mock(status_code=401, text="")
        result = self.admin.checked_tool_sga(Ambiente(**AMBIENTE_GOOD_SGA))
        self.assertIn("Tool SGA", result)
        self.assertIn("🔑", result)  # Token inválido

    @patch("requests.get")
    def test_not_ok_checked_tool_sga2(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        result = self.admin.checked_tool_sga(Ambiente(**AMBIENTE_GOOD_SGA))
        self.assertIn("Tool SGA", result)
        self.assertIn("❌", result)  # Qualquer outro erro

    @patch("requests.get")
    def test_not_ok_checked_tool_sga3(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False, "tool_sga_token": None}))
        result = self.admin.checked_tool_sga(ambiente)
        self.assertIn("Tool SGA", result)
        self.assertIn("🚫", result)

    @patch("requests.get")
    def test_not_ok_checked_tool_sga4(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_active": False}))
        result = self.admin.checked_tool_sga(ambiente)
        self.assertIn("Tool SGA", result)
        self.assertIn("⏸️", result)

    @patch("requests.get")
    def test_not_ok_checked_tool_sga5(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        ambiente = Ambiente(**(AMBIENTE_GOOD_SGA | {"tool_sga_token": None}))
        result = self.admin.checked_tool_sga(ambiente)
        self.assertIn("Tool SGA", result)
        self.assertIn("⚠️", result)

    def test_not_ok_checked_tool_sga6(self):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        result = self.admin.checked_tool_sga(Ambiente(**AMBIENTE_GOOD_SGA))
        self.assertIn("Tool SGA", result)
        self.assertIn("⛔", result)

    @patch("requests.get")
    def test_ok_checked_local_suap(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""

        # mock_get.side_effect = Exception("Connection error")
        mock_get.return_value = Mock(status_code=200, text="")
        result = self.admin.checked_local_suap(Ambiente(**AMBIENTE_GOOD_SUAP))
        self.assertIn("Local SUAP", result)
        self.assertIn("✅", result)

    @patch("requests.get")
    def test_not_ok_checked_local_suap1(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""

        # mock_get.side_effect = Exception("Connection error")
        mock_get.return_value = Mock(status_code=401, text="")
        result = self.admin.checked_local_suap(Ambiente(**AMBIENTE_GOOD_SUAP))
        self.assertIn("Local SUAP", result)
        self.assertIn("🔑", result)  # Token inválido

    @patch("requests.get")
    def test_not_ok_checked_local_suap2(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        result = self.admin.checked_local_suap(Ambiente(**AMBIENTE_GOOD_SUAP))
        self.assertIn("Local SUAP", result)
        self.assertIn("❌", result)  # Qualquer outro erro

    @patch("requests.get")
    def test_not_ok_checked_local_suap3(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        ambiente = Ambiente(**(AMBIENTE_GOOD_SUAP | {"local_suap_active": False, "local_suap_token": None}))
        result = self.admin.checked_local_suap(ambiente)
        self.assertIn("Local SUAP", result)
        self.assertIn("🚫", result)

    @patch("requests.get")
    def test_not_ok_checked_local_suap4(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        ambiente = Ambiente(**(AMBIENTE_GOOD_SUAP | {"local_suap_active": False}))
        result = self.admin.checked_local_suap(ambiente)
        self.assertIn("Local SUAP", result)
        self.assertIn("⏸️", result)

    @patch("requests.get")
    def test_not_ok_checked_local_suap5(self, mock_get):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        mock_get.return_value = Mock(status_code=500, text="")
        ambiente = Ambiente(**(AMBIENTE_GOOD_SUAP | {"local_suap_token": None}))
        result = self.admin.checked_local_suap(ambiente)
        self.assertIn("Local SUAP", result)
        self.assertIn("⚠️", result)

    def test_not_ok_checked_local_suap6(self):
        """Testa que AmbienteAdmin.get_queryset chama all() no queryset base."""
        result = self.admin.checked_local_suap(Ambiente(**(AMBIENTE_GOOD_SUAP)))
        self.assertIn("Local SUAP", result)
        self.assertIn("⛔", result)


class DecoratorsTestCase(TestCase):
    """Testes para decorators."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()

    def test_json_response_decorator_with_dict(self):
        """Testa decorator json_response com dicionário."""

        @json_response
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/")
        response = test_view(request)

        self.assertIsInstance(response, JsonResponse)

    def test_json_response_decorator_with_json_response(self):
        """Testa decorator json_response com JsonResponse."""

        @json_response
        def test_view(request):
            return JsonResponse({"status": "ok"})

        request = self.factory.get("/test/")
        response = test_view(request)

        self.assertIsInstance(response, JsonResponse)

    def test_exception_as_json_decorator_success(self):
        """Testa decorator exception_as_json com sucesso."""

        @exception_as_json
        def test_view(request):
            return JsonResponse({"status": "ok"})

        request = self.factory.get("/test/")
        response = test_view(request)

        self.assertEqual(response.status_code, 200)

    def test_exception_as_json_decorator_with_sync_error(self):
        """Testa decorator exception_as_json com SyncError."""

        @exception_as_json
        def test_view(request):
            raise SyncError("Test error", 400)

        request = self.factory.get("/test/")
        response = test_view(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_exception_as_json_decorator_with_generic_exception(self):
        """Testa decorator exception_as_json com exceção genérica."""

        @exception_as_json
        def test_view(request):
            raise Exception("Generic error")

        request = self.factory.get("/test/")
        response = test_view(request)

        self.assertEqual(response.status_code, 500)

    @override_settings(SUAP_INTEGRADOR_KEY=TEST_TOKEN)
    def test_valid_token_decorator_success(self):
        """Testa decorator valid_token com token válido."""

        @valid_token
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/")
        request.META["HTTP_AUTHENTICATION"] = f"Token {TEST_TOKEN}"

        result = test_view(request)
        self.assertEqual(result["status"], "ok")

    @override_settings(SUAP_INTEGRADOR_KEY=TEST_TOKEN)
    def test_valid_token_decorator_invalid_token(self):
        """Testa decorator valid_token com token inválido."""

        @valid_token
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/")
        request.META["HTTP_AUTHENTICATION"] = f"Token {TEST_TOKEN_NOT_OK}"

        with self.assertRaises(SyncError) as context:
            test_view(request)

        self.assertEqual(context.exception.code, 403)

    @override_settings(SUAP_INTEGRADOR_KEY=TEST_TOKEN)
    def test_valid_token_decorator_missing_token(self):
        """Testa decorator valid_token sem token."""

        @valid_token
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/")

        with self.assertRaises(SyncError) as context:
            test_view(request)

        self.assertEqual(context.exception.code, 431)

    def test_check_is_post_decorator_success(self):
        """Testa decorator check_is_post com POST."""

        @check_is_post
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.post("/test/")
        result = test_view(request)

        self.assertEqual(result["status"], "ok")

    def test_check_is_post_decorator_failure(self):
        """Testa decorator check_is_post com GET."""

        @check_is_post
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/")

        with self.assertRaises(SyncError) as context:
            test_view(request)

        self.assertEqual(context.exception.code, 501)

    def test_check_is_get_decorator_success(self):
        """Testa decorator check_is_get com GET."""

        @check_is_get
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/")
        result = test_view(request)

        self.assertEqual(result["status"], "ok")

    def test_check_is_get_decorator_failure(self):
        """Testa decorator check_is_get com POST."""

        @check_is_get
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.post("/test/")

        with self.assertRaises(SyncError) as context:
            test_view(request)

        self.assertEqual(context.exception.code, 501)

    def test_check_json_decorator_valid_json(self):
        """Testa decorator check_json com JSON válido."""

        @check_json(Solicitacao.Operacao.SYNC_UP_DIARIO)
        def test_view(request):
            return request.json_recebido

        json_data = {"campus": {"sigla": "TEST"}}
        request = self.factory.post("/test/", data=json.dumps(json_data), content_type="application/json")

        result = test_view(request)
        self.assertEqual(result, json_data)

    def test_check_json_decorator_invalid_json(self):
        """Testa decorator check_json com JSON inválido."""

        @check_json(Solicitacao.Operacao.SYNC_UP_DIARIO)
        def test_view(request):
            return request.json_recebido

        request = self.factory.post("/test/", data="invalid json {{{", content_type="application/json")

        result = test_view(request)
        self.assertIn("check_json", result)
        self.assertIn("error", result.get("check_json", {}))

    def test_detect_ambiente_decorator_found(self):
        """Testa decorator detect_ambiente encontrando ambiente."""
        Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        @detect_ambiente
        def test_view(request):
            return {"ambiente": request.ambiente.nome}

        request = self.factory.get("/test/?campus_sigla=TEST")
        request.json_recebido = {"campus": {"sigla": "TEST"}}

        response = test_view(request)
        data = json.loads(response.content)
        self.assertEqual(data["ambiente"], "Ambiente Teste")

    def test_detect_ambiente_decorator_not_found(self):
        """Testa decorator detect_ambiente não encontrando ambiente."""

        @detect_ambiente
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/?campus_sigla=INEXISTENTE")
        request.json_recebido = {"campus": {"sigla": "INEXISTENTE"}}

        with self.assertRaises(SyncError) as context:
            test_view(request)

        self.assertEqual(context.exception.code, 404)


class TrySolicitacaoDecoratorTestCase(TestCase):
    """Testes para o decorator try_solicitacao."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

    def test_try_solicitacao_success(self):
        """Testa try_solicitacao com sucesso."""

        @try_solicitacao(Solicitacao.Operacao.SYNC_UP_DIARIO)
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.post("/test/")
        request.ambiente = self.ambiente
        request.json_recebido = {
            "campus": {"sigla": "TEST"},
            "turma": {"codigo": "T1"},
            "componente": {"sigla": "C1"},
            "diario": {"id": 123},
        }

        result = test_view(request)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(Solicitacao.objects.count(), 1)

        solicitacao = Solicitacao.objects.first()
        self.assertEqual(solicitacao.status, Solicitacao.Status.SUCESSO)

    def test_try_solicitacao_with_error(self):
        """Testa try_solicitacao com erro na view."""

        @try_solicitacao(Solicitacao.Operacao.SYNC_UP_DIARIO)
        def test_view(request):
            raise Exception("View error")

        request = self.factory.post("/test/")
        request.ambiente = self.ambiente
        request.json_recebido = {
            "campus": {"sigla": "TEST"},
            "turma": {"codigo": "T1"},
            "componente": {"sigla": "C1"},
            "diario": {"id": 123},
        }

        with self.assertRaises(SyncError):
            test_view(request)

        solicitacao = Solicitacao.objects.first()
        self.assertEqual(solicitacao.status, Solicitacao.Status.FALHA)

    def test_try_solicitacao_with_json_error(self):
        """Testa try_solicitacao com erro no JSON."""

        @try_solicitacao(Solicitacao.Operacao.SYNC_UP_DIARIO)
        def test_view(request):
            return {"status": "ok"}

        request = self.factory.post("/test/")
        request.ambiente = self.ambiente
        request.json_recebido = {"error": {"code": 400, "message": "Invalid JSON"}}

        with self.assertRaises(SyncError) as context:
            test_view(request)

        self.assertEqual(context.exception.code, 400)


class CohortSelecaoTestCase(TestCase):
    """Testes de seleção de coortes para sincronização, com exemplos reais."""

    SYNC_JSON_COM_POLO = {
        "campus": {"id": 14, "sigla": "ZL", "descricao": "Campus EaD"},
        "curso": {"id": 1, "codigo": "15056", "nome": "Sistemas Operacionais Abertos"},
        "turma": {"id": 2, "codigo": "20261.6.15056.1E"},
        "componente": {"id": 1, "sigla": "TEC.1023", "descricao": "Bancos de Dados"},
        "diario": {"id": 2, "sigla": "TEC.1023", "situacao": "Aberto"},
        "alunos": [
            {"polo": {"descricao": "Natal (RN)"}, "programa": "Institucional"},
            {"polo": {"descricao": "Mossoró (RN)"}, "programa": "UAB"},
        ],
    }
    SYNC_JSON_SEM_POLO = {
        "campus": {"id": 14, "sigla": "ZL", "descricao": "Campus EaD"},
        "curso": {"id": 2, "codigo": "99999", "nome": "Curso Sem Polo"},
        "turma": {"id": 3, "codigo": "20261.6.99999.1E"},
        "componente": {"id": 2, "sigla": "TEC.9999", "descricao": "Disciplina Sem Polo"},
        "diario": {"id": 3, "sigla": "TEC.9999", "situacao": "Aberto"},
        "alunos": [
            {"polo": {"descricao": "Sem polo"}, "programa": "Institucional"},
        ],
    }

    def setUp(self):
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)
        self.solicitacao = Solicitacao.objects.create(
            ambiente=self.ambiente,
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            recebido=self.SYNC_JSON_COM_POLO,
        )
        self.broker = BaseBroker(self.solicitacao)

        self.role_coo_polo = Role.objects.create(name="ZL.CooPolo", shortname="coordenadordepolo", active=True)
        self.role_coo_curso = Role.objects.create(name="ZL.CooCurso", shortname="coordenadordecurso", active=True)
        self.role_tut = Role.objects.create(name="ZL.CooTutProg", shortname="tutordeprograma", active=True)

    def _cria_cohort(self, name, idnumber, role, rule_diario, rule_coordenacao, active=True):
        return Cohort.objects.create(
            name=name,
            idnumber=idnumber,
            role=role,
            rule_diario=rule_diario,
            rule_coordenacao=rule_coordenacao,
            active=active,
        )

    def _adiciona_colaborador(self, cohort, login, nome, email):
        user, _ = MoodleUser.objects.get_or_create(
            login=login, defaults={"fullname": nome, "email": email, "active": True}
        )
        Enrolment.objects.create(cohort=cohort, user=user)
        return user

    # --- Sem coortes ---

    def test_sem_coortes_cadastradas_retorna_lista_vazia(self):
        """Sem nenhuma coorte no banco, get_cohort retorna lista vazia."""
        resultado = self.broker.get_cohort()
        self.assertEqual(resultado, [])

    def test_sem_coortes_ativas_retorna_lista_vazia(self):
        """Coorte inativa nunca é incluída, mesmo com regra correspondente."""
        self._cria_cohort(
            name="ZL.CooPolo.Natal(RN)",
            idnumber="ZL.CooPolo.Natal(RN)",
            role=self.role_coo_polo,
            rule_diario='$any([aluno.polo.descricao == "Natal (RN)" for aluno in alunos])',
            rule_coordenacao='$any([aluno.polo.descricao == "Natal (RN)" for aluno in alunos])',
            active=False,
        )
        resultado = self.broker.get_cohort()
        self.assertEqual(resultado, [])

    def test_sem_coorte_correspondente_retorna_lista_vazia(self):
        """Coorte ativa mas sem regra que corresponda ao JSON retorna lista vazia."""
        self._cria_cohort(
            name="ZL.CooPolo.Parelhas",
            idnumber="ZL.CooPolo.Parelhas",
            role=self.role_coo_polo,
            rule_diario='$any([aluno.polo.descricao == "Parelhas" for aluno in alunos])',
            rule_coordenacao='$any([aluno.polo.descricao == "Parelhas" for aluno in alunos])',
        )
        self.solicitacao.recebido = self.SYNC_JSON_SEM_POLO
        resultado = self.broker.get_cohort()
        self.assertEqual(resultado, [])

    # --- Com coortes por polo ---

    def test_coorte_polo_natal_corresponde_ao_json(self):
        """Coorte de polo Natal(RN) é selecionada quando há aluno desse polo."""
        cohort = self._cria_cohort(
            name="ZL.CooPolo.Natal(RN)",
            idnumber="ZL.CooPolo.Natal(RN)",
            role=self.role_coo_polo,
            rule_diario='$any([aluno.polo.descricao == "Natal (RN)" for aluno in alunos])',
            rule_coordenacao='$any([aluno.polo.descricao == "Natal (RN)" for aluno in alunos])',
        )
        self._adiciona_colaborador(cohort, "coord.natal", "Coord Natal", "coord.natal@ifrn.edu.br")
        resultado = self.broker.get_cohort()
        idnumbers = [c["idnumber"] for c in resultado]
        self.assertIn("ZL.CooPolo.Natal(RN)", idnumbers)

    def test_coorte_polo_mossoro_nao_corresponde_sem_aluno_desse_polo(self):
        """Coorte de Mossoró não é selecionada quando não há aluno desse polo."""
        self._cria_cohort(
            name="ZL.CooPolo.Mossoró (RN)",
            idnumber="ZL.CooPolo.Mossoró (RN)",
            role=self.role_coo_polo,
            rule_diario='$any([aluno.polo.descricao == "Mossoró (RN)" for aluno in alunos])',
            rule_coordenacao='$any([aluno.polo.descricao == "Mossoró (RN)" for aluno in alunos])',
        )
        self.solicitacao.recebido = self.SYNC_JSON_SEM_POLO
        resultado = self.broker.get_cohort()
        self.assertEqual(resultado, [])

    # --- Com coortes por curso ---

    def test_coorte_curso_15056_corresponde_ao_json(self):
        """Coorte de coordenação do curso 15056 é selecionada pelo código do curso."""
        cohort = self._cria_cohort(
            name="ZL.CooCurso.15056",
            idnumber="ZL.CooCurso.15056",
            role=self.role_coo_curso,
            rule_diario='curso.codigo == "15056"',
            rule_coordenacao='curso.codigo == "15056"',
        )
        self._adiciona_colaborador(cohort, "coo.curso15056", "Coo Curso 15056", "coo@ifrn.edu.br")
        resultado = self.broker.get_cohort()
        idnumbers = [c["idnumber"] for c in resultado]
        self.assertIn("ZL.CooCurso.15056", idnumbers)

    def test_coorte_curso_diferente_nao_corresponde(self):
        """Coorte com código de curso diferente não é selecionada."""
        self._cria_cohort(
            name="ZL.CooCurso.99624",
            idnumber="ZL.CooCurso.99624",
            role=self.role_coo_curso,
            rule_diario='curso.codigo == "99624"',
            rule_coordenacao='curso.codigo == "99624"',
        )
        resultado = self.broker.get_cohort()
        self.assertEqual(resultado, [])

    # --- Com coortes por programa ---

    def test_coorte_programa_uab_corresponde_quando_ha_aluno_uab(self):
        """Coorte UAB é selecionada quando há aluno com programa UAB."""
        cohort = self._cria_cohort(
            name="ZL.CooTutProg.UAB",
            idnumber="ZL.CooTutProg.UAB",
            role=self.role_tut,
            rule_diario='$any([aluno.programa == "UAB" for aluno in alunos])',
            rule_coordenacao='$any([aluno.programa == "UAB" for aluno in alunos])',
        )
        self._adiciona_colaborador(cohort, "tut.uab", "Tutor UAB", "tut.uab@ifrn.edu.br")
        resultado = self.broker.get_cohort()
        idnumbers = [c["idnumber"] for c in resultado]
        self.assertIn("ZL.CooTutProg.UAB", idnumbers)

    # --- Múltiplas coortes simultâneas ---

    def test_multiplas_coortes_correspondentes_todas_incluidas(self):
        """Quando polo e curso correspondem, ambas as coortes são retornadas."""
        c1 = self._cria_cohort(
            name="ZL.CooPolo.Natal(RN)",
            idnumber="ZL.CooPolo.Natal(RN)",
            role=self.role_coo_polo,
            rule_diario='$any([aluno.polo.descricao == "Natal (RN)" for aluno in alunos])',
            rule_coordenacao='$any([aluno.polo.descricao == "Natal (RN)" for aluno in alunos])',
        )
        c2 = self._cria_cohort(
            name="ZL.CooCurso.15056",
            idnumber="ZL.CooCurso.15056",
            role=self.role_coo_curso,
            rule_diario='curso.codigo == "15056"',
            rule_coordenacao='curso.codigo == "15056"',
        )
        self._adiciona_colaborador(c1, "coord.natal", "Coord Natal", "coord.natal@ifrn.edu.br")
        self._adiciona_colaborador(c2, "coo.curso", "Coo Curso", "coo.curso@ifrn.edu.br")

        resultado = self.broker.get_cohort()
        idnumbers = [c["idnumber"] for c in resultado]
        self.assertIn("ZL.CooPolo.Natal(RN)", idnumbers)
        self.assertIn("ZL.CooCurso.15056", idnumbers)

    # --- Payload das coortes ---

    def test_payload_da_coorte_inclui_colaboradores(self):
        """Coorte retornada deve incluir colaboradores com dados corretos."""
        cohort = self._cria_cohort(
            name="ZL.CooCurso.15056",
            idnumber="ZL.CooCurso.15056",
            role=self.role_coo_curso,
            rule_diario='curso.codigo == "15056"',
            rule_coordenacao='curso.codigo == "15056"',
        )
        self._adiciona_colaborador(cohort, "coord.x", "Coord X", "coord.x@ifrn.edu.br")

        resultado = self.broker.get_cohort()
        coorte = next(c for c in resultado if c["idnumber"] == "ZL.CooCurso.15056")
        self.assertEqual(coorte["nome"], "ZL.CooCurso.15056")
        self.assertEqual(coorte["role"], "coordenadordecurso")
        colaboradores = coorte["colaboradores"]
        self.assertEqual(len(colaboradores), 1)
        self.assertEqual(colaboradores[0]["login"], "coord.x")
        self.assertEqual(colaboradores[0]["email"], "coord.x@ifrn.edu.br")


class SolicitacaoModelTestCase(TestCase):
    """Testes para o modelo Solicitacao."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        self.recebido_json = {
            "campus": {"sigla": "TEST"},
            "turma": {"codigo": "20261.1.132456.123.1M"},
            "componente": {"sigla": "MAT.001"},
            "diario": {"id": 12345, "tipo": "regular"},
        }

        self.solicitacao = Solicitacao.objects.create(
            ambiente=self.ambiente,
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            status=Solicitacao.Status.PROCESSANDO,
            recebido=self.recebido_json,
        )

    def test_create_solicitacao(self):
        """Testa criação de solicitação."""
        solicitacao = Solicitacao.objects.create(
            ambiente=self.ambiente,
            operacao=Solicitacao.Operacao.SYNC_DOWN_NOTAS,
            status=Solicitacao.Status.SUCESSO,
            recebido={"campus": {"sigla": "TEST"}, "diario": {"id": 999}},
        )

        self.assertIsNotNone(solicitacao.pk)
        self.assertEqual(solicitacao.operacao, Solicitacao.Operacao.SYNC_DOWN_NOTAS)

    def test_solicitacao_str_representation(self):
        """Testa representação em string da solicitação."""
        string_repr = str(self.solicitacao)

        self.assertIn("TEST", string_repr)
        self.assertIn("12345", string_repr)

    def test_solicitacao_auto_populate_on_save(self):
        """Testa que save() popula campos automaticamente."""
        self.assertEqual(self.solicitacao.campus_sigla, "TEST")
        self.assertEqual(self.solicitacao.diario_id, 12345)
        self.assertEqual(self.solicitacao.tipo, "regular")
        # diario_codigo é gerado como turma.codigo#diario.id
        self.assertIn("20261.1.132456.123.1M", self.solicitacao.diario_codigo)
        self.assertIn("#12345", self.solicitacao.diario_codigo)

    def test_solicitacao_status_merged_property(self):
        """Testa propriedade status_merged."""
        self.solicitacao.status = Solicitacao.Status.SUCESSO
        self.solicitacao.status_code = "200"

        status_html = self.solicitacao.status_merged

        self.assertIn("Sucesso", status_html)
        self.assertIn("200", status_html)

    def test_solicitacao_timestamp_auto_created(self):
        """Testa que timestamp é criado automaticamente."""
        self.assertIsNotNone(self.solicitacao.timestamp)

    def test_solicitacao_ordering(self):
        """Testa ordenação de solicitações."""
        solicitacao2 = Solicitacao.objects.create(
            ambiente=self.ambiente,
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            recebido={"campus": {"sigla": "TEST"}, "diario": {"id": 999}},
        )

        solicitacoes = list(Solicitacao.objects.all())
        # Ordenação por -timestamp (mais recentes primeiro)
        self.assertEqual(solicitacoes[0], solicitacao2)

    def test_solicitacao_status_choices(self):
        """Testa choices de status."""
        self.solicitacao.status = Solicitacao.Status.SUCESSO
        self.solicitacao.save()

        solicitacao = Solicitacao.objects.get(pk=self.solicitacao.pk)
        self.assertEqual(solicitacao.status, Solicitacao.Status.SUCESSO)

    def test_solicitacao_save_accepts_django_keyword_arguments(self):
        """Testa que save() delega corretamente para o Model.save do Django."""
        self.solicitacao.status = Solicitacao.Status.SUCESSO
        self.solicitacao.status_code = "200"

        self.solicitacao.save(update_fields=["status", "status_code"])

        solicitacao = Solicitacao.objects.get(pk=self.solicitacao.pk)
        self.assertEqual(solicitacao.status, Solicitacao.Status.SUCESSO)
        self.assertEqual(solicitacao.status_code, "200")

    def test_solicitacao_operacao_choices(self):
        """Testa choices de operação."""
        self.assertEqual(self.solicitacao.operacao, Solicitacao.Operacao.SYNC_UP_DIARIO)

    def test_solicitacao_json_fields(self):
        """Testa campos JSON."""
        self.solicitacao.enviado = {"test": "data"}
        self.solicitacao.respondido = {"response": "ok"}
        self.solicitacao.save()

        solicitacao = Solicitacao.objects.get(pk=self.solicitacao.pk)
        self.assertEqual(solicitacao.enviado["test"], "data")
        self.assertEqual(solicitacao.respondido["response"], "ok")

    def test_solicitacao_verbose_names(self):
        """Testa verbose_name e verbose_name_plural."""
        self.assertEqual(Solicitacao._meta.verbose_name, "solicitação")
        self.assertEqual(Solicitacao._meta.verbose_name_plural, "solicitações")


class SolicitacaoAdminTestCase(TestCase):
    """Testes para SolicitacaoAdmin."""

    def setUp(self):
        """Configura o ambiente de teste."""
        from django.contrib.admin.sites import AdminSite

        from integrador.admin import SolicitacaoAdmin

        self.admin = SolicitacaoAdmin(Solicitacao, AdminSite())
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)
        self.solicitacao = Solicitacao.objects.create(
            ambiente=self.ambiente,
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            tipo="CRIAR_DIARIO",
            status=Solicitacao.Status.PROCESSANDO,
            recebido={"diario": {"id": 123, "codigo": "TEST123"}},
        )

    def test_status_merged(self):
        """Testa status_merged."""
        result = self.admin.status_merged(self.solicitacao)
        self.assertIn("Processando", result)

    def test_acoes(self):
        """Testa acoes."""
        result = self.admin.acoes(self.solicitacao)
        self.assertIn("Reenviar", result)

    def test_quando(self):
        """Testa quando."""
        result = self.admin.quando(self.solicitacao)
        self.assertIsInstance(result, str)

    def test_quando_without_timestamp_returns_dash(self):
        """Testa quando sem timestamp."""
        self.solicitacao.timestamp = None
        result = self.admin.quando(self.solicitacao)
        self.assertEqual(result, "-")

    def test_professores(self):
        """Testa professores."""
        self.solicitacao.recebido = {"professores": [{"nome": "Prof Test", "login": "prof123", "tipo": "servidor"}]}
        result = self.admin.professores(self.solicitacao)
        self.assertIn("Prof Test", result)

    def test_professores_returns_dash_when_empty(self):
        """Testa professores sem entradas."""
        self.solicitacao.recebido = {"professores": []}
        result = self.admin.professores(self.solicitacao)
        self.assertEqual(result, "-")

    def test_professores_returns_dash_on_exception(self):
        """Testa professores retornando '-' em erro inesperado."""
        self.solicitacao.recebido = {"professores": [{"nome": "Prof Test", "login": object(), "tipo": "servidor"}]}
        result = self.admin.professores(self.solicitacao)
        self.assertEqual(result, "-")

    def test_codigo_diario(self):
        """Testa codigo_diario."""
        self.solicitacao.respondido = {"url": "https://test.com/diario"}
        result = self.admin.codigo_diario(self.solicitacao)
        self.assertIn("https://test.com/diario", result)

    def test_codigo_diario_returns_dash_on_exception(self):
        """Testa codigo_diario retornando '-' em erro inesperado."""
        self.solicitacao.respondido = object()
        result = self.admin.codigo_diario(self.solicitacao)
        self.assertEqual(result, "-")

    def test_get_urls_wrap_executes_admin_view_wrapper(self):
        """Testa wrapper de get_urls delegando para admin_site.admin_view."""
        with patch.object(
            self.admin.admin_site, "admin_view", return_value=lambda *args, **kwargs: "ok"
        ) as mock_admin_view:
            urls = self.admin.get_urls()
            callback = urls[0].callback
            result = callback(Mock(), object_id=str(self.solicitacao.id))

        self.assertEqual(result, "ok")
        self.assertTrue(mock_admin_view.called)
        called_views = [call.args[0] for call in mock_admin_view.call_args_list]
        self.assertIn(self.admin.sync_moodle_view, called_views)

    @patch("integrador.admin.Suap2LocalSuapBroker")
    def test_sync_moodle_view_success(self, mock_broker):
        """Testa sync_moodle_view com sucesso."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get(f"/admin/integrador/solicitacao/{self.solicitacao.id}/sync_moodle/")

        mock_instance = Mock()
        mock_instance.sync_up_enrolments.return_value = self.solicitacao
        mock_broker.return_value = mock_instance

        response = self.admin.sync_moodle_view(request, self.solicitacao.id)
        self.assertEqual(response.status_code, 302)  # Redirect

    @patch("integrador.admin.Suap2LocalSuapBroker")
    def test_sync_moodle_view_error(self, mock_broker):
        """Testa sync_moodle_view com erro."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get(f"/admin/integrador/solicitacao/{self.solicitacao.id}/sync_moodle/")

        mock_broker.side_effect = Exception("Test error")

        response = self.admin.sync_moodle_view(request, self.solicitacao.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Test error", response.content.decode())

    @patch("integrador.admin.Suap2LocalSuapBroker")
    def test_sync_moodle_view_handles_none_response(self, mock_broker):
        """Testa sync_moodle_view quando broker retorna None."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get(f"/admin/integrador/solicitacao/{self.solicitacao.id}/sync_moodle/")

        mock_instance = Mock()
        mock_instance.sync_up_enrolments.return_value = None
        mock_broker.return_value = mock_instance

        response = self.admin.sync_moodle_view(request, self.solicitacao.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Erro desconhecido", response.content.decode())

    @patch("base.admin.BaseModelAdmin.get_queryset")
    def test_get_queryset_select_related_ambiente(self, mock_get_queryset):
        """Testa que SolicitacaoAdmin.get_queryset aplica select_related em ambiente."""
        request = RequestFactory().get("/admin/integrador/solicitacao/")
        request.user = User.objects.create_superuser("admin_sol", "admin_sol@test.com", str(uuid.uuid4()))

        mock_qs = Mock()
        mock_qs.select_related.return_value = "SELECT_RELATED_QS"
        mock_get_queryset.return_value = mock_qs

        result = self.admin.get_queryset(request)

        self.assertEqual(result, "SELECT_RELATED_QS")
        mock_qs.select_related.assert_called_once_with("ambiente")


class BaseBrokerTestCase(TestCase):
    """Testes para BaseBroker."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        self.solicitacao = Solicitacao.objects.create(
            ambiente=self.ambiente, operacao=Solicitacao.Operacao.SYNC_UP_DIARIO, recebido={"diario": {"id": 123}}
        )

        self.broker = BaseBroker(self.solicitacao)

    def test_base_broker_initialization(self):
        """Testa inicialização do BaseBroker."""
        self.assertEqual(self.broker.solicitacao, self.solicitacao)
        self.assertEqual(self.broker.solicitacao.ambiente, self.ambiente)

    def test_base_broker_credentials_property(self):
        """Testa propriedade credentials."""
        credentials = self.broker.credentials

        self.assertIn("Authentication", credentials)
        self.assertIn(f"Token {TEST_TOKEN}", credentials["Authentication"])

    def test_base_broker_get_cohorts(self):
        """Testa método get_cohort."""
        cohorts = self.broker.get_cohort()

        self.assertEqual(cohorts, [])

    def test_base_broker_sync_up_enrolments_not_implemented(self):
        """Testa que sync_up_enrolments não está implementado."""
        with self.assertRaises(NotImplementedError):
            self.broker.sync_up_enrolments()

    def test_base_broker_sync_down_grades_not_implemented(self):
        """Testa que sync_down_grades não está implementado."""
        with self.assertRaises(NotImplementedError):
            self.broker.sync_down_grades()

    def test_base_broker_cast_cohort_maps_expected_payload(self):
        """Testa cast_cohort com mapeamento completo de dados."""
        user = Mock(fullname="User Name", email="user@test.com", login="user_login", active=True)
        role = Mock(name="Coordenador de curso", shortname="coordenadordecurso", active=True)
        enrolment = Mock(user=user)
        enrolments = Mock()
        enrolments.select_related.return_value.all.return_value = [enrolment]
        cohort = SimpleNamespace(
            name="Cohort Test",
            role=role,
            active=True,
            idnumber="COHORT-1",
            description="Desc",
            enrolments=enrolments,
        )

        payload = self.broker.cast_cohort(cohort)

        self.assertEqual(payload["nome"], "Cohort Test")
        self.assertEqual(payload["role"], "coordenadordecurso")
        self.assertEqual(payload["idnumber"], "COHORT-1")
        self.assertEqual(payload["colaboradores"][0]["email"], "user@test.com")

    @patch("integrador.brokers.base.logger.warning")
    @patch("integrador.brokers.base.rule_engine.Rule")
    def test_base_broker_cohort_matches_handles_rule_error(self, mock_rule, mock_warning):
        """Testa cohort_matches quando a avaliação da regra falha."""
        cohort = Mock(id=10, name="Cohort Error", rule_diario="invalid")
        mock_rule.side_effect = Exception("invalid rule")

        result = self.broker.cohort_matches(cohort, "rule_diario")

        self.assertFalse(result)
        mock_warning.assert_called_once()

    @patch("integrador.brokers.base.Cohort.objects.filter")
    def test_base_broker_get_cohort_combines_diario_and_coordenacao(self, mock_filter):
        """Testa get_cohort combinando cohorts elegíveis por regras diferentes."""
        cohort_a = SimpleNamespace(name="A")
        cohort_b = SimpleNamespace(name="B")
        mock_filter.return_value = [cohort_a, cohort_b]

        with patch.object(self.broker, "cohort_matches") as mock_matches:
            mock_matches.side_effect = lambda cohort, field: (cohort is cohort_a and field == "rule_diario") or (
                cohort is cohort_b and field == "rule_coordenacao"
            )
            with patch.object(self.broker, "cast_cohort") as mock_cast:
                mock_cast.side_effect = lambda cohort: {"nome": cohort.name}

                cohorts = self.broker.get_cohort()

        self.assertEqual(cohorts, [{"nome": "A"}, {"nome": "B"}])


class Suap2LocalSuapBrokerTestCase(TestCase):
    """Testes para Suap2LocalSuapBroker."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        self.solicitacao = Solicitacao.objects.create(
            ambiente=self.ambiente,
            operacao=Solicitacao.Operacao.SYNC_UP_DIARIO,
            diario_id="123",
            recebido={
                "campus": {"id": 1, "sigla": "TEST", "descricao": "Campus Teste"},
                "curso": {"id": 10, "codigo": "15806", "nome": "Sistemas Operacionais Abertos"},
                "turma": {"id": 2, "codigo": "T1"},
                "componente": {"id": 5, "sigla": "TEC.1023", "descricao": "Bancos de Dados"},
                "diario": {"id": 123, "sigla": "TEC.1023", "situacao": "Aberto"},
            },
        )

        self.broker = Suap2LocalSuapBroker(self.solicitacao)

    def test_broker_initialization(self):
        """Testa inicialização do broker."""
        self.assertEqual(self.broker.solicitacao, self.solicitacao)

    def test_broker_moodle_base_api_url_property(self):
        """Testa propriedade moodle_base_api_url."""
        self.assertEqual(self.broker.moodle_base_api_url, "https://test.moodle.com/local/suap/api")

    @patch("integrador.brokers.suap2local_suap.http_post_json")
    def test_broker_sync_up_enrolments_success(self, mock_http_post_json):
        """Testa sync_up_enrolments com sucesso."""
        mock_http_post_json.return_value = {
            "url": "https://test.moodle.com/course/view.php?id=1",
            "url_sala_coordenacao": "https://test.moodle.com/course/view.php?id=2",
            "roles_not_found": [],
        }

        result = self.broker.sync_up_enrolments()

        self.assertIn("url", result)
        self.assertIn("url_sala_coordenacao", result)
        self.assertEqual(result["roles_not_found"], [])
        self.assertEqual(result["ambiente"], "https://test.moodle.com")
        mock_http_post_json.assert_called_once()

    def test_broker_sync_up_enrolments_payload_faltando_campo_obrigatorio(self):
        """Testa que SyncError é lançado quando o payload não tem campos obrigatórios."""
        self.solicitacao.recebido = {"diario": {"id": 1}}  # incompleto
        self.solicitacao.save()
        with self.assertRaises(SyncError) as ctx:
            self.broker.sync_up_enrolments()
        self.assertEqual(ctx.exception.code, 422)
        self.assertIn("campus", str(ctx.exception))

    @patch("integrador.brokers.suap2local_suap.http_post_json")
    def test_broker_sync_up_enrolments_raises_sync_error_when_get_cohort_fails(self, mock_http_post_json):
        """Testa sync_up_enrolments levantando SyncError quando preparação falha."""
        with patch.object(self.broker, "get_cohort", side_effect=Exception("erro interno")):
            with self.assertRaises(SyncError):
                self.broker.sync_up_enrolments()

        mock_http_post_json.assert_not_called()

    @patch("integrador.brokers.suap2local_suap.http_get_json")
    def test_broker_sync_down_grades_success(self, mock_http_get_json):
        """Testa sync_down_grades com sucesso."""
        mock_http_get_json.return_value = []

        result = self.broker.sync_down_grades()

        self.assertEqual(result, [])


class ManagementCommandTestCase(TestCase):
    """Testes para management commands."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

    def test_atualiza_solicitacoes_command_exists(self):
        """Testa que o comando atualiza_solicitacoes existe."""
        # Cria solicitações com diario_codigo nulo
        for i in range(3):
            sol = Solicitacao.objects.create(
                ambiente=self.ambiente, operacao=Solicitacao.Operacao.SYNC_UP_DIARIO, recebido={"diario": {"id": i}}
            )
            Solicitacao.objects.filter(pk=sol.pk).update(diario_codigo=None)

        # Chama o comando
        out = io.StringIO()
        call_command("atualiza_solicitacoes", stdout=out)

        # Verifica que comando executou e não deixou registros com diário nulo
        self.assertEqual(Solicitacao.objects.filter(diario_codigo__isnull=True).count(), 0)

    def test_atualiza_solicitacoes_updates_records(self):
        """Testa que o comando atualiza registros."""
        # Cria solicitação com diario_codigo nulo
        self.assertIsNotNone(self.ambiente)
        sol = Solicitacao.objects.create(
            ambiente=self.ambiente, operacao=Solicitacao.Operacao.SYNC_UP_DIARIO, recebido={"diario": {"id": 999}}
        )
        sol.diario_codigo = None
        sol.save()

        # Chama o comando
        call_command("atualiza_solicitacoes")

        # Recarrega solicitação
        sol.refresh_from_db()

        # Verifica que ambiente foi selecionado corretamente
        self.assertIsNotNone(self.ambiente)
        self.assertIsNotNone(sol.ambiente)
        self.assertIsNotNone(sol.ambiente)


class SecurityViewsCoverageTestCase(TestCase):
    """Testes direcionados para ampliar cobertura de security.views."""

    def setUp(self):
        self.factory = RequestFactory()

    def _add_session(self, request):
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    def test_security_helpers_success_flow(self, mock_get, mock_post):
        """Cobre _get_tokens, _get_userinfo e _save_user com dados válidos."""
        from django.conf import settings

        from security import views as security_views

        with patch.dict(
            settings.OAUTH,
            {
                "BASE_URL": "https://suap.test.com",
                "TOKEN_URL": "https://suap.test.com/o/token/",
                "USERINFO_URL": "https://suap.test.com/api/rh/eu/",
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "REDIRECT_URI": "http://suap.test.com/authenticate/",
            },
            clear=True,
        ):
            mock_post.return_value = Mock(
                status_code=200,
                text=json.dumps({"access_token": TEST_TOKEN, "scope": "read"}),
            )
            request = self.factory.get("/authenticate/?code=abc")
            tokens = security_views._get_tokens(request)

            self.assertEqual(tokens["access_token"], TEST_TOKEN)

            mock_get.return_value = Mock(
                status_code=200,
                text=json.dumps(
                    {
                        "identificacao": "user.security",
                        "primeiro_nome": "User",
                        "ultimo_nome": "Security",
                        "email_preferencial": "user.security@ifrn.edu.br",
                    }
                ),
            )
            userinfo = security_views._get_userinfo(tokens)
            user = security_views._save_user(userinfo)

            self.assertEqual(user.username, "user.security")
            self.assertEqual(user.email, "user.security@ifrn.edu.br")

    def test_get_tokens_missing_code_raises(self):
        """Cobre erro quando o código OAuth não é enviado."""
        from security import views as security_views

        request = self.factory.get("/authenticate/")

        with self.assertRaises(Exception):
            security_views._get_tokens(request)

    def test_get_tokens_missing_redirect_uri_raises(self):
        """Cobre erro quando REDIRECT_URI não está configurado."""
        from django.conf import settings

        from security import views as security_views

        request = self.factory.get("/authenticate/?code=abc")

        with patch.dict(
            settings.OAUTH,
            {
                "TOKEN_URL": "https://suap.test.com/o/token/",
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
            },
            clear=True,
        ):
            with self.assertRaises(ValueError):
                security_views._get_tokens(request)

    @patch("security.views.requests.post")
    def test_get_tokens_mismatching_redirect_uri_raises(self, mock_post):
        """Cobre erro de redirect URI incompatível retornado pelo OAuth."""
        from django.conf import settings

        from security import views as security_views

        request = self.factory.get("/authenticate/?code=abc")

        with patch.dict(
            settings.OAUTH,
            {
                "TOKEN_URL": "https://suap.test.com/o/token/",
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "REDIRECT_URI": "http://suap.test.com/authenticate/",
            },
            clear=True,
        ):
            mock_post.return_value = Mock(
                status_code=400,
                text=json.dumps({"error_description": "Mismatching redirect URI."}),
            )

            with self.assertRaises(ValueError):
                security_views._get_tokens(request)

    def test_save_user_updates_existing_user_branch(self):
        """Cobre branch de atualização de usuário existente."""
        from security import views as security_views

        User.objects.create_user(username="existing.user", first_name="Old", email="old@ifrn.edu.br")

        user = security_views._save_user(
            {
                "identificacao": "existing.user",
                "primeiro_nome": "New",
                "ultimo_nome": "User",
                "email_preferencial": "new@ifrn.edu.br",
            }
        )

        self.assertEqual(user.username, "existing.user")
        refreshed_user = User.objects.get(username="existing.user")
        self.assertEqual(refreshed_user.first_name, "New")
        self.assertEqual(refreshed_user.email, "new@ifrn.edu.br")

    def test_login_missing_redirect_uri_raises(self):
        """Cobre validação de REDIRECT_URI no login."""
        from django.conf import settings

        from security import views as security_views

        request = self.factory.get("/login/")
        self._add_session(request)

        with patch.dict(
            settings.OAUTH,
            {
                "BASE_URL": "https://suap.test.com",
                "CLIENT_ID": "test_client",
            },
            clear=True,
        ):
            with self.assertRaises(ValueError):
                security_views.login(request)

    def test_login_redirects_to_configured_oauth(self):
        """Cobre retorno de redirect no fluxo nominal de login."""
        from django.conf import settings

        from security import views as security_views

        request = self.factory.get("/login/?next=/admin/")
        self._add_session(request)

        with patch.dict(
            settings.OAUTH,
            {
                "BASE_URL": "https://suap.test.com",
                "CLIENT_ID": "test_client",
                "REDIRECT_URI": "http://suap.test.com/authenticate/",
            },
            clear=True,
        ):
            response = security_views.login(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("https://suap.test.com/o/authorize/", response.url)
        self.assertIn("client_id=test_client", response.url)

    @patch("security.views.auth.login")
    @patch("security.views._save_user")
    @patch("security.views._get_userinfo")
    @patch("security.views._get_tokens")
    def test_authenticate_success_redirects_next(
        self, mock_get_tokens, mock_get_userinfo, mock_save_user, mock_auth_login
    ):
        """Cobre fluxo de sucesso da authenticate com redirect para next."""
        from security import views as security_views

        mock_get_tokens.return_value = {"access_token": TEST_TOKEN, "scope": "read"}
        mock_get_userinfo.return_value = {"identificacao": "auth.user"}
        user = User.objects.create_user(username="auth.user")
        mock_save_user.return_value = user

        request = self.factory.get(f"/authenticate/?code={TEST_TOKEN}")
        self._add_session(request)
        request.session["next"] = "/admin/"

        response = security_views.authenticate(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/")
        mock_auth_login.assert_called_once_with(request, user, backend="django.contrib.auth.backends.ModelBackend")

    def test_authenticate_access_denied_renders_not_authorized(self):
        """Cobre retorno imediato quando OAuth responde access_denied."""
        from security import views as security_views

        request = self.factory.get("/authenticate/?error=access_denied")
        self._add_session(request)

        response = security_views.authenticate(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Você não autorizou!".encode("utf-8"), response.content)

    @patch("security.views.capture_exception")
    @patch("security.views._get_tokens")
    def test_authenticate_exception_branch_renders_error(self, mock_get_tokens, mock_capture_exception):
        """Cobre captura de exceção e renderização de erro na authenticate."""
        from security import views as security_views

        mock_get_tokens.side_effect = RuntimeError("oauth failure")

        request = self.factory.get("/authenticate/?code=abc")
        self._add_session(request)

        response = security_views.authenticate(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"oauth failure", response.content)
        mock_capture_exception.assert_called_once()

    @override_settings(LOGOUT_REDIRECT_URL="https://malicious.example/logout", LOGIN_REDIRECT_URL="/admin/")
    def test_logout_falls_back_to_login_redirect_for_untrusted_host(self):
        """Cobre branch de fallback quando LOGOUT_REDIRECT_URL não é host permitido."""
        from django.conf import settings

        from security import views as security_views

        request = self.factory.get("/logout/")
        self._add_session(request)

        with patch.dict(
            settings.OAUTH,
            {
                "BASE_URL": "https://suap.test.com",
            },
            clear=True,
        ):
            response = security_views.logout(request)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/admin/?next="))

    @override_settings(
        LOGOUT_REDIRECT_URL="https://suap.test.com/logout?origin=integrador", LOGIN_REDIRECT_URL="/admin/"
    )
    def test_logout_uses_ampersand_when_query_exists(self):
        """Cobre branch de separador '&' quando a URL já possui querystring."""
        from django.conf import settings

        from security import views as security_views

        request = self.factory.get("/logout/")
        self._add_session(request)

        with patch.dict(
            settings.OAUTH,
            {
                "BASE_URL": "https://suap.test.com",
            },
            clear=True,
        ):
            response = security_views.logout(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/logout?origin=integrador&next=", response.url)


class IntegrationTestCase(TestCase):
    """Testes de integração para fluxos completos."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

    @override_settings(SUAP_INTEGRADOR_KEY=TEST_TOKEN)
    @patch("integrador.brokers.suap2local_suap.http_post_json")
    def test_complete_sync_up_flow(self, mock_post):
        """Testa fluxo completo de sync_up_enrolments."""
        mock_post.return_value = {
            "status_code": 200,
            "text": json.dumps(
                {
                    "url": "https://moodle.integration.test/course/view.php?id=1",
                    "url_sala_coordenacao": "https://moodle.integration.test/course/view.php?id=2",
                    "roles_not_found": [],
                }
            ),
        }

        json_data = {
            "campus": {"id": 1, "sigla": "TEST", "descricao": "Campus Integration"},
            "curso": {"id": 10, "codigo": "15806", "nome": "Sistemas Operacionais Abertos"},
            "turma": {"id": 2, "codigo": "T123"},
            "componente": {"id": 5, "sigla": "COMP", "descricao": "Componente de Integração"},
            "diario": {"id": 456, "sigla": "COMP", "situacao": "Aberto"},
            "professores": [],
        }

        request = self.factory.post("/api/enviar_diarios/", data=json.dumps(json_data), content_type="application/json")
        request.META["HTTP_AUTHENTICATION"] = f"Token {TEST_TOKEN}"

        response = sync_up_enrolments(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Solicitacao.objects.count(), 1)

        solicitacao = Solicitacao.objects.first()
        self.assertEqual(solicitacao.status, Solicitacao.Status.SUCESSO)
        self.assertEqual(solicitacao.ambiente, self.ambiente)


class EdgeCasesTestCase(TestCase):
    """Testes de casos extremos."""

    def test_ambiente_with_multiple_matching_rules(self):
        """Testa ambiente com múltiplas regras correspondentes."""
        amb1 = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        sync_json = {"campus": {"sigla": "TEST"}}
        ambiente = Ambiente.objects.seleciona_ambiente(sync_json)

        # Deve retornar o primeiro que corresponder
        self.assertEqual(ambiente, amb1)

    def test_solicitacao_with_missing_json_fields(self):
        """Testa solicitação com campos JSON faltando."""
        ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        # JSON incompleto
        solicitacao = Solicitacao.objects.create(
            ambiente=ambiente, operacao=Solicitacao.Operacao.SYNC_UP_DIARIO, recebido={}
        )

        # Deve lidar com campos faltando gracefully
        self.assertEqual(solicitacao.campus_sigla, None)

    def test_ambiente_expressao_with_complex_logic(self):
        """Testa ambiente com expressão seletora complexa."""
        ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        sync_json = {"campus": {"sigla": "TEST"}, "diario": {"tipo": "regular"}}

        resultado = Ambiente.objects.seleciona_ambiente(sync_json)
        self.assertEqual(resultado, ambiente)

    def test_broker_with_url_ending_with_slash(self):
        """Testa broker com URL terminando em barra."""
        ambiente = Ambiente.objects.create(**AMBIENTE_GOOD_SGA)

        solicitacao = Solicitacao.objects.create(
            ambiente=ambiente, operacao=Solicitacao.Operacao.SYNC_UP_DIARIO, recebido={"diario": {"id": 1}}
        )

        broker = Suap2LocalSuapBroker(solicitacao)

        # base_url não deve ter barra final
        self.assertFalse(broker.solicitacao.ambiente.base_url.endswith("/"))

    def test_ambiente_manager_with_invalid_expression(self):
        """Testa manager com expressão inválida."""
        Ambiente.objects.create(**(AMBIENTE_GOOD_SGA | {"expressao_seletora": "invalid { expression"}))
