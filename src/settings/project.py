import datetime

from sc4py.env import env, env_as_bool

SHOW_SUPPORT_FORM = env_as_bool("SHOW_SUPPORT_FORM", True)
SHOW_SUPPORT_CHAT = env_as_bool("SHOW_SUPPORT_CHAT", True)

PROJECT_COMPANY = env("PROJECT_COMPANY", "IFRN")
PROJECT_TITLE = env("PROJECT_TITLE", "Integrador AVA")
PROJECT_SUBTITLE = env("PROJECT_SUBTITLE", "Sistema de integração de Ambientes Virtuais de Aprendizagem")
PROJECT_VERSION = env("PROJECT_VERSION", "1.1.056")
PROJECT_LAST_STARTUP = int(datetime.datetime.timestamp(datetime.datetime.now()) * 1000)
PROJECT_COPYRIGHT = env("PROJECT_COPYRIGHT", "🄯2025 IFRN")
PROJECT_LICENSE = env("PROJECT_LICENSE", "Licença MIT")
PROJECT_LICENSE_URL = env("PROJECT_LICENSE_URL", "https://opensource.org/license/mit")
