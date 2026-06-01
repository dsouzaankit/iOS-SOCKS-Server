"""Keep http.server from writing access lines to stderr (Pythonista console)."""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler


class NoAccessLogMixin:
    """Suppress all BaseHTTPRequestHandler access/error stderr logging."""

    def log_request(self, code="-", size="-"):
        pass

    def log_message(self, format, *args):
        pass

    def log_error(self, format, *args):
        pass

    def send_response(self, code, message=None):
        self.send_response_only(code, message)
        self.send_header("Server", self.version_string())
        self.send_header("Date", self.date_time_string())


class OptionalAccessLogMixin:
    """Access logs only when server.access_log is True."""

    def log_request(self, code="-", size="-"):
        if not getattr(self.server, "access_log", False):
            return
        if isinstance(code, HTTPStatus):
            code = code.value
        self.log_message('"%s" %s %s', self.requestline, str(code), str(size))

    def log_message(self, format, *args):
        if not getattr(self.server, "access_log", False):
            return
        import logging

        logging.getLogger("http").info(
            "%s: " + format, getattr(self, "log_tag", "?"), *args
        )

    def send_response(self, code, message=None):
        if getattr(self.server, "access_log", False):
            BaseHTTPRequestHandler.send_response(self, code, message)
            return
        self.send_response_only(code, message)
        self.send_header("Server", self.version_string())
        self.send_header("Date", self.date_time_string())
