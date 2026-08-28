# -*- coding: utf-8 -*-
from sc4py.env import env_as_bool

# Integrador
MIDDLEWARE = [
    "integrador.middleware.DisableCSRFForAPIMiddleware",  # Deve vir ANTES do CsrfViewMiddleware
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

if not env_as_bool("DJANGO_DEBUG", True):
    MIDDLEWARE.insert(4, "whitenoise.middleware.WhiteNoiseMiddleware")
