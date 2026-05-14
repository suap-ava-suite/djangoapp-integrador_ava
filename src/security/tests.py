"""
Testes unitários para a app security.

Este módulo contém testes para:
- login view: Autenticação OAuth com SUAP
- authenticate view: Callback OAuth e criação/atualização de usuários
- logout view: Desconexão do sistema
- Fluxos de autenticação
- Tratamento de erros
"""

import json
import uuid
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings

from security.apps import SecurityConfig
from security.views import authenticate, login, logout

TEST_TOKEN_VALUE = f"test-{uuid.uuid4().hex}"
TEST_OAUTH_OK = {
    "BASE_URL": "https://suap.test.com",
    "TOKEN_URL": "https://suap.test.com/o/token/",
    "USERINFO_URL": "https://suap.test.com/api/rh/eu/",
    "CLIENT_ID": TEST_TOKEN_VALUE,
    "CLIENT_SECRET": TEST_TOKEN_VALUE,
    "REDIRECT_URI": "http://suap.test.com/authenticate/",
}


class SecurityAppConfigTestCase(TestCase):
    """Testes para a configuração da app security."""

    def test_app_config_name(self):
        """Testa se o nome da app está correto."""
        self.assertEqual(SecurityConfig.name, "security")

    def test_app_config_verbose_name(self):
        """Testa verbose_name da app."""
        self.assertEqual(SecurityConfig.verbose_name, "Segurança")

    def test_app_config_icon(self):
        """Testa se o ícone está definido."""
        self.assertEqual(SecurityConfig.icon, "fa fa-user")

    def test_app_config_default_auto_field(self):
        """Testa se default_auto_field está configurado."""
        self.assertEqual(SecurityConfig.default_auto_field, "django.db.models.BigAutoField")


class SessionRequestTestCase(TestCase):
    """Classe base para testes que precisam de sessão na requisição."""

    def add_session_to_request(self, request):
        """Adiciona sessão à requisição."""
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()


