# -*- coding: utf-8 -*-
"""
Views customizadas para tratamento de erros.
"""

import logging

import sentry_sdk
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token

logger = logging.getLogger(__name__)


@requires_csrf_token
def csrf_failure(request, reason=""):
    """
    View customizada para tratar falhas de CSRF.

    Esta view é chamada quando uma requisição falha na verificação CSRF.
    Ela captura o erro e envia para o Sentry para monitoramento, além de
    retornar uma resposta adequada ao cliente.

    Args:
        request: O objeto HttpRequest que falhou na verificação CSRF
        reason: A razão da falha (fornecida pelo Django)

    Returns:
        JsonResponse ou HttpResponse com status 403
    """
    meta = request.META
    content_type = meta.get("CONTENT_TYPE", "unknown").lower()
    accept_header = meta.get("HTTP_ACCEPT", "unknown").lower()
    is_json_request = (
        request.path.startswith("/api/") or "application/json" in content_type or "application/json" in accept_header
    )

    context = {
        "error": "CSRF verification failed",
        "reason": reason,
        "path": request.path,
        "method": request.method,
        "referer": meta.get("HTTP_REFERER", "Unknown"),
        "content_type": content_type,
        "accept_header": accept_header,
        "is_json_request": is_json_request,
        "user_agent": meta.get("HTTP_USER_AGENT", "Unknown"),
    }

    # Log local para warning
    logger.warning(f"CSRF verification failed: {reason}", extra={"context": context})

    # Envia o erro para o Sentry com contexto adicional
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("error_type", "csrf_failure")
        scope.set_tag("csrf_reason", reason)
        scope.set_context("csrf_failure", context)
        sentry_sdk.capture_message(f"CSRF verification failed: {reason}", level="warning")

    if is_json_request:
        return JsonResponse(context, status=403)

    try:
        return render(request, "403_csrf.html", context, status=403)
    except Exception:
        try:
            return render(request, "403.html", context, status=403)
        except Exception:
            from django.http import HttpResponse

            return HttpResponse("<h1>Forbidden (403)</h1><p>CSRF verification failed.</p>", status=403)
