import logging


class LoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger: logging.Logger):
        super().__init__(logger, extra={})