class LoginViewTestCase(SessionRequestTestCase):
    """Testes para a view de login."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_login_redirects_to_oauth(self):
        """Testa se login redireciona para OAuth."""
        request = self.factory.get("/login/")
        self.add_session_to_request(request)

        response = login(request)

        # Verifica redirecionamento
        self.assertEqual(response.status_code, 302)

        # Verifica URL de redirecionamento
        self.assertIn("suap.test.com", response.url)
        self.assertIn("authorize", response.url)
        self.assertIn(TEST_TOKEN_VALUE, response.url)

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_login_saves_next_parameter_in_session(self):
        """Testa se login salva parâmetro next na sessão."""
        request = self.factory.get("/login/?next=/admin/")
        self.add_session_to_request(request)

        login(request)

        # Verifica se 'next' foi salvo na sessão
        self.assertEqual(request.session["next"], "/admin/")

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_login_default_next_when_not_provided(self):
        """Testa valor padrão de next quando não fornecido."""
        request = self.factory.get("/login/")
        self.add_session_to_request(request)

        login(request)

        # Deve usar "/" como padrão
        self.assertEqual(request.session["next"], "/")

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_login_constructs_correct_redirect_uri(self):
        """Testa se a URI de redirecionamento está correta."""
        request = self.factory.get("/login/")
        self.add_session_to_request(request)
        response = login(request)
        self.assertIn("redirect_uri=http", response.url)


class AuthenticateViewTestCase(SessionRequestTestCase):
    """Testes para a view de autenticação."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_handles_access_denied(self):
        """Testa tratamento de erro access_denied."""
        request = self.factory.get("/authenticate/?error=access_denied")
        self.add_session_to_request(request)

        response = authenticate(request)

        # Verifica que renderiza template de não autorizado
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"autorizou o compartilhamento de dados", response.content)

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_successful_flow(self, mock_get, mock_post):
        """Testa fluxo de autenticação bem-sucedido."""
        # Mock do token response
        mock_post.return_value = Mock(
            status_code=200, text=json.dumps({"access_token": "test_token", "scope": "test_scope"})
        )

        # Mock do userinfo response
        mock_get.return_value = Mock(
            status_code=200,
            text=json.dumps(
                {
                    "identificacao": "testuser",
                    "primeiro_nome": "Test",
                    "ultimo_nome": "User",
                    "email_preferencial": "test@example.com",
                }
            ),
        )

        request = self.factory.get("/authenticate/?code=test_code")
        self.add_session_to_request(request)
        request.session["next"] = "/admin/"

        response = authenticate(request)

        # Verifica redirecionamento
        self.assertEqual(response.status_code, 302)

        # Verifica se o usuário foi criado
        user = User.objects.get(username="testuser")
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "User")
        self.assertEqual(user.email, "test@example.com")

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_creates_first_user_as_superuser(self, mock_get, mock_post):
        """Testa se o primeiro usuário é criado como superuser."""
        # Mock das respostas
        mock_post.return_value = Mock(
            status_code=200, text=json.dumps({"access_token": "test_token", "scope": "test_scope"})
        )
        mock_get.return_value = Mock(
            text=json.dumps(
                {
                    "identificacao": "firstuser",
                    "primeiro_nome": "First",
                    "ultimo_nome": "User",
                    "email_preferencial": "first@example.com",
                }
            )
        )
        # Garante que não há usuários
        User.objects.all().delete()

        request = self.factory.get("/authenticate/?code=test_code")
        self.add_session_to_request(request)
        request.session["next"] = "/"

        response = authenticate(request)
        print(response)

        # Verifica que primeiro usuário é superuser
        user = User.objects.get(username="firstuser")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_updates_existing_user(self, mock_get, mock_post):
        """Testa atualização de usuário existente."""
        # Cria usuário existente
        User.objects.create_user(username="existinguser", first_name="Old", last_name="Name", email="old@example.com")

        # Mock das respostas
        mock_post.return_value = Mock(
            status_code=200, text=json.dumps({"access_token": "test_token", "scope": "test_scope"})
        )

        mock_get.return_value = Mock(
            text=json.dumps(
                {
                    "identificacao": "existinguser",
                    "primeiro_nome": "New",
                    "ultimo_nome": "Name",
                    "email_preferencial": "new@example.com",
                }
            )
        )

        request = self.factory.get("/authenticate/?code=test_code")
        self.add_session_to_request(request)
        request.session["next"] = "/"

        authenticate(request)

        # Verifica que usuário foi atualizado
        user = User.objects.get(username="existinguser")
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.email, "new@example.com")

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_without_code_parameter(self):
        """Testa authenticate sem parâmetro code."""
        request = self.factory.get("/authenticate/")
        self.add_session_to_request(request)

        response = authenticate(request)

        # Deve renderizar página de erro
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"authorization_error", response.content)

    @patch("security.views.requests.post")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_handles_token_error(self, mock_post):
        """Testa tratamento de erro ao obter token."""
        # Mock de erro no token
        mock_post.side_effect = Exception("Token request failed")

        request = self.factory.get("/authenticate/?code=test_code")
        self.add_session_to_request(request)

        response = authenticate(request)
        self.assertEqual(response.status_code, 200)

        # Deve renderizar página de erro
        self.assertIn(b"authorization_error", response.content)

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_uses_default_email_when_not_provided(self, mock_get, mock_post):
        """Testa uso de email padrão quando não fornecido."""
        mock_post.return_value = Mock(
            status_code=200, text=json.dumps({"access_token": "test_token", "scope": "test_scope"})
        )
        # Userinfo sem email_preferencial
        mock_get.return_value = Mock(
            text=json.dumps({"identificacao": "noemail", "primeiro_nome": "No", "ultimo_nome": "Email"})
        )

        request = self.factory.get("/authenticate/?code=test_code")
        self.add_session_to_request(request)
        request.session["next"] = "/"

        response = authenticate(request)
        self.assertEqual(response.status_code, 302)

        # Verifica email padrão
        user = User.objects.get(username="noemail")
        self.assertEqual(user.email, "noemail@ifrn.edu.br")

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    @patch("security.views.capture_exception")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_handles_generic_exception(self, mock_capture, mock_get, mock_post):
        """Testa tratamento de exceção genérica."""
        mock_post.side_effect = Exception("Network error")

        request = self.factory.get("/authenticate/?code=test_code")
        self.add_session_to_request(request)

        response = authenticate(request)

        # Deve renderizar página de erro
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"erro ao tentar autenticar usando o SUAP", response.content)
        mock_capture.assert_called_once()

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_with_email_preferencial(self, mock_get, mock_post):
        """Testa que email_preferencial tem prioridade."""
        mock_post.return_value = Mock(text=json.dumps({"access_token": "test_token", "scope": "test_scope"}))

        mock_get.return_value = Mock(
            text=json.dumps(
                {
                    "identificacao": "testuser",
                    "primeiro_nome": "Test",
                    "ultimo_nome": "User",
                    "email_preferencial": "preferred@example.com",
                }
            )
        )

        request = self.factory.get("/authenticate/?code=test_code")
        self.add_session_to_request(request)
        request.session["next"] = "/"

        response = authenticate(request)

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username="testuser")
        self.assertEqual(user.email, "preferred@example.com")


