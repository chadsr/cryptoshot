from collections.abc import Mapping
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from requests.structures import CaseInsensitiveDict

from ...services.types import JSON, HttpHeaders

from .exceptions import RequestException, TooManyRequestsException

HEADERS_JSON: HttpHeaders = {
    "accept": "application/json",
    "content-type": "application/json",
}

HEADERS_URL_ENCODED = {
    "content-type": "application/x-www-form-urlencoded; charset=utf-8",
    "accept": "application/json",
}

RESPONSE_ERROR_KEYS = ["error", "errors"]

DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 10.0)


def _parse_retry_after(headers: CaseInsensitiveDict[str]) -> float | None:
    val = headers.get("Retry-After")
    if not val:
        return None
    # Two forms per RFC 7231: delta-seconds or HTTP-date
    try:
        # Try delta-seconds
        secs = float(val)
        if secs < 0:
            return None
        return secs
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (dt - now).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


def validate_response(response: requests.Response):
    error_msgs: list[JSON] = []
    response_json = response.json()

    if isinstance(response_json, dict):
        for error_key in RESPONSE_ERROR_KEYS:
            if error_key in response_json:
                error_obj = response_json[error_key]
                if isinstance(error_obj, list) and len(error_obj) > 0:
                    error_msgs.extend([str(error_msg) for error_msg in error_obj])
                elif isinstance(error_obj, dict) and len(error_obj) > 0:
                    error_msgs.append(error_obj)
                elif isinstance(error_obj, str) and len(error_obj) > 0:
                    error_msgs.append(error_obj)

    if len(error_msgs) > 0 or response.status_code != 200:
        status_code = response.status_code
        result = response_json
        error_messages = error_msgs
        headers = dict(response.headers)

        match status_code:
            case 429:
                raise TooManyRequestsException(
                    "Too many requests",
                    status_code=status_code,
                    result=result,
                    error_messages=error_messages,
                    headers=headers,
                    retry_after_seconds=_parse_retry_after(response.headers),
                )
            case _:
                raise RequestException(
                    "Request failed",
                    status_code=status_code,
                    result=result,
                    error_messages=error_messages,
                    headers=headers,
                )


def get_json_request(
    url: str,
    params: str | bytes | Mapping[str, object] | None = None,
    headers: HttpHeaders = HEADERS_JSON,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
) -> JSON:
    try:
        req_params: str | bytes | Mapping[str, str] | None
        if isinstance(params, Mapping):
            # Convert numeric/bool params to strings for requests
            req_params = {k: str(v) for k, v in params.items()}
        else:
            req_params = params

        res = requests.get(url, params=req_params, headers=headers, timeout=timeout)
        validate_response(res)
        return res.json()
    except requests.RequestException as e:
        raise RequestException("get request failed", exception=e) from e


def post_json_request(
    url: str,
    json: JSON | None = None,
    data: bytes | None = None,
    headers: HttpHeaders = HEADERS_JSON,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
) -> JSON:
    try:
        res = requests.post(url, json=json, data=data, headers=headers, timeout=timeout)
        validate_response(res)
        return res.json()
    except requests.RequestException as e:
        raise RequestException("post request failed", exception=e) from e
