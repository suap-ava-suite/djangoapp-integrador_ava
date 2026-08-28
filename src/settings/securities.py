# -*- coding: utf-8 -*-
from sc4py.env import env, env_as_bool, env_as_list

SUAP_INTEGRADOR_KEY = env("SUAP_INTEGRADOR_KEY")
SUAP_BASE_URL = env("SUAP_BASE_URL", "https://suap.ifrn.edu.br")

SECRET_KEY = env("DJANGO_SECRET_KEY", "changeme")
LOGIN_URL = env("DJANGO_LOGIN_URL", "/auth/suap/login/")
LOGIN_REDIRECT_URL = env("DJANGO_LOGIN_REDIRECT_URL", "/")
LOGOUT_REDIRECT_URL = env("DJANGO_LOGOUT_REDIRECT_URL", "/auth/suap/logout/")
GO_TO_HTTPS = env_as_bool("GO_TO_HTTPS", False)
AUTHENTICATION_BACKENDS = env_as_list(
    "AUTHENTICATION_BACKENDS",
    [
        "django_suap_auth.profile.backends.SuapProfileAuthBackend",
        "django.contrib.auth.backends.ModelBackend",
    ],
)
AUTH_PASSWORD_VALIDATORS = env_as_list("DJANGO_AUTH_PASSWORD_VALIDATORS", [])

oauth_base_url = env("OAUTH_BASE_URL", "https://suap.ifrn.edu.br")
SUAP_AUTH = {
    "CLIENT_ID": env("OAUTH_CLIENT_ID", ""),
    "CLIENT_SECRET": env("OAUTH_CLIENT_SECRET", ""),
    "REDIRECT_URI": env("OAUTH_REDIRECT_URI", ""),
    "BASE_URL": oauth_base_url,
    "SCOPES": ["identificacao", "email"],
    "USER_LOOKUP_FIELD": "username",
    "USER_ATTR_MAP": {
        "username": "identificacao",
        "email": "email_preferencial",
        ("first_name", "last_name"): "nome_registro",
    },
    "USER_DEFAULTS": {"is_active": True},
    "FIRST_USER_DEFAULTS": {"is_staff": True, "is_superuser": True},
    "BACKEND": "django_suap_auth.profile.backends.SuapProfileAuthBackend",
    "USER_JSON_FIELD": "suap_data",
    "USER_INFO_ENDPOINTS": [
        # RH / Servidor
        "/api/rh/eu/",
        "/api/rh/meus-dados/",
        {
            "endpoint": "/api/rh/meus-vinculos/",
            "namespace": "meus_vinculos",
            "extract_list": "results",
        },
        {
            "endpoint": "/api/rh/servidores_funcao_ativa/?matricula={identificacao}",
            "namespace": "servidores_funcao_ativa",
            "extract_list": "results",
        },
        {
            "endpoint": "/api/rh/meu-historico-funcional/",
            "namespace": "meu_historico_funcional",
            "extract_list": "results",
        },
        # Ensino / Aluno
        {
            "endpoint": "/api/ensino/meus-dados-aluno/",
            "namespace": "meus_dados_aluno",
        },
        {
            "endpoint": "/api/ensino/requisitos-conclusao/",
            "namespace": "requisitos_conclusao",
        },
        {
            "endpoint": "/api/ensino/periodos/",
            "namespace": "periodos",
            "extract_list": "results",
        },
        {
            "endpoint": "/api/ensino/diarios/{semestre}/",
            "for_each": "periodos",
            "namespace": "diarios",
            "extract_list": "results",
        },
        {
            "endpoint": "/api/ensino/meus-periodos-letivos/",
            "namespace": "meus_periodos_letivos",
            "extract_list": "results",
        },
        {
            "endpoint": "/api/ensino/meu-boletim/{ano_letivo}/{periodo_letivo}/",
            "for_each": "meus_periodos_letivos",
            "namespace": "boletins",
            "extract_list": "results",
        },
    ],
}