class LogoutViewTestCase(TestCase):
    """Testes para a view de logout."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser")
        self.user.set_unusable_password()
        self.user.save()

    def add_session_to_request(self, request):
        """Adiciona sessão à requisição."""
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()

    @override_settings(
        LOGOUT_REDIRECT_URL="https://suap.test.com/logout",
        LOGIN_REDIRECT_URL="/admin/",
        OAUTH=TEST_OAUTH_OK,
    )
    def test_logout_redirects_to_suap(self):
        """Testa se logout redireciona para SUAP."""
        request = self.factory.get("/logout/")
        request.user = self.user
        self.add_session_to_request(request)

        response = logout(request)

        # Verifica redirecionamento
        self.assertEqual(response.status_code, 302)
        self.assertIn("suap.test.com/logout", response.url)

    @override_settings(
        LOGOUT_REDIRECT_URL="https://suap.test.com/logout",
        LOGIN_REDIRECT_URL="/admin/",
        OAUTH=TEST_OAUTH_OK,
    )
    def test_logout_includes_next_parameter(self):
        """Testa se logout inclui parâmetro next."""
        request = self.factory.get("/logout/")
        request.user = self.user
        self.add_session_to_request(request)

        response = logout(request)

        # Verifica que URL contém next parameter
        self.assertIn("next=", response.url)
        self.assertIn("%2Fadmin%2F", response.url)  # URL encoded /admin/

    @override_settings(
        LOGOUT_REDIRECT_URL="https://suap.test.com/logout",
        LOGIN_REDIRECT_URL="/admin/",
        OAUTH=TEST_OAUTH_OK,
    )
    def test_logout_with_logout_token_still_redirects(self):
        """Testa se logout com token em sessão mantém redirecionamento esperado."""
        request = self.factory.get("/logout/")
        request.user = self.user
        self.add_session_to_request(request)
        request.session["logout_token"] = TEST_TOKEN_VALUE

        response = logout(request)

        # Verifica redirecionamento com parâmetro next
        self.assertEqual(response.status_code, 302)
        self.assertIn("next=", response.url)

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_logout_with_empty_logout_token(self):
        """Testa logout sem logout_token na sessão."""
        request = self.factory.get("/logout/")
        request.user = self.user
        self.add_session_to_request(request)

        response = logout(request)

        # Deve funcionar sem token
        self.assertEqual(response.status_code, 302)
        self.assertIn("next=", response.url)


class SecurityURLsTestCase(TestCase):
    """Testes para URLs da app security."""

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_login_url_is_accessible(self):
        """Testa se a URL /login/ é acessível."""
        response = self.client.get("/login/")

        # Deve redirecionar para OAuth
        self.assertEqual(response.status_code, 302)

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_url_is_accessible(self):
        """Testa se a URL /authenticate/ é acessível."""
        response = self.client.get("/authenticate/")

        # Deve retornar resposta (erro ou página)
        self.assertIn(response.status_code, [200, 302])

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_logout_url_is_accessible(self):
        """Testa se a URL /logout/ é acessível."""
        response = self.client.get("/logout/")

        # Deve redirecionar
        self.assertEqual(response.status_code, 302)


class EdgeCasesTestCase(TestCase):
    """Testes de casos extremos."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()

    def add_session_to_request(self, request):
        """Adiciona sessão à requisição."""
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()

    @patch("security.views.requests.post")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_with_mismatching_redirect_uri_error(self, mock_post):
        """Testa erro de redirect URI não correspondente."""
        token_error_payload = {
            "error": "invalid_request",
            "error_description": "Mismatching redirect URI.",
        }
        mock_post.return_value = Mock(
            status_code=400,
            text=json.dumps(token_error_payload),
            json=Mock(return_value=token_error_payload),
        )

        request = self.factory.get(f"/authenticate/?code={TEST_OAUTH_OK}")
        self.add_session_to_request(request)

        response = authenticate(request)
        self.assertEqual(response.status_code, 200)

        self.assertIn(b"no OAUTH_REDIRECT_URI", response.content)

    @patch("security.views.requests.post")
    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_authenticate_with_username_at_max_length(self, mock_get, mock_post):
        """Testa autenticação com username no limite exato de tamanho."""
        mock_post.return_value = Mock(text=json.dumps({"access_token": TEST_TOKEN_VALUE, "scope": "test_scope"}))
        username_max_length = User._meta.get_field("username").max_length
        exact_username = "a" * username_max_length
        mock_get.return_value = Mock(
            text=json.dumps({"identificacao": exact_username, "primeiro_nome": "Edge", "ultimo_nome": "User"})
        )
        request = self.factory.get(f"/authenticate/?code={TEST_TOKEN_VALUE}")
        self.add_session_to_request(request)
        request.session["next"] = "/"
        response = authenticate(request)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username=exact_username).exists())

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_login_with_special_characters_in_next(self):
        """Testa login com caracteres especiais em next."""
        request = self.factory.get("/login/?next=/admin/test?id=123&name=test")
        self.add_session_to_request(request)

        login(request)

        # Deve salvar corretamente
        self.assertIn("next", request.session)

    @override_settings(
        LOGOUT_REDIRECT_URL="https://suap.test.com/logout",
        LOGIN_REDIRECT_URL="/admin/",
        OAUTH=TEST_OAUTH_OK,
    )
    def test_logout_without_authenticated_user(self):
        """Testa logout sem usuário autenticado."""
        request = self.factory.get("/logout/")
        request.user = AnonymousUser()
        self.add_session_to_request(request)

        response = logout(request)

        # Deve funcionar mesmo sem usuário
        self.assertEqual(response.status_code, 302)


