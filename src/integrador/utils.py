import json
import logging
import urllib.error
import urllib.request
from http.client import HTTPException

logger = logging.getLogger(__name__)


REQUEST_TIMEOUT_SECONDS = 10


class SyncError(Exception):
    def __init__(self, message, code, retorno=None, params=None):
        super().__init__(message, code, params)
        self.message = message
        self.code = code
        self.retorno = retorno
        logger.debug(f"{code}: {message} - {retorno}")


def _handle_http_request_exception(exc: Exception, url: str, encoding: str = "utf-8"):
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body = exc.read().decode(encoding)
            try:
                error_data = json.loads(body)
            except Exception:
                error_data = None
        except Exception:
            error_data = None

        if error_data and "error" in error_data:
            err_msg = error_data["error"].get("message", exc.reason)
            err_code = error_data["error"].get("code", exc.code)
            raise SyncError(err_msg, err_code, retorno=error_data)

        exc_new = HTTPException(f"{exc.code} - {exc.reason}")
        setattr(exc_new, "status", exc.code)
        setattr(exc_new, "reason", exc.reason)
        setattr(exc_new, "headers", dict(exc.headers or {}))
        setattr(exc_new, "url", url)
        raise exc_new
    else:
        exc_new = HTTPException(f"502 - {exc.reason}")
        setattr(exc_new, "status", 502)
        setattr(exc_new, "reason", str(exc.reason))
        setattr(exc_new, "headers", {})
        setattr(exc_new, "url", url)
        raise exc_new


def _send_request(req, timeout, url, encoding="utf-8", decode=True):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            byte_array_content = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        _handle_http_request_exception(exc, url, encoding)

    return byte_array_content.decode(encoding) if decode and encoding is not None else byte_array_content


def http_get(url, headers: dict | None = None, encoding="utf-8", decode=True, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT_SECONDS)
    req_headers = headers or {}
    req = urllib.request.Request(url, headers=req_headers, method="GET")  # noqa: S310
    return _send_request(req, timeout, url, encoding, decode)


def http_post(
    url,
    jsonbody: dict | None = None,
    headers: dict | None = None,
    encoding="utf-8",
    decode=True,
    **kwargs,
):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT_SECONDS)
    req_headers = headers or {}

    if jsonbody is not None:
        payload = json.dumps(jsonbody).encode(encoding)
        if "Content-Type" not in req_headers and "content-type" not in req_headers:
            req_headers["Content-Type"] = "application/json"
    else:
        payload = None

    req = urllib.request.Request(url, data=payload, headers=req_headers, method="POST")  # noqa: S310
    return _send_request(req, timeout, url, encoding, decode)


def http_get_json(url, headers={}, encoding="utf-8", json_kwargs=None, **kwargs):
    content = http_get(url, headers=headers, encoding=encoding, **kwargs)
    return json.loads(content, **(json_kwargs or {}))


def http_post_json(
    url,
    jsonbody: dict | None = None,
    headers: dict | None = None,
    encoding="utf-8",
    json_kwargs=None,
    **kwargs,
):
    content = http_post(url, jsonbody=jsonbody, headers=headers or {}, encoding=encoding, **kwargs)
    try:
        result = json.loads(content, **(json_kwargs or {}))
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to decode JSON response from {url}: {exc.msg} - Response content: \n{content}\n")
        raise exc
    return result
