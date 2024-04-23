import requests

from ..types import URL, HttpHeaders, JSON
from ..exceptions import RequestException


JSON_HEADERS: HttpHeaders = {
    "accept": "application/json",
    "content-type": "application/json",
}

RESPONSE_ERROR_KEYS = ["error", "errors"]


def validate_response(response: requests.Response):
    error_msgs: list[str] = []
    response_json = response.json()

    if isinstance(response_json, dict):
        for error_key in RESPONSE_ERROR_KEYS:
            if error_key in response_json:
                error_obj = response_json[error_key]
                if isinstance(error_obj, list) and len(error_obj) > 0:
                    error_msgs.extend([str(error_msg) for error_msg in error_obj])
                if isinstance(error_obj, dict):
                    error_msgs.extend(
                        [
                            f"{error_key}: {error_value}"
                            for error_key, error_value in error_obj.items()
                        ]
                    )
                elif isinstance(error_obj, str):
                    error_msgs.append(error_obj)

    if len(error_msgs) > 0 or response.status_code != requests.codes.ok:
        raise RequestException(
            "request failed",
            status_code=response.status_code,
            result=response_json,
            error_messages=error_msgs,
        )

    return


def get_json_request(url: URL, params=None, headers: HttpHeaders = JSON_HEADERS):
    try:
        res = requests.get(url, params=params, headers=headers)
        validate_response(res)
        return res.json()
    except requests.RequestException as e:
        raise RequestException("get request failed", exception=e)


def post_json_request(url: URL, payload: JSON, headers: HttpHeaders = JSON_HEADERS):
    try:
        res = requests.post(url, json=payload, headers=headers)
        validate_response(res)
        return res.json()
    except requests.RequestException as e:
        raise RequestException("post request failed", exception=e)
