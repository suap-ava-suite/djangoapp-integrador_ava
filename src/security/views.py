import json
import logging
import urllib

import requests
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from sentry_sdk import capture_exception

logger = logging.getLogger(__name__)


REQUEST_TIMEOUT_SECONDS = 10


def _get_tokens(request):
    OAUTH = settings.OAUTH

    if "code" not in request.GET:
        raise Exception(_("O SUAP não informou o código de autenticação."))

    redirect_uri = OAUTH.get("REDIRECT_URI")
    if not redirect_uri:
        raise ValueError("Configure OAUTH['REDIRECT_URI'] para autenticação OAuth.")

    response = requests.post(
        OAUTH.get("TOKEN_URL", ""),
        data={
            "grant_type": "authorization_code",
            "code": request.GET.get("code"),
            "redirect_uri": redirect_uri,
            "client_id": OAUTH["CLIENT_ID"],
            "client_secret": OAUTH["CLIENT_SECRET"],
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    logger.info("OAuth endpoint response status %s", response.status_code)
    if not response.ok:
        raise ValueError(f"Falha ao obter token no OAuth (status {response.status_code}): {response.text[:200]}")
    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ValueError("Resposta inválida do endpoint de token: conteúdo não é JSON válido.") from exc
    if data.get("error_description") == "Mismatching redirect URI.":
        raise ValueError(
            "O administrador do sistema configurou errado o 'Redirect uris' no SUAP-Login ou no OAUTH_REDIRECT_URI."
        )
    return data


def _get_userinfo(request_data):
    OAUTH = settings.OAUTH
    query = urllib.parse.urlencode({"scope": request_data.get("scope", "")})
    response = requests.get(
        f"{OAUTH['USERINFO_URL']}?{query}",
        headers={
            "Authorization": f"Bearer {request_data.get('access_token')}",
            "x-api-key": OAUTH["CLIENT_SECRET"],
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    logger.info("_get_userinfo response received with status %s", response.status_code)
    if not response.ok:
        raise ValueError(f"Falha ao consultar userinfo no OAuth (status {response.status_code}): {response.text[:200]}")
    try:
        return json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ValueError("Resposta inválida do endpoint userinfo: conteúdo não é JSON válido.") from exc


def _save_user(userinfo):
    username = userinfo.get("identificacao")
    if not username:
        raise ValueError("Resposta do OAuth inválida: campo obrigatório 'identificacao' ausente.")
    user = User.objects.filter(username=username).first()

    email_preferencial = userinfo.get("email_preferencial")
    email = email_preferencial or (f"{username}@ifrn.edu.br" if username else "")

    defaults = {
        "first_name": userinfo.get("primeiro_nome"),
        "last_name": userinfo.get("ultimo_nome"),
        "email": email,
    }

    if user is None:
        is_superuser = User.objects.count() == 0
        user = User.objects.create(
            username=username,
            is_superuser=is_superuser,
            is_staff=is_superuser,
            **defaults,
        )
    else:
        user.first_name = defaults["first_name"]
        user.last_name = defaults["last_name"]
        user.email = defaults["email"]
        user.save(update_fields=["first_name", "last_name", "email"])
    return user


def login(request: HttpRequest) -> HttpResponse:
    OAUTH = settings.OAUTH
    request.session["next"] = request.GET.get("next", "/")

    redirect_uri = OAUTH.get("REDIRECT_URI")
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": OAUTH["CLIENT_ID"],
            "redirect_uri": redirect_uri,
        }
    )
    if not redirect_uri:
        raise ValueError("Configure OAUTH['REDIRECT_URI'] para autenticação OAuth.")
    suap_url = f"{OAUTH['BASE_URL']}/o/authorize/?{params}"
    return redirect(suap_url)  # nosemgrep: python.django.security.injection.open-redirect.open-redirect


def authenticate(request: HttpRequest) -> HttpResponse:
    if request.GET.get("error") == "access_denied":
        return render(request, "security/not_authorized.html")

    try:
        request_data = _get_tokens(request)
        userinfo = _get_userinfo(request_data)
        user = _save_user(userinfo)
        auth.login(request, user)
        next_url = request.session.pop("next", "/")
        allowed_hosts = {request.get_host(), urllib.parse.urlsplit(settings.OAUTH["BASE_URL"]).netloc}
        require_https = request.is_secure()
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts=allowed_hosts, require_https=require_https):
            next_url = "/"
        return redirect(next_url)
    except Exception as e:
        capture_exception(e)
        return render(request, "security/authorization_error.html", context={"error_cause": str(e)})


def logout(request: HttpRequest) -> HttpResponse:
    logout_token = request.session.get("logout_token", "")
    logout_url = settings.LOGOUT_REDIRECT_URL
    allowed_hosts = {request.get_host(), urllib.parse.urlsplit(settings.OAUTH["BASE_URL"]).netloc}
    require_https = request.is_secure()
    if not url_has_allowed_host_and_scheme(logout_url, allowed_hosts=allowed_hosts, require_https=require_https):
        logout_url = settings.LOGIN_REDIRECT_URL

    auth.logout(request)

    encoded_logout_token = urllib.parse.quote_plus(logout_token)
    next_url = urllib.parse.quote_plus(settings.LOGIN_REDIRECT_URL)
    separator = "&" if urllib.parse.urlsplit(logout_url).query else "?"
    return redirect(f"{logout_url}{separator}token={encoded_logout_token}&next={next_url}")
