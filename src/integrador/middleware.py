# -*- coding: utf-8 -*-
import logging
import re

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class DisableCSRFForAPIMiddleware(MiddlewareMixin):
    """
    Middleware to disable CSRF checking for specific API endpoints.
    """

    # Padrões de URL que devem ser isentos de CSRF
    CSRF_EXEMPT_URLS = [
        re.compile(r"^__debug__/"),  # Django Debug Toolbar
        re.compile(r"^api/"),  # APIs
    ]

    def process_request(self, request):
        """
        Marca a requisição como isenta de CSRF se a URL corresponder aos padrões.
        """
        path = request.path_info.lstrip("/")

        for pattern in self.CSRF_EXEMPT_URLS:
            if pattern.match(path):
                setattr(request, "_dont_enforce_csrf_checks", True)
                break

        return None
