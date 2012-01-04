"""Implementation of JSON-RPC specification. """

import uuid
import logging
import urlparse
import functools
import traceback

import tornado.web
import tornado.escape

from tornado.httpclient import HTTPClient, AsyncHTTPClient, HTTPRequest
from tornado.httputil import HTTPHeaders

from .extensions import ExtRequestHandler

def datetime(obj):
    """Encode ``datetime`` object as a string. """
    if obj is not None:
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return None

class JSONRPCError(Exception):
    """Base class for JSON-RPC errors. """

    def __init__(self, data=None):
        self.data = data

class ParseError(JSONRPCError):
    code = -32700
    text = "Parse error"

class InvalidRequest(JSONRPCError):
    code = -32600
    text = "Invalid request"

class MethodNotFound(JSONRPCError):
    code = -32601
    text = "Method not found"

class InvalidParams(JSONRPCError):
    code = -32602
    text = "Invalid params"

class InternalError(JSONRPCError):
    code = -32603
    text = "Server error"

class AuthenticationRequired(JSONRPCError):
    code = -31001
    text = "Authentication required"

def method(func):
    """Mark a function as a non-authenticated JSON-RPC method. """
    func.jsonrpc = True
    return func

def authenticated(func):
    """Mark a function as an authenticated JSON-RPC method. """
    func.authenticated = True
    func.jsonrpc = True
    return func

class AsyncJSONRPCRequestHandler(ExtRequestHandler):
    """Simple handler of JSON-RPC requests. """

    def return_result(self, result=None):
        """Return properly formatted JSON-RPC result response. """
        response = {'result': result, 'error': None, 'id': self.id}
        body = tornado.escape.json_encode(response)

        try:
            self.write(body)
            self.finish()
        except IOError:
            logging.warning("JSON-RPC: warning: connection was closed")
        else:
            logging.info("JSON-RPC: '%s' method call ended successfully" % self.method)

    def return_error(self, code, message, data=None):
        """Return properly formatted JSON-RPC error response. """
        error = { 'code': code, 'message': message }

        if data is not None:
            error['data'] = data

        response = {'result': None, 'error': error}

        if hasattr(self, 'id'):
            response['id'] = self.id

        body = tornado.escape.json_encode(response)

        try:
            self.set_status(400)
            self.write(body)
            self.finish()
        except IOError:
            logging.warning("JSON-RPC: warning: connection was closed")
        else:
            logging.info("JSON-RPC: error: %s (%s)" % (message, code))

    @method
    def system__describe(self):
        """Return description of methods available in this handler. """
        procs = []

        for name in dir(self):
            if name.startswith('_'):
                continue

            if name.startswith('system'):
                continue

            func = getattr(self, name)

            if not getattr(func, 'jsonrpc', False):
                continue

            procs.append({
                'name': name.replace('__', '.'),
                'summary': func.__doc__,
                'authenticated': getattr(func, 'authenticated', False),
            })

        self.return_result({'procs': procs})

    def is_json_content_type(self):
        """Check if Content-Type header is available and set properly. """
        content_type = self.request.headers.get('Content-Type')

        if content_type is None or not content_type.startswith('application/json'):
            logging.warning("JSON-RPC: error: invalid Content-Type: %s" % content_type)
            self.set_status(400)
            self.finish()
            return False

        return True

    @tornado.web.asynchronous
    def post(self):
        """Receive and process JSON-RPC requests. """
        logging.info("JSON-RPC: received RPC method call")

        if not self.is_json_content_type():
            return

        try:
            try:
                data = tornado.escape.json_decode(self.request.body)
            except ValueError:
                raise ParseError
            else:
                for name in ['jsonrpc', 'id', 'method', 'params']:
                    value = data.get(name, None)

                    if value is not None:
                        setattr(self, name, value)
                    else:
                        raise InvalidRequest("'%s' parameter is mandatory" % name)

                method = getattr(self, self.method.replace('.', '__'), None)

                if method is None or not getattr(method, 'jsonrpc', False):
                    raise MethodNotFound("'%s' is not a valid method" % self.method)

                if getattr(method, 'authenticated', False) and not self.user.is_authenticated():
                    raise AuthenticationRequired("%s' method requires authentication" % self.method)

                self._call_method(method, self.params)
        except JSONRPCError as exc:
            self.return_error(exc.code, exc.text, exc.data)

    def _fix_keys(self, obj):
        """Convert Unicode keys to strings in a dict. """
        return dict([ (str(k), v) for k, v in obj.items() ])

    def _handle_exception(self, exc):
        """Handle an exception or return ``False``. """
        return False

    def _call_method(self, method, params):
        """Call a JSON-RPC method with the given arguments. """
        if isinstance(params, dict):
            try:
                params = self._fix_keys(params)
            except UnicodeError:
                raise InvalidParams

        try:
            if isinstance(params, dict):
                return method(**params)
            elif isinstance(params, list):
                return method(*params)
            else:
                raise TypeError
        except TypeError:
            raise InvalidParams
        except Exception as exc:
            if self._handle_exception(exc) is False:
                traceback.print_exc()
                raise InternalError

class JSONRPCProxy(object):
    """Simple proxy for making JSON-RPC requests. """

    def __init__(self, url, rpc=None, log_errors=True):
        if rpc is not None:
            self.url = urlparse.urljoin(url, rpc)
        else:
            self.url = url

        self.log_errors = log_errors

    def call(self, method, params, okay=None, fail=None):
        """Make an asynchronous JSON-RPC method call. """
        body = tornado.escape.json_encode({
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': uuid.uuid4().hex,
        });

        logging.info("JSON-RPC: call '%s' method on %s" % (method, self.url))

        headers = HTTPHeaders({'Content-Type': 'application/json'})
        request = HTTPRequest(self.url, method='POST', body=body,
            headers=headers, request_timeout=0)

        if okay is None and fail is None:
            client = HTTPClient()
            response = client.fetch(request)

            if response.code != 200 or not response.body:
                return None

            try:
                data = tornado.escape.json_decode(response.body)
            except ValueError:
                return None
            else:
                return data
        else:
            client = AsyncHTTPClient()
            client.fetch(request, functools.partial(self._on_response, okay, fail))

    def _on_response(self, okay, fail, response):
        """Parse and process response from a JSON-RPC server. """
        error = None

        try:
            if response.code != 200 and self.log_errors:
                logging.error("JSON-RPC: got %s HTTP response code" % response.code)

            if response.body is None:
                raise JSONRPCError("communication failed")

            try:
                data = tornado.escape.json_decode(response.body)
            except ValueError:
                raise JSONRPCError("parsing response failed")
            else:
                error = data.get('error', None)

                if error is not None:
                    raise JSONRPCError("code=%(code)s, message=%(message)s" % error)

                if okay is not None:
                    okay(data.get('result', None))
        except JSONRPCError as exc:
            if self.log_errors:
                logging.error("JSON-RPC: error: %s" % exc.data)

            if fail is not None:
                fail(error, http_code=response.code)

