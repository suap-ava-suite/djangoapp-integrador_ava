from pathlib import Path

from django.utils.translation import gettext_lazy as _
from sc4py.env import env, env_as_bool

# https://docs.djangoproject.com/en/5.0/topics/i18n/

BASE_DIR = Path(__file__).resolve().parent.parent

LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", "pt-br")
TIME_ZONE = env("DJANGO_TIME_ZONE", "America/Fortaleza")
USE_I18N = env_as_bool("DJANGO_USE_I18N", True)
USE_L10N = env_as_bool("DJANGO_USE_L10N", True)
USE_TZ = env_as_bool("DJANGO_USE_TZ", True)
USE_THOUSAND_SEPARATOR = env_as_bool("DJANGO_USE_THOUSAND_SEPARATOR", True)

LANGUAGES = [
    ("pt-br", _("Portuguese")),
    ("en", _("English")),
    ("es", _("Spanish")),
    ("fr", _("French")),
    ("zh-hans", _("Simplified Chinese")),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]
