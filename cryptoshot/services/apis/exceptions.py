from ..types import JSON
from ..exceptions import ServiceException


class ApiException(ServiceException):
    pass


class ApiUnavailableException(ApiException):
    def __init__(self, reason: str | None):
        super().__init__("API temporarily unavailable")
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
        headers: dict[str, str] | None = None,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.result_json = result
        self.exception = exception
        self.error_messages = error_messages
        self.headers = headers
        # If present, how long the client should wait before retrying
        self.retry_after_seconds = retry_after_seconds


class TooManyRequestsException(RequestException):
    pass
