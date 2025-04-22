from typing import Any
import requests

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

DEFAULT_TIMEOUT = 10


def validate_response(response: requests.Response):
    error_msgs: list[JSON] = []
    response_json = response.json()

    if isinstance(response_json, dict):
        for error_key in RESPONSE_ERROR_KEYS:
            if error_key in response_json:
                error_obj = response_json[error_key]
                if isinstance(error_obj, list) and len(error_obj) > 0:
                    error_msgs.extend([str(error_msg) for error_msg in error_obj])
                if isinstance(error_obj, dict) and len(error_obj) > 0:
                    error_msgs.append(error_obj)
                elif isinstance(error_obj, str) and len(error_obj) > 0:
                    error_msgs.append(error_obj)

    if len(error_msgs) > 0 or response.status_code != 200:
        exception_args = {
            "status_code": response.status_code,
            "result": response_json,
            "error_messages": error_msgs,
        }

        match response.status_code:
            case 429:
                raise TooManyRequestsException("Too many requests", **exception_args)
            case _:
                raise RequestException("Request failed", **exception_args)


def get_json_request(
    url: str,
    params: str | bytes | dict[str, Any] | None = None,
    headers: HttpHeaders = HEADERS_JSON,
    timeout: int = DEFAULT_TIMEOUT,
) -> JSON:
    try:
        res = requests.get(url, params=params, headers=headers, timeout=timeout)
        validate_response(res)
        return res.json()
    except requests.RequestException as e:
        raise RequestException("get request failed", exception=e) from e


def post_json_request(
    url: str,
    json: JSON | None = None,
    data: bytes | None = None,
    headers: HttpHeaders = HEADERS_JSON,
    timeout: int = DEFAULT_TIMEOUT,
) -> JSON:
    try:
        res = requests.post(url, json=json, data=data, headers=headers, timeout=timeout)
        validate_response(res)
        return res.json()
    except requests.RequestException as e:
        raise RequestException("post request failed", exception=e) from e