class GetTokensTestCase(TestCase):
    """Testes para a função _get_tokens."""

    def setUp(self):
        """Configura o ambiente de teste."""
        self.factory = RequestFactory()

    @patch("security.views.requests.post")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_get_tokens_success(self, mock_post):
        """Testa obtenção bem-sucedida de tokens."""
        from security.views import _get_tokens

        mock_post.return_value = Mock(
            text=json.dumps(
                {
                    "access_token": TEST_OAUTH_OK,
                    "refresh_token": TEST_OAUTH_OK,
                    "token_type": "Bearer",
                    "scope": "read write",
                }
            )
        )

        request = self.factory.get(f"/authenticate/?code={TEST_OAUTH_OK}")
        request.META["HTTP_HOST"] = "localhost:8000"

        tokens = _get_tokens(request)

        self.assertEqual(tokens["access_token"], TEST_OAUTH_OK)
        self.assertEqual(tokens["token_type"], "Bearer")
        mock_post.assert_called_once()

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_get_tokens_missing_code_raises(self):
        """Cobre erro quando o código OAuth não é enviado."""
        from security import views as security_views

        request = self.factory.get("/authenticate/")

        with self.assertRaises(Exception):
            security_views._get_tokens(request)

    @patch("security.views.requests.post")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_get_tokens_mismatching_redirect_uri(self, mock_post):
        """Testa erro quando redirect URI não corresponde."""
        from security.views import _get_tokens

        mock_post.return_value = Mock(text=json.dumps({"error_description": "Mismatching redirect URI."}))

        request = self.factory.get("/authenticate/?code=test_code")
        request.META["HTTP_HOST"] = "localhost:8000"

        with self.assertRaises(ValueError) as context:
            _get_tokens(request)

        self.assertIn("Redirect", str(context.exception))


