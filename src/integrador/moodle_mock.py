import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# local_suap plugin — serviços conhecidos e implementados no mock
# ---------------------------------------------------------------------------
_LOCAL_SUAP_KNOWN_SERVICES = frozenset(
    {
        "get_diarios",
        "get_atualizacoes_counts",
        "set_favourite_course",
        "set_visible_course",
        "set_user_preference",
        "sync_user_preference",
        "sync_up_enrolments",
        "sync_down_grades",
    }
)

_LOCAL_SUAP_IMPLEMENTED_SERVICES = frozenset(
    {
        "sync_up_enrolments",
        "sync_down_grades",
    }
)

# ---------------------------------------------------------------------------
# tool_sga plugin — serviços conhecidos (broker ainda não implementado)
# ---------------------------------------------------------------------------


class MockHTTPResponse:
    def __init__(self, payload: object, status_code: int = 200, headers: dict | None = None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.reason = HTTPStatus(status_code).phrase
        self.headers = headers or {"Content-Type": "application/json"}
        self.content = json.dumps(payload).encode("utf-8")

    @classmethod
    def html_error(cls, status_code: int = 500, message: str | None = None) -> "MockHTTPResponse":
        """Simula resposta HTML do Moodle, como ocorre em erros fatais do PHP."""
        phrase = message or HTTPStatus(status_code).phrase
        html = f"<!DOCTYPE html><html><body><h1>{phrase}</h1></body></html>".encode("utf-8")
        obj = object.__new__(cls)
        obj.status_code = status_code
        obj.ok = 200 <= status_code < 300
        obj.reason = HTTPStatus(status_code).phrase
        obj.headers = {"Content-Type": "text/html; charset=utf-8"}
        obj.content = html
        return obj


class LocalSuapHTTPMock:
    """
    Mock HTTP client para o plugin `local_suap` do Moodle.

    Usado pelo broker `Suap2LocalSuapBroker` (suap2local_suap).

    Simula o endpoint `/local/suap/api/index.php` com os serviços:
      - sync_up_enrolments  (POST)
      - sync_down_grades    (GET)
    """

    TOKEN = "changeme"  # noqa: S105

    def _validate_authentication(self, headers: dict) -> MockHTTPResponse | None:
        auth = headers.get("Authentication") or headers.get("authentication")
        if auth is None:
            return MockHTTPResponse(
                {"error": {"message": "Bad Request - Authentication not informed", "code": 400}},
                status_code=400,
            )
        if auth != f"Token {self.TOKEN}":  #
            return MockHTTPResponse(
                {"error": {"message": "Unauthorized", "code": 401}},
                status_code=401,
            )
        return None

    def _extract_service(self, url: str) -> str:
        query = urlparse(url).query
        if not query:
            return ""
        first_token = query.split("&", 1)[0]
        return first_token.split("=", 1)[0]

    def _extract_query_params(self, url: str) -> dict[str, str]:
        query = urlparse(url).query
        return {key: values[0] for key, values in parse_qs(query).items() if values}

    SYNC_UP_REQUIRED_FIELDS = {
        "campus": ["id", "sigla", "descricao"],
        "curso": ["id", "codigo", "nome"],
        "turma": ["id", "codigo"],
        "componente": ["id", "sigla", "descricao"],
        "diario": ["id", "sigla", "situacao"],
    }

    def sync_up_enrolments(self, parsed, jsonbody: dict | None = None) -> MockHTTPResponse:
        payload = jsonbody or {}
        missing = [
            f"{field}.{sub}" if field in payload else field
            for field, subfields in self.SYNC_UP_REQUIRED_FIELDS.items()
            for sub in (subfields if field in payload else [""])
            if field not in payload or sub not in payload[field]
        ]
        if missing:
            return MockHTTPResponse(
                {"error": {"message": f"Campos obrigatórios ausentes: {', '.join(missing)}", "code": 422}},
                status_code=422,
            )
        base = f"{parsed.scheme}://{parsed.netloc}"
        return MockHTTPResponse(
            {
                "url": f"{base}/course/view.php?id=1",
                "url_sala_coordenacao": f"{base}/course/view.php?id=2",
                "roles_not_found": [],
            }
        )

    def sync_down_grades(self, url: str) -> MockHTTPResponse:
        params = self._extract_query_params(url)
        diario_id = params.get("diario_id", "")
        return MockHTTPResponse(
            [
                {
                    "matricula": "20260001",
                    "nota": 8.5,
                    "diario_id": diario_id,
                    "mock": True,
                }
            ]
        )

    def request(
        self, method: str, url: str, jsonbody: dict | None = None, headers: dict | None = None
    ) -> MockHTTPResponse:
        parsed = urlparse(url)
        if not parsed.path.endswith("/local/suap/api/index.php"):
            return MockHTTPResponse({"error": "Endpoint Moodle mock não reconhecido."}, status_code=404)

        service = self._extract_service(url)
        if service not in _LOCAL_SUAP_KNOWN_SERVICES:
            return MockHTTPResponse(
                {"error": {"message": "Serviço não existe", "code": 404}},
                status_code=404,
            )

        auth_error = self._validate_authentication(headers or {})
        if auth_error:
            return auth_error

        if service not in _LOCAL_SUAP_IMPLEMENTED_SERVICES:
            return MockHTTPResponse(
                {"error": {"message": "Não implementado", "code": 501}},
                status_code=501,
            )

        if method == "POST" and service == "sync_up_enrolments":
            return self.sync_up_enrolments(parsed, jsonbody)

        if method == "GET" and service == "sync_down_grades":
            return self.sync_down_grades(url)

        return MockHTTPResponse({"error": f"Serviço não suportado no mock: {service}"}, status_code=400)

    def get(self, url: str, headers: dict | None = None) -> MockHTTPResponse:
        return self.request("GET", url, headers=headers)

    def post(self, url: str, jsonbody: dict | None = None, headers: dict | None = None) -> MockHTTPResponse:
        return self.request("POST", url, jsonbody=jsonbody, headers=headers)


class ToolSgaHTTPMock:
    """
    Mock HTTP client para o plugin `tool_sga` do Moodle.

    Usado pelos brokers:
      - `Suap2ToolSgaBroker` (suap2tool_sga)
      - `Sga2ToolSgaBroker`  (sga2tool_sga)

    **Atenção:** os brokers correspondentes ainda não estão implementados,
    portanto este mock retorna 501 para qualquer chamada enquanto aguarda
    a definição da API do plugin `tool_sga`.
    """

    TOKEN = "changeme"  # noqa: S105

    PLUGIN_PATH = "/local/tool_sga/api/index.php"

    def _validate_authentication(self, headers: dict) -> MockHTTPResponse | None:
        auth = headers.get("Authentication") or headers.get("authentication")
        if auth is None:
            return MockHTTPResponse(
                {"error": {"message": "Bad Request - Authentication not informed", "code": 400}},
                status_code=400,
            )
        if auth != f"Token {self.TOKEN}":
            return MockHTTPResponse(
                {"error": {"message": "Unauthorized", "code": 401}},
                status_code=401,
            )
        return None

    def request(
        self, method: str, url: str, jsonbody: dict | None = None, headers: dict | None = None
    ) -> MockHTTPResponse:
        parsed = urlparse(url)
        if not parsed.path.endswith(self.PLUGIN_PATH):
            return MockHTTPResponse({"error": "Endpoint Moodle mock não reconhecido."}, status_code=404)

        auth_error = self._validate_authentication(headers or {})
        if auth_error:
            return auth_error

        # Broker ainda não implementado — todos os serviços retornam 501
        return MockHTTPResponse(
            {"error": {"message": "Broker tool_sga ainda não implementado.", "code": 501}},
            status_code=501,
        )

    def get(self, url: str, headers: dict | None = None) -> MockHTTPResponse:
        return self.request("GET", url, headers=headers)

    def post(self, url: str, jsonbody: dict | None = None, headers: dict | None = None) -> MockHTTPResponse:
        return self.request("POST", url, jsonbody=jsonbody, headers=headers)


# Alias mantido para compatibilidade com código existente.
# Prefer using LocalSuapHTTPMock directly.
MoodleHTTPMock = LocalSuapHTTPMock


_server_lock = threading.Lock()
_server = None
_server_thread = None


def start_mock_moodle_server_in_background() -> None:
    """Start a lightweight HTTP server serving mocked Moodle endpoints.

    Cobre apenas o broker `Suap2LocalSuapBroker` (plugin `local_suap`).
    Os brokers `Suap2ToolSgaBroker` e `Sga2ToolSgaBroker` ainda não estão
    implementados e, portanto, não possuem servidor mock em background.
    """
    global _server
    global _server_thread

    if not getattr(settings, "MOODLE_HTTP_MOCK_BACKGROUND", False):
        return

    with _server_lock:
        if _server_thread is not None and _server_thread.is_alive():
            return

        host = getattr(settings, "MOODLE_HTTP_MOCK_HOST", "127.0.0.1")
        port = int(getattr(settings, "MOODLE_HTTP_MOCK_PORT", 18091))
        mock = LocalSuapHTTPMock()

        class Handler(BaseHTTPRequestHandler):
            def _write_response(self, response: MockHTTPResponse):
                self.send_response(response.status_code)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response.content)

            def do_GET(self):
                response = mock.get(self.path, headers=dict(self.headers))
                self._write_response(response)

            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    body = json.loads(raw_body.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    body = {}
                response = mock.post(self.path, jsonbody=body, headers=dict(self.headers))
                self._write_response(response)

            def log_message(self, format, *args):
                logger.debug("local-suap-mock: " + format, *args)

        _server = ThreadingHTTPServer((host, port), Handler)
        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()
        logger.info("Moodle mock HTTP server running on %s:%s", host, port)
