# -*- coding: utf-8 -*-
import importlib.util
import logging
import sys

from sc4py.env import env_as_bool, env_as_list

from .apps import INSTALLED_APPS
from .middlewares import MIDDLEWARE

logger = logging.getLogger(__name__)

DEBUG = env_as_bool("DJANGO_DEBUG", True)
DEBUG_URLPATTERNS = []

# Check if running tests
IS_RUNNING_TESTS = "test" in sys.argv

if DEBUG and not IS_RUNNING_TESTS:
    try:
        if importlib.util.find_spec("debug_toolbar") is not None:
            MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
            INSTALLED_APPS += env_as_list("DEV_APPS", ["debug_toolbar"])
            INTERNAL_IPS = ["127.0.0.1", "localhost"]
            DEBUG_TOOLBAR_CONFIG = {
                "SHOW_TOOLBAR_CALLBACK": lambda request: True,
                "IS_RUNNING_TESTS": False,
                "DISABLE_PANELS": {
                    "debug_toolbar.panels.history.HistoryPanel",
                    "debug_toolbar.panels.versions.VersionsPanel",
                    "debug_toolbar.panels.redirects.RedirectsPanel",
                    "debug_toolbar.panels.profiling.ProfilingPanel",
                },
                "SHOW_COLLAPSED": True,
            }

        # https://github.com/unbit/django-uwsgi
        # https://github.com/giginet/django-debug-toolbar-vcs-info
        # https://github.com/orf/django-debug-toolbar-template-timings
        # https://github.com/orf/django-debug-toolbar-template-timings
        # https://github.com/node13h/django-debug-toolbar-template-profiler
        # https://github.com/djsutho/django-debug-toolbar-request-history
        # https://github.com/mikekeda/django-debug-toolbar-line-profiler
        # https://github.com/rkern/line_profiler
        # https://gitlab.com/living180/pyflame
        # https://django-debug-toolbar.readthedocs.io/en/latest/panels.html#uwsgi-stats
    except ModuleNotFoundError:
        logger.info("Não foi possível carregar o debug_toolbar")
