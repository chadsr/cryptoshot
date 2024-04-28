from ..types import JSON
from ..exceptions import ServiceException


class ApiException(ServiceException):
    pass


class ApiUnavailableException(ApiException):
    def __init__(self, reason: str | None):
        self.reason = reason


class InvalidAPIKeyException(ApiException):
    pass


class InvalidAPIConfigException(ApiException):
    pass


class ApiRateLimitException(ApiException):
    pass


class RequestException(ApiException):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        result: JSON | None = None,
        error_messages: list[str | JSON] | None = None,
        exception: Exception | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.result_json = result
        self.exception = exception
        self.error_messages = error_messages


class TooManyRequestsException(RequestException):
    pass
