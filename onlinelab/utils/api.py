"""APIs related extensions to JSON-RPC library. """

from .jsonrpc import AsyncJSONRPCRequestHandler

class APIError(Exception):
    """Base class for API errors. """

class APIRequestHandler(AsyncJSONRPCRequestHandler):
    """JSON-RPC handler extended with API helper functions. """

    def return_api_result(self, result=None):
        """Return higher-level JSON-RPC result response. """
        if result is None:
            result = {}

        result['ok'] = True

        self.return_result(result)

    def return_api_error(self, reason=None):
        """Return higher-level JSON-RPC error response. """
        self.return_result({'ok': False, 'reason': reason})

    def _handle_exception(self, exc):
        """Handle an exception or return ``False``. """
        if isinstance(exc, APIError):
            self.return_api_error(exc.error)
        else:
            return False