class GetUserinfoTestCase(TestCase):
    """Testes para a função _get_userinfo."""

    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_get_userinfo_success(self, mock_get):
        """Testa obtenção bem-sucedida de informações do usuário."""
        from security.views import _get_userinfo

        mock_get.return_value = Mock(
            text=json.dumps(
                {
                    "identificacao": "testuser123",
                    "primeiro_nome": "Test",
                    "ultimo_nome": "User",
                    "email_preferencial": "test@example.com",
                }
            )
        )

        request_data = {"access_token": "valid_access_token", "scope": "read"}

        userinfo = _get_userinfo(request_data)

        self.assertEqual(userinfo["identificacao"], "testuser123")
        self.assertEqual(userinfo["email_preferencial"], "test@example.com")
        mock_get.assert_called_once()

    @patch("security.views.requests.get")
    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_get_userinfo_with_all_fields(self, mock_get):
        """Testa obtenção de userinfo com todos os campos."""
        from security.views import _get_userinfo

        mock_get.return_value = Mock(
            text=json.dumps(
                {
                    "identificacao": "fulluser",
                    "primeiro_nome": "Full",
                    "ultimo_nome": "Name User",
                    "email_preferencial": "full@example.com",
                }
            )
        )

        request_data = {"access_token": "token", "scope": "read write"}

        userinfo = _get_userinfo(request_data)

        self.assertIn("identificacao", userinfo)
        self.assertIn("primeiro_nome", userinfo)
        self.assertIn("ultimo_nome", userinfo)


class SaveUserTestCase(TestCase):
    """Testes para a função _save_user."""

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_save_user_creates_new_user(self):
        """Testa criação de novo usuário."""
        from security.views import _save_user

        # Garante que há pelo menos um usuário (para não ser superuser)
        User.objects.create_user(username="existing")

        userinfo = {
            "identificacao": "newuser",
            "primeiro_nome": "New",
            "ultimo_nome": "User",
            "email_preferencial": "new@example.com",
        }

        user = _save_user(userinfo)

        self.assertIsNotNone(user.pk)
        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "User")
        self.assertEqual(user.email, "new@example.com")
        self.assertFalse(user.is_superuser)

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_save_user_first_user_is_superuser(self):
        """Testa se primeiro usuário é superuser."""
        from security.views import _save_user

        # Remove todos os usuários
        User.objects.all().delete()

        userinfo = {
            "identificacao": "firstuser",
            "primeiro_nome": "First",
            "ultimo_nome": "User",
            "email_preferencial": "first@example.com",
        }

        user = _save_user(userinfo)

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_save_user_updates_existing_user(self):
        """Testa atualização de usuário existente."""
        from security.views import _save_user

        # Cria usuário existente
        User.objects.create_user(username="existinguser", first_name="Old", last_name="Name", email="old@example.com")

        userinfo = {
            "identificacao": "existinguser",
            "primeiro_nome": "Updated",
            "ultimo_nome": "NewName",
            "email_preferencial": "updated@example.com",
        }

        _save_user(userinfo)

        # Recarrega do banco
        user = User.objects.get(username="existinguser")
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.last_name, "NewName")
        self.assertEqual(user.email, "updated@example.com")

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_save_user_uses_default_email(self):
        """Testa uso de email padrão quando preferencial não existe."""
        from security.views import _save_user

        User.objects.create_user(username="existing")  # Para não ser superuser

        userinfo = {"identificacao": "noemailuser", "primeiro_nome": "No", "ultimo_nome": "Email"}

        user = _save_user(userinfo)

        self.assertEqual(user.email, "noemailuser@ifrn.edu.br")

    @override_settings(OAUTH=TEST_OAUTH_OK)
    def test_save_user_with_empty_email_preferencial(self):
        """Testa quando email_preferencial está vazio."""
        from security.views import _save_user

        User.objects.create_user(username="existing")

        userinfo = {
            "identificacao": "emptyemail",
            "primeiro_nome": "Empty",
            "ultimo_nome": "Email",
            "email_preferencial": "",
        }

        user = _save_user(userinfo)

        self.assertEqual(user.email, "emptyemail@ifrn.edu.br")
