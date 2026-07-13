import requests
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

from integrador.models import Ambiente


def _check_plugin_token(base_url: str, token: str, api_path: str) -> dict | str:
    if not token or not str(token).strip():
        return "NO_TOKEN"
    try:
        response = requests.get(
            f"{base_url}{api_path}",
            headers={"Authentication": f"Token {token}"},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
        return f"FAIL ({response.status_code})"
    except Exception as e:
        return f"ERROR ({e})"


def health(request):
    try:
        connection.connect()
        connection_result = "OK"
    except Exception:
        connection_result = "FAIL"

    moodles = {}
    for ambiente in Ambiente.objects.all().order_by("ordem", "id"):
        local_suap_token = ambiente.local_suap_token
        tool_sga_token = ambiente.tool_sga_token
        moodles[ambiente.nome] = {
            "url": ambiente.url,
            "local_suap": (
                _check_plugin_token(ambiente.base_url, local_suap_token, "/local/suap/api/index.php?health")
                if ambiente.local_suap_active
                else "INACTIVE"
            ),
            "tool_sga": (
                _check_plugin_token(ambiente.base_url, tool_sga_token, "/admin/tool/sga/api/index.php?health")
                if ambiente.tool_sga_active
                else "INACTIVE"
            ),
        }

    return JsonResponse(
        {
            "Version": settings.PROJECT_VERSION,
            "Debug": "FAIL (are active)" if settings.DEBUG else "OK",
            "Database": connection_result,
            "Moodles": moodles,
        }
    )
